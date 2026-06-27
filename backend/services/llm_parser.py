"""
LLM-based text normalization for OCR-extracted bill fields.

Runs a lightweight pass to fix OCR noise in names, addresses, and dates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI, OpenAIError

from config import get_openai_api_key, get_openai_model, is_openai_key_configured
from services.utils import is_null

logger = logging.getLogger(__name__)

TEXT_FIELDS_TO_NORMALIZE = [
    "consumer_name",
    "address",
    "billing_month",
    "billing_period",
    "bill_date",
    "due_date",
    "division",
    "sub_division",
    "billing_cycle",
    "tariff_category",
    "GST_number",
]

NORMALIZE_PROMPT = """You fix OCR errors in Maharashtra MSEDCL electricity bill text fields.
Preserve original meaning. Fix spacing, broken Devanagari/English, date formats.
Return JSON with the SAME keys provided. Use null for keys that were null.
Do not invent data. Only correct obvious OCR mistakes."""


def normalize_text_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Optional LLM pass to clean OCR text fields after Vision extraction.
    Returns merged data; on failure returns input unchanged.
    """
    if not is_openai_key_configured():
        return data

    payload = {
        k: data.get(k)
        for k in TEXT_FIELDS_TO_NORMALIZE
        if not is_null(data.get(k))
    }
    if not payload:
        return data

    client = OpenAI(api_key=get_openai_api_key())
    model = get_openai_model()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": NORMALIZE_PROMPT},
                {
                    "role": "user",
                    "content": f"Normalize these bill text fields:\n{json.dumps(payload, ensure_ascii=False)}",
                },
            ],
            max_tokens=2048,
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return data
        fixed = json.loads(content)
        if isinstance(fixed, dict):
            merged = dict(data)
            for k, v in fixed.items():
                if k in TEXT_FIELDS_TO_NORMALIZE and not is_null(v):
                    merged[k] = v
            logger.info("LLM text normalization applied to %d fields", len(fixed))
            return merged
    except (OpenAIError, json.JSONDecodeError) as exc:
        logger.warning("Text normalization skipped: %s", exc)

    return data
