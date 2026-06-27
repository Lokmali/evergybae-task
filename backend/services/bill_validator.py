"""
Post-extraction validation and normalization for MSEDCL electricity bills.

Cleans AI output into Excel-ready values: numeric amounts without symbols,
normalized dates, corrected load vs tariff confusion, and field aliasing.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Values the model returns when a field is absent
_NULL_STRINGS = frozenset(
    {"", "N/A", "n/a", "NA", "NONE", "NULL", "NULL.", "-", "—", "nil", "Nil", "unknown"}
)

# Patterns that indicate a tariff description, NOT a load in kW
_TARIFF_LOAD_FALSE_POSITIVE = re.compile(
    r"/|\bLT\b|\bHT\b|\bPhase\b|\bRes\b|\bComm\b|\bInd\b|Tariff|Category",
    re.IGNORECASE,
)

# Tariff codes on MSEDCL bills (e.g. A50, B21) — short alphanumeric
_TARIFF_CODE_PATTERN = re.compile(r"^[A-Z]\d{1,3}$", re.IGNORECASE)

# Consumer number: typically 10–15 digits
_CONSUMER_NUMBER_PATTERN = re.compile(r"^\d{10,15}$")

# Field name aliases from AI JSON → internal / Excel mapping keys
_FIELD_ALIASES: dict[str, str] = {
    "gst_number": "GST_number",
    "GST_number": "GST_number",
    "GSTIN": "GST_number",
    "consumer_no": "consumer_number",
    "account_number": "consumer_number",
    "sanctioned_load_kw": "sanctioned_load",
    "contract_load_kw": "contract_load",
    "connected_load_kw": "connected_load",
    "total_bill_amount": "bill_amount",
    "total_amount": "bill_amount",
    "energy_consumed": "units_consumed",
    "consumption": "units_consumed",
    "units": "units_consumed",
}

# Canonical scalar fields expected from extraction
CANONICAL_FIELDS = [
    "consumer_name",
    "consumer_number",
    "billing_month",
    "billing_period",
    "bill_date",
    "due_date",
    "address",
    "tariff_category",
    "meter_number",
    "meter_serial_number",
    "division",
    "sub_division",
    "tariff_code",
    "contract_load",
    "connected_load",
    "sanctioned_load",
    "voltage",
    "power_factor",
    "billing_cycle",
    "GST_number",
    "previous_reading",
    "current_reading",
    "units_consumed",
    "bill_amount",
    "fixed_charges",
    "energy_charges",
    "fuel_adjustment",
    "electricity_duty",
    "tax_on_sale",
    "monthly_history",
]


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in _NULL_STRINGS:
        return True
    return False


def _strip_units_and_currency(text: str) -> str:
    """Remove kWh, KW, ₹, Rs. and thousands separators from numeric strings."""
    cleaned = text.strip()
    cleaned = cleaned.replace("₹", "").replace("Rs.", "").replace("rs.", "")
    cleaned = cleaned.replace("INR", "").replace("inr", "")
    cleaned = re.sub(r"\bkWh\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bKW\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bkW\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").strip()
    return cleaned


def parse_numeric(value: Any) -> int | float | None:
    """Parse a numeric field — return int/float without unit symbols."""
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, 4)

    text = _strip_units_and_currency(str(value))
    if not text:
        return None

    try:
        num = float(text)
        return int(num) if num.is_integer() else round(num, 4)
    except ValueError:
        return None


def normalize_date(value: Any) -> str | None:
    """Normalize dates to DD-MM-YYYY string for Excel."""
    if _is_null(value):
        return None

    text = str(value).strip()

    formats = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue

    # Already DD-MM-YYYY-ish
    if re.match(r"^\d{2}-\d{2}-\d{4}$", text):
        return text

    logger.warning("Could not normalize date: %s", text)
    return text


def normalize_billing_cycle(value: Any) -> str | None:
    """
    Format billing cycle paths with spaced slashes.
    2020/TUMSAR SDN/BHANDARA DIVISION → 2020 / TUMSAR SDN / BHANDARA DIVISION
    """
    if _is_null(value):
        return None

    text = str(value).strip()
    if "/" not in text:
        return text

    parts = [p.strip() for p in text.split("/") if p.strip()]
    return " / ".join(parts)


def _is_valid_load_value(value: Any) -> bool:
    """Reject tariff strings mistakenly assigned to load fields."""
    if _is_null(value):
        return False

    text = str(value).strip()
    if _TARIFF_LOAD_FALSE_POSITIVE.search(text):
        return False

    num = parse_numeric(value)
    if num is None:
        return False

    # MSEDCL domestic loads are typically 0.1–500 kW
    return 0.01 <= float(num) <= 500.0


def _normalize_load(value: Any, tariff_category: str | None = None) -> float | int | None:
    """Return numeric kW only if value passes load validation."""
    if not _is_valid_load_value(value):
        if not _is_null(value):
            logger.warning("Rejected invalid load value: %s", value)
        return None

    num = parse_numeric(value)
    if num is None:
        return None

    # Common MSEDCL error: "90" from "90/LT I Res" misread as 0.90 kW
    if float(num) < 1.5 and tariff_category:
        tariff_text = str(tariff_category)
        if re.search(r"\b90\b", tariff_text) and abs(float(num) - 0.9) < 0.05:
            logger.warning(
                "Rejected load %.2f kW — likely misread from tariff '%s'",
                float(num),
                tariff_text,
            )
            return None

    if float(num) < 0.5:
        logger.warning("Rejected load below 0.5 kW: %s", num)
        return None

    return num


def _normalize_tariff_code(value: Any) -> str | None:
    if _is_null(value):
        return None
    text = str(value).strip().upper()
    # Strip accidental load suffix
    text = re.sub(r"\s*KW$", "", text, flags=re.IGNORECASE).strip()
    if _TARIFF_CODE_PATTERN.match(text):
        return text
    # Allow short codes like A50 even if pattern slightly differs
    if len(text) <= 6 and re.match(r"^[A-Z0-9]+$", text):
        return text
    logger.warning("Unexpected tariff_code format: %s", text)
    return text


def _normalize_consumer_number(value: Any) -> str | None:
    if _is_null(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    if _CONSUMER_NUMBER_PATTERN.match(digits):
        return digits
    if len(digits) >= 8:
        logger.warning("Consumer number length unusual (%d digits): %s", len(digits), digits)
        return digits
    logger.warning("Invalid consumer number rejected: %s", value)
    return None


def _normalize_power_factor(value: Any) -> float | None:
    num = parse_numeric(value)
    if num is None:
        return None
    # Percentage form e.g. 98 → 0.98
    if num > 1.0 and num <= 100.0:
        num = round(num / 100.0, 4)
    if 0.0 <= num <= 1.0:
        return num
    logger.warning("Power factor out of range, nulled: %s", value)
    return None


def _normalize_meter_fields(data: dict[str, Any]) -> None:
    """
    Prefer consumer meter number for meter_number; keep serial separately.
    Never use reading numbers as meter numbers.
    """
    serial = data.get("meter_serial_number")
    meter = data.get("meter_number")

    for key in ("meter_number", "meter_serial_number"):
        val = data.get(key)
        if _is_null(val):
            continue
        text = str(val).strip()
        # Reading numbers are usually small integers — not meter IDs
        if key == "meter_number" and re.match(r"^\d{1,4}$", text):
            logger.warning("meter_number looks like a reading number, clearing: %s", text)
            data[key] = None

    if _is_null(data.get("meter_number")) and not _is_null(serial):
        data["meter_number"] = str(serial).strip()

    if not _is_null(serial):
        data["meter_serial_number"] = str(serial).strip()
    if not _is_null(data.get("meter_number")):
        data["meter_number"] = str(data["meter_number"]).strip()


def _resolve_load_fields(data: dict[str, Any]) -> None:
    """Normalize load fields; reject tariff-code confusion."""
    tariff = data.get("tariff_category")
    data["contract_load"] = _normalize_load(data.get("contract_load"), tariff)
    data["connected_load"] = _normalize_load(data.get("connected_load"), tariff)
    data["sanctioned_load"] = _normalize_load(data.get("sanctioned_load"), tariff)


def _normalize_monthly_history(value: Any) -> list[dict[str, Any]] | None:
    if _is_null(value):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, list):
        return None

    history: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        month = entry.get("month") or entry.get("Month")
        units = parse_numeric(entry.get("units") or entry.get("Units"))
        if _is_null(month) or units is None:
            continue
        item: dict[str, Any] = {"month": str(month).strip(), "units": units}
        amount = parse_numeric(entry.get("amount") or entry.get("bill_amount"))
        if amount is not None:
            item["amount"] = amount
        history.append(item)

    return history if history else None


def _apply_aliases(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge aliased keys into canonical field names."""
    merged: dict[str, Any] = {}
    for key, value in raw.items():
        canonical = _FIELD_ALIASES.get(key, key)
        if canonical not in merged or _is_null(merged[canonical]):
            merged[canonical] = value
    return merged


def validate_and_normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Full post-AI validation pipeline.

    Returns a dict with canonical field names and Excel-ready values.
    """
    data = _apply_aliases(raw)

    result: dict[str, Any] = {field: None for field in CANONICAL_FIELDS}

    # Text fields — strip only
    for key in (
        "consumer_name",
        "billing_month",
        "billing_period",
        "address",
        "tariff_category",
        "division",
        "sub_division",
        "voltage",
        "GST_number",
    ):
        val = data.get(key)
        result[key] = None if _is_null(val) else str(val).strip()

    result["consumer_number"] = _normalize_consumer_number(data.get("consumer_number"))
    result["bill_date"] = normalize_date(data.get("bill_date"))
    result["due_date"] = normalize_date(data.get("due_date"))
    result["billing_cycle"] = normalize_billing_cycle(data.get("billing_cycle"))
    result["tariff_code"] = _normalize_tariff_code(data.get("tariff_code"))

    # Meter fields (mutates copy)
    meter_data = {
        "meter_number": data.get("meter_number"),
        "meter_serial_number": data.get("meter_serial_number"),
    }
    _normalize_meter_fields(meter_data)
    result["meter_number"] = meter_data.get("meter_number")
    result["meter_serial_number"] = meter_data.get("meter_serial_number")

    # Load fields with cross-check
    load_data = {
        "contract_load": data.get("contract_load"),
        "connected_load": data.get("connected_load"),
        "sanctioned_load": data.get("sanctioned_load"),
        "tariff_category": data.get("tariff_category"),
    }
    _resolve_load_fields(load_data)
    result["contract_load"] = load_data.get("contract_load")
    result["connected_load"] = load_data.get("connected_load")
    result["sanctioned_load"] = load_data.get("sanctioned_load")
    if not _is_null(load_data.get("tariff_category")) and _is_null(result["tariff_category"]):
        result["tariff_category"] = str(load_data["tariff_category"]).strip()

    result["power_factor"] = _normalize_power_factor(data.get("power_factor"))

    # Numeric readings and charges — store as numbers only
    for key in (
        "previous_reading",
        "current_reading",
        "units_consumed",
        "bill_amount",
        "fixed_charges",
        "energy_charges",
        "fuel_adjustment",
        "electricity_duty",
        "tax_on_sale",
    ):
        num = parse_numeric(data.get(key))
        result[key] = num

    result["monthly_history"] = _normalize_monthly_history(data.get("monthly_history"))

    # Log extraction summary
    filled = [k for k, v in result.items() if v is not None and k != "monthly_history"]
    logger.info("Validated %d scalar fields (+ history)", len(filled))
    for key in filled:
        logger.debug("  %s: %s", key, result[key])
    if result["monthly_history"]:
        logger.info("  monthly_history: %d months", len(result["monthly_history"]))

    return result


def sanitize_for_api(data: dict[str, Any]) -> dict[str, Any]:
    """
    Prepare validated data for JSON API / Excel writer.

    monthly_history stays as a list for preview; Excel writer ignores unmapped fields.
    """
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            sanitized[key] = None
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def sanitize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    """JSON-serialize complex fields for file persistence."""
    out = sanitize_for_api(data)
    if isinstance(out.get("monthly_history"), list):
        # Keep as list for API response — frontend can display
        pass
    return out
