"""
Extract structured bill data from MSEDCL electricity bills using OpenAI Vision.

Pipeline: multi-variant preprocess → Vision API → gap-fill pass → validate.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError

from config import GAP_FILL_ENABLED, get_openai_api_key, get_openai_model, is_openai_key_configured
from services.bill_validator import sanitize_for_api, validate_and_normalize
from services.extraction_prompt import (
    GAP_FILL_PROMPT,
    PRIORITY_GAP_FIELDS,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from services.extraction_schema import MSEDCL_BILL_JSON_SCHEMA
from services.image_preprocessor import preprocess_for_extraction
from services.llm_parser import normalize_text_fields

logger = logging.getLogger(__name__)

VISION_DETAIL = "high"
MAX_OUTPUT_TOKENS = 16384
GAP_FILL_THRESHOLD = 8  # Only re-scan when many fields still missing


def _encode_image_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _count_missing_priority(raw: dict[str, Any]) -> list[str]:
    missing = []
    for field in PRIORITY_GAP_FIELDS:
        val = raw.get(field)
        if field == "monthly_history":
            if not val or (isinstance(val, list) and len(val) == 0):
                missing.append(field)
        elif _is_empty(val):
            missing.append(field)
    return missing


def _merge_monthly_history(a: Any, b: Any) -> list[dict[str, Any]]:
    """Merge monthly history arrays, dedupe by month name, prefer entries with more data."""
    combined: dict[str, dict[str, Any]] = {}

    for source in (a, b):
        if not isinstance(source, list):
            continue
        for entry in source:
            if not isinstance(entry, dict):
                continue
            month = entry.get("month")
            if not month:
                continue
            key = str(month).strip().lower()
            existing = combined.get(key)
            if existing is None or len(entry) > len(existing):
                combined[key] = entry

    return list(combined.values())


def merge_extraction_results(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Fill null fields in primary from secondary; merge monthly history."""
    merged = dict(primary)

    for key, val in secondary.items():
        if key == "monthly_history":
            merged[key] = _merge_monthly_history(merged.get(key), val)
        elif _is_empty(merged.get(key)) and not _is_empty(val):
            merged[key] = val

    return merged


def _build_vision_content(
    image_variants: list[tuple[Path, str]],
    user_text: str = USER_PROMPT,
) -> list[dict[str, Any]]:
    """Build message content with instructions + labelled image variants."""
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    for path, caption in image_variants:
        content.append({"type": "text", "text": f"--- {caption} ---"})
        b64 = _encode_image_base64(path)
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64}",
                    "detail": VISION_DETAIL,
                },
            }
        )
    return content


def _call_vision_api(
    client: OpenAI,
    model: str,
    image_variants: list[tuple[Path, str]],
    user_text: str = USER_PROMPT,
) -> dict[str, Any]:
    """Invoke OpenAI with JSON schema structured output."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_vision_content(image_variants, user_text)},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": MSEDCL_BILL_JSON_SCHEMA,
            },
        )
    except OpenAIError as exc:
        err_text = str(exc).lower()
        if "json_schema" in err_text or "response_format" in err_text:
            logger.warning("json_schema unsupported, falling back to json_object: %s", exc)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0,
                response_format={"type": "json_object"},
            )
        else:
            logger.exception("OpenAI API error")
            raise ValueError(f"OpenAI API error: {exc}") from exc

    raw_content = response.choices[0].message.content
    if not raw_content:
        raise ValueError("OpenAI returned an empty response.")

    return _parse_json_response(raw_content.strip())


def extract_bill_data(image_paths: Path | list[Path]) -> dict[str, Any]:
    """
    Send preprocessed bill image(s) to OpenAI Vision and return validated fields.

    Uses multi-variant scanning + optional gap-fill pass for completeness.
    """
    if not is_openai_key_configured():
        raise ValueError(
            "OpenAI API key is missing or still set to the placeholder. "
            "Open backend/.env, paste your real key (starts with sk-), save the file, "
            "then restart the backend server."
        )

    paths = [image_paths] if isinstance(image_paths, Path) else list(image_paths)
    paths = [p for p in paths if p.exists()]

    if not paths:
        raise ValueError("No valid image files provided for extraction.")

    logger.info("Preparing multi-variant scans for %d source page(s)", len(paths))
    variants = preprocess_for_extraction(paths)

    api_key = get_openai_api_key()
    model = get_openai_model()
    client = OpenAI(api_key=api_key)

    logger.info(
        "Extraction pass 1 — OpenAI Vision (%s), %d image variant(s)",
        model,
        len(variants),
    )
    raw_data = _call_vision_api(client, model, variants)

    missing = _count_missing_priority(raw_data)
    if GAP_FILL_ENABLED and len(missing) >= GAP_FILL_THRESHOLD:
        # Gap-fill uses full-page scans only (skip magnified crops) for speed
        full_page_variants = [
            (p, c) for p, c in variants if "magnified" not in c.lower()
        ] or variants
        logger.info(
            "Extraction pass 2 — gap-fill for %d missing fields (using %d images)",
            len(missing),
            len(full_page_variants),
        )
        gap_prompt = GAP_FILL_PROMPT.format(missing_fields=", ".join(missing))
        secondary = _call_vision_api(client, model, full_page_variants, user_text=gap_prompt)
        raw_data = merge_extraction_results(raw_data, secondary)

    raw_data = normalize_text_fields(raw_data)
    validated = validate_and_normalize(raw_data)
    filled = sum(1 for k, v in validated.items() if v is not None and not k.startswith("_"))
    logger.info("Extraction complete — %d fields populated", filled)
    return sanitize_for_api(validated)


def _parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.split("\n") if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON: %s", text[:500])
        raise ValueError(
            "Failed to parse AI response as JSON. Please try uploading again."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("AI response was not a JSON object.")

    return data


def validate_extracted_data(data: dict[str, Any]) -> dict[str, Any]:
    """Re-validate user-edited data before Excel generation."""
    validated = validate_and_normalize(data)
    return sanitize_for_api(validated)
