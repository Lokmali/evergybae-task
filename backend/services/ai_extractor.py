"""
Extract structured bill data from MSEDCL electricity bills using OpenAI Vision.

Supports multi-page PDFs (consumption history on page 2+) and post-AI validation.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError

from config import get_openai_api_key, get_openai_model, is_openai_key_configured
from services.bill_validator import sanitize_for_api, validate_and_normalize

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert document intelligence system specialized in Maharashtra MSEDCL (Maharashtra State Electricity Distribution Company Limited) electricity bills.

You read BOTH Marathi and English text fluently.

CRITICAL RULES:
1. Search the ENTIRE document — every page, every section, every table.
2. Do NOT stop after finding the first occurrence — cross-check labels with values.
3. Match each value to the EXACT field label printed on the bill.
4. NEVER invent or guess data. If a field is not visible, return null.
5. NEVER confuse these distinct fields:
   - consumer_number: 10–15 digit account/consumer ID (NOT meter serial)
   - meter_number: Consumer meter number printed near meter details
   - meter_serial_number: Physical meter serial / make number (separate from consumer number)
   - tariff_code: Short code like A50, B21 (NOT load, NOT full tariff description)
   - tariff_category: Full tariff description like "90/LT I Res 1-Phase" (NOT kW load)
   - contract_load / sanctioned_load / connected_load: Numeric kW ONLY (e.g. 3.30) — NEVER extract from tariff text
   - previous_reading / current_reading: Meter kWh readings (large integers, e.g. 33674, 33699)
   - billing_cycle: Cycle path like "2020/TUMSAR SDN/BHANDARA DIVISION"
   - division: e.g. "BHANDARA DIVISION"
   - sub_division: e.g. "TUMSAR SDN"

LOAD EXTRACTION (VERY IMPORTANT):
- Look for labels: "Contract Load", "Sanctioned Load", "Connected Load", "Load (KW)", "Load (kW)"
- Extract ONLY the numeric kW value next to that label (e.g. 3.30)
- "90" in "90/LT I Res" is NOT load — it is part of tariff category
- "0.90 KW" from tariff code is WRONG — real load is typically 1.0–50 kW for domestic bills

CHARGES:
Extract numeric amounts ONLY (no ₹ symbol) for:
fixed_charges, energy_charges, fuel_adjustment, electricity_duty, tax_on_sale, bill_amount

CONSUMPTION:
- units_consumed: numeric kWh only (e.g. 25, not "25 kWh")
- bill_amount: numeric INR only (e.g. 1460, not "₹1460.00")

12-MONTH HISTORY:
If a consumption graph/table shows last 12 months, extract ALL months into monthly_history array.
Each entry: {"month": "February 2025", "units": 99, "amount": null}
Include amount only if visible for that month.

OUTPUT:
Return STRICT JSON only. No markdown. No explanation. No text outside JSON."""

USER_PROMPT = """Extract ALL fields from this Maharashtra MSEDCL electricity bill.
Read every page provided. Return this exact JSON structure with null for missing fields:

{
  "consumer_name": null,
  "consumer_number": null,
  "billing_month": null,
  "billing_period": null,
  "bill_date": null,
  "due_date": null,
  "address": null,
  "tariff_category": null,
  "meter_number": null,
  "meter_serial_number": null,
  "division": null,
  "sub_division": null,
  "tariff_code": null,
  "contract_load": null,
  "connected_load": null,
  "sanctioned_load": null,
  "voltage": null,
  "power_factor": null,
  "billing_cycle": null,
  "gst_number": null,
  "previous_reading": null,
  "current_reading": null,
  "units_consumed": null,
  "bill_amount": null,
  "fixed_charges": null,
  "energy_charges": null,
  "fuel_adjustment": null,
  "electricity_duty": null,
  "tax_on_sale": null,
  "monthly_history": []
}"""


def _encode_image_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _media_type_for_path(image_path: Path) -> str:
    ext = image_path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "image/png"


def _build_vision_content(image_paths: list[Path]) -> list[dict[str, Any]]:
    """Build OpenAI message content with text + all bill page images."""
    content: list[dict[str, Any]] = [
        {"type": "text", "text": USER_PROMPT},
    ]
    for i, path in enumerate(image_paths, start=1):
        if len(image_paths) > 1:
            content.append(
                {
                    "type": "text",
                    "text": f"--- Bill page {i} of {len(image_paths)} ---",
                }
            )
        media_type = _media_type_for_path(path)
        b64 = _encode_image_base64(path)
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{b64}",
                    "detail": "high",
                },
            }
        )
    return content


def extract_bill_data(image_paths: Path | list[Path]) -> dict[str, Any]:
    """
    Send bill image(s) to OpenAI Vision and return validated JSON fields.

    Args:
        image_paths: Single image or list of images (multi-page PDF).

    Returns:
        Validated dictionary of extracted field names to values.
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

    api_key = get_openai_api_key()
    model = get_openai_model()

    logger.info(
        "Extracting bill data via OpenAI Vision (%s) — %d image(s)",
        model,
        len(paths),
    )

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_vision_content(paths)},
            ],
            max_tokens=8192,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:
        logger.exception("OpenAI API error")
        raise ValueError(f"OpenAI API error: {exc}") from exc

    raw_content = response.choices[0].message.content
    if not raw_content:
        raise ValueError("OpenAI returned an empty response.")

    raw_data = _parse_json_response(raw_content.strip())
    validated = validate_and_normalize(raw_data)
    return sanitize_for_api(validated)


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Parse JSON from model output, stripping markdown fences if present."""
    text = raw.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
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
    """
    Re-validate user-edited data before Excel generation.

    Accepts raw or partially validated dict from the preview UI.
    """
    validated = validate_and_normalize(data)
    return sanitize_for_api(validated)
