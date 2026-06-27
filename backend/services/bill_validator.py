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

from services.msedcl_normalizers import (
    correct_meter_readings,
    harvest_load_values_from_raw,
    normalize_address,
    normalize_billing_cycle,
    normalize_billing_period,
    normalize_division,
    normalize_sub_division,
)
from services.utils import (
    NOT_AVAILABLE,
    build_solar_summary,
    confidence_label_to_percent,
    is_null,
    parse_numeric,
    resolve_bill_amount,
)

logger = logging.getLogger(__name__)

# Re-export for callers that import from bill_validator
__all__ = [
    "CANONICAL_FIELDS",
    "NOT_AVAILABLE",
    "parse_numeric",
    "sanitize_for_api",
    "sanitize_for_storage",
    "strip_internal_metadata",
    "validate_and_normalize",
]

LOAD_FIELDS = ("contract_load", "connected_load", "sanctioned_load")

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
    "consumer_id": "consumer_number",
    "consumer_address": "address",
    "service_address": "address",
    "name": "consumer_name",
    "consumer": "consumer_name",
    # Amount aliases — final payable is resolved separately via resolve_bill_amount()
    "payable_amount": "bill_amount",
    "fixed_charge": "fixed_charges",
    "energy_charge": "energy_charges",
    "fac": "fuel_adjustment",
    "fca": "fuel_adjustment",
    "duty": "electricity_duty",
    "reading_group": "tariff_code",
    "load_kw": "contract_load",
    "contracted_load": "contract_load",
    "approved_load": "sanctioned_load",
    "sanctioned_load_kw": "sanctioned_load",
    "contract_load_kw": "contract_load",
    "connected_load_kw": "connected_load",
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


def normalize_date(value: Any) -> str | None:
    """Normalize dates to DD-MM-YYYY string for Excel."""
    if is_null(value):
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


def _is_valid_load_value(value: Any) -> bool:
    """Reject tariff strings mistakenly assigned to load fields."""
    if is_null(value):
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
        if not is_null(value):
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
    if is_null(value):
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
    if is_null(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    if _CONSUMER_NUMBER_PATTERN.match(digits):
        return digits
    if len(digits) >= 8:
        logger.warning("Consumer number length unusual (%d digits): %s", len(digits), digits)
        return digits
    logger.warning("Invalid consumer number rejected: %s", value)
    return None


def _normalize_power_factor(value: Any, raw: dict[str, Any] | None = None) -> float | str | None:
    """Return power factor 0–1 only; reject billing-period text mis-assigned to this field."""
    raw = raw or {}

    if is_null(value):
        return None

    text = str(value).strip()
    if re.search(r"\bmonth\b", text, re.I):
        logger.warning("power_factor rejected — looks like billing period: %s", text)
        return None

    # Reject if identical to billing cycle / period strings (common AI mix-up)
    for other_key in ("billing_cycle", "billing_period"):
        other = raw.get(other_key)
        if not is_null(other) and str(other).strip().lower() == text.lower():
            logger.warning("power_factor rejected — duplicate of %s", other_key)
            return None

    num = parse_numeric(value)
    if num is None:
        return None

    # Percentage form e.g. 98 → 0.98
    if num > 1.0 and num <= 100.0:
        num = round(num / 100.0, 4)

    if 0.0 <= num <= 1.0:
        # 1.0 exactly often means misread "1.00 Month" — reject unless no billing month text
        if num == 1.0:
            bp = str(raw.get("billing_period") or raw.get("billing_cycle") or "")
            if re.search(r"\bmonth\b", bp, re.I) or bp.strip() in ("1.00 Month", "1 Month", "Monthly"):
                logger.warning("power_factor 1.0 rejected — likely billing duration mix-up")
                return None
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
        if is_null(val):
            continue
        text = str(val).strip()
        # Pure small integers are meter readings, not meter IDs — unless alphanumeric
        if key == "meter_number" and re.match(r"^\d{1,4}$", text):
            logger.warning("meter_number looks like a reading number, clearing: %s", text)
            data[key] = None

    if is_null(data.get("meter_number")) and not is_null(serial):
        data["meter_number"] = str(serial).strip()

    if not is_null(serial):
        data["meter_serial_number"] = str(serial).strip()
    if not is_null(data.get("meter_number")):
        data["meter_number"] = str(data["meter_number"]).strip()


def _resolve_load_fields(data: dict[str, Any]) -> None:
    """Normalize load fields; reject tariff-code confusion."""
    tariff = data.get("tariff_category")
    data["contract_load"] = _normalize_load(data.get("contract_load"), tariff)
    data["connected_load"] = _normalize_load(data.get("connected_load"), tariff)
    data["sanctioned_load"] = _normalize_load(data.get("sanctioned_load"), tariff)


def _propagate_load_values(result: dict[str, Any]) -> None:
    """
    If only one load type exists on the bill, copy it to the other load fields.

    MSEDCL bills may label load as Contract, Connected, or Sanctioned — often only one appears.
    """
    numeric_loads = [
        result[k] for k in LOAD_FIELDS
        if result.get(k) is not None and isinstance(result[k], (int, float))
    ]
    unique = set(numeric_loads)
    if len(unique) == 1:
        single = numeric_loads[0]
        for key in LOAD_FIELDS:
            if result.get(key) is None:
                result[key] = single
                logger.info("Propagated load %.2f kW to %s", float(single), key)

    for key in LOAD_FIELDS:
        if result.get(key) is None:
            result[key] = NOT_AVAILABLE


def _apply_missing_field_defaults(result: dict[str, Any]) -> None:
    """Use 'Not Available' for optional fields absent on the bill."""
    na_fields = (
        "fixed_charges",
        "voltage",
        "power_factor",
        "fuel_adjustment",
        "electricity_duty",
        "tax_on_sale",
    )
    for key in na_fields:
        if result.get(key) is None:
            result[key] = NOT_AVAILABLE


def _build_confidence_percentages(
    result: dict[str, Any],
    label_confidence: dict[str, str],
    bill_source: str | None,
) -> dict[str, int]:
    """Convert internal labels + extraction certainty into 0–100 display scores."""
    scores: dict[str, int] = {}

    for field in CANONICAL_FIELDS:
        if field == "monthly_history":
            continue

        val = result.get(field)
        if field in label_confidence:
            scores[field] = confidence_label_to_percent(label_confidence[field])
        elif val == NOT_AVAILABLE or val is None:
            scores[field] = 0
        elif field == "bill_amount" and bill_source:
            # Higher confidence when chosen from an explicit payable label
            if any(w in bill_source for w in ("payable", "final", "net")):
                scores[field] = 98
            else:
                scores[field] = 88
        elif isinstance(val, (int, float)):
            scores[field] = 96
        else:
            scores[field] = 94

    return scores


def _normalize_monthly_history(value: Any) -> list[dict[str, Any]] | None:
    if is_null(value):
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
        if is_null(month) or units is None:
            continue
        item: dict[str, Any] = {"month": str(month).strip(), "units": units}
        amount = parse_numeric(
            entry.get("bill_amount") or entry.get("amount") or entry.get("Amount")
        )
        if amount is not None:
            item["amount"] = amount
        history.append(item)

    return history if history else None


def _validate_readings_and_units(result: dict[str, Any]) -> dict[str, str]:
    """Delegate to MSEDCL reading correction (swap + OCR digit fix via units)."""
    return correct_meter_readings(result)


def _apply_aliases(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge aliased keys into canonical field names."""
    merged: dict[str, Any] = {}
    for key, value in raw.items():
        canonical = _FIELD_ALIASES.get(key, key)
        if canonical not in merged or is_null(merged[canonical]):
            merged[canonical] = value
    return merged


def validate_and_normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Full post-AI validation pipeline.

    Returns a dict with canonical field names and Excel-ready values.
    """
    # Bill amount: pick final payable over previous balance / intermediate totals
    resolved_amount, bill_source = resolve_bill_amount(raw)
    if resolved_amount is not None:
        logger.info(
            "Bill amount %s chosen from '%s' (priority over other amounts on bill)",
            resolved_amount,
            bill_source,
        )

    data = _apply_aliases(raw)
    if resolved_amount is not None:
        data["bill_amount"] = resolved_amount

    # Regex fallback for load kW values embedded in text fields
    for field, kw_val in harvest_load_values_from_raw({**raw, **data}).items():
        if is_null(data.get(field)) and is_null(data.get(f"{field}_kw")):
            data[field] = kw_val
            logger.info("Harvested %s = %.2f kW from bill text", field, kw_val)

    result: dict[str, Any] = {field: None for field in CANONICAL_FIELDS}

    # Text fields — strip only
    for key in (
        "consumer_name",
        "billing_month",
        "tariff_category",
        "GST_number",
    ):
        val = data.get(key)
        result[key] = None if is_null(val) else str(val).strip()

    result["address"] = normalize_address(data.get("address"))
    result["billing_period"] = normalize_billing_period(data.get("billing_period"), data)
    result["division"] = normalize_division(data.get("division"))
    result["sub_division"] = normalize_sub_division(data.get("sub_division"))

    result["consumer_number"] = _normalize_consumer_number(data.get("consumer_number"))
    result["bill_date"] = normalize_date(data.get("bill_date"))
    result["due_date"] = normalize_date(data.get("due_date"))
    result["billing_cycle"] = normalize_billing_cycle(
        data.get("billing_cycle"), result["consumer_number"]
    )
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
    if not is_null(load_data.get("tariff_category")) and is_null(result["tariff_category"]):
        result["tariff_category"] = str(load_data["tariff_category"]).strip()

    _propagate_load_values(result)

    result["voltage"] = None if is_null(data.get("voltage")) else str(data.get("voltage")).strip()
    result["power_factor"] = _normalize_power_factor(data.get("power_factor"), data)

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

    _apply_missing_field_defaults(result)

    result["monthly_history"] = _normalize_monthly_history(data.get("monthly_history"))

    # Cross-validate meter readings and units consumed
    reading_confidence = _validate_readings_and_units(result)

    # Build field confidence map for API (frontend may use for highlighting)
    label_confidence: dict[str, str] = dict(reading_confidence)
    if result["consumer_number"] is None and not is_null(data.get("consumer_number")):
        label_confidence["consumer_number"] = "low"
    for load_key in LOAD_FIELDS:
        if not is_null(data.get(load_key)) and result.get(load_key) == NOT_AVAILABLE:
            label_confidence[load_key] = "low"
        elif result.get(load_key) == NOT_AVAILABLE:
            label_confidence[load_key] = "not_found"
    if result.get("fixed_charges") == NOT_AVAILABLE:
        label_confidence["fixed_charges"] = "not_found"
    for na_key in ("voltage", "power_factor", "fuel_adjustment", "electricity_duty", "tax_on_sale"):
        if result.get(na_key) == NOT_AVAILABLE:
            label_confidence[na_key] = "not_found"
    if result.get("bill_amount") is None:
        label_confidence["bill_amount"] = "not_found"
    if result.get("billing_cycle") is None and not is_null(data.get("billing_cycle")):
        label_confidence["billing_cycle"] = "low"

    result["_field_confidence"] = _build_confidence_percentages(
        result, label_confidence, bill_source
    )
    result["_solar_summary"] = build_solar_summary(result)
    if bill_source:
        result["_bill_amount_source"] = bill_source

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
    Keys prefixed with _ are metadata (e.g. _field_confidence) — not written to Excel.
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


def strip_internal_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """Remove _prefixed metadata keys before Excel generation."""
    return {k: v for k, v in data.items() if not k.startswith("_")}


def sanitize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    """JSON-serialize complex fields for file persistence."""
    out = sanitize_for_api(data)
    if isinstance(out.get("monthly_history"), list):
        # Keep as list for API response — frontend can display
        pass
    return out
