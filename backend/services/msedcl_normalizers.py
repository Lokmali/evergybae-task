"""
MSEDCL-specific field normalization and OCR correction helpers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.utils import is_null, parse_numeric

logger = logging.getLogger(__name__)

# Consumer number pattern — used to reject false positives in billing_cycle
_CONSUMER_NUMBER_PATTERN = re.compile(r"^\d{10,15}$")

# Common OCR digit confusions on meter readings (8↔6, 1↔7, etc.)
_OCR_DIGIT_PAIRS = frozenset(
    {("0", "8"), ("8", "0"), ("1", "7"), ("7", "1"), ("3", "8"), ("8", "3"),
     ("5", "6"), ("6", "5"), ("6", "8"), ("8", "6"), ("1", "4"), ("4", "1")}
)

_BILLING_PERIOD_DURATION = re.compile(r"^(\d+(?:\.\d+)?)\s*Month", re.IGNORECASE)
_BILLING_PERIOD_RANGE = re.compile(
    r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\s*(?:to|TO|-)\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
)

# Regex fallback: find kW load values in text blobs when Vision misses structured fields
_LOAD_LABEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"contract(?:ed)?\s*load", re.I), "contract_load"),
    (re.compile(r"connected\s*load", re.I), "connected_load"),
    (re.compile(r"sanction(?:ed|ion)\s*load|approved\s*load|मंजूर\s*भार", re.I), "sanctioned_load"),
]
_LOAD_KW_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*k?w\b", re.I)


def is_consumer_number_like(value: Any) -> bool:
    """True when value is (or normalizes to) a MSEDCL consumer/account number."""
    if is_null(value):
        return False
    digits = re.sub(r"\D", "", str(value))
    return bool(_CONSUMER_NUMBER_PATTERN.match(digits))


def _matches_bill_and_due_dates(start_val: Any, end_val: Any, raw: dict[str, Any]) -> bool:
    """True when a date range is just bill issue date + payment due date (not billing period)."""
    from services.bill_validator import normalize_date

    bd = normalize_date(raw.get("bill_date"))
    dd = normalize_date(raw.get("due_date"))
    ds = normalize_date(start_val)
    de = normalize_date(end_val)
    if not bd or not dd or not ds or not de:
        return False
    return ds == bd and de == dd


def normalize_billing_period(value: Any, raw: dict[str, Any] | None = None) -> str | None:
    """
    Normalize MSEDCL billing period.

    Valid outputs: '1.00 Month' (duration) OR meter reading date range
    (previous reading date → current reading date).

    Never uses bill_date / due_date — those are invoice dates, not billing period.
    """
    raw = raw or {}

    def _date_range(start_val: Any, end_val: Any) -> str | None:
        if is_null(start_val) or is_null(end_val):
            return None
        from services.bill_validator import normalize_date

        ds = normalize_date(start_val)
        de = normalize_date(end_val)
        if ds and de:
            return f"{ds} to {de}"
        return None

    # 1. Meter reading dates (correct MSEDCL billing period range)
    reading_range = _date_range(
        raw.get("previous_reading_date") or raw.get("meter_reading_date_previous"),
        raw.get("current_reading_date") or raw.get("meter_reading_date_current"),
    )
    if reading_range:
        return reading_range

    # 2. Explicit billing_period_start/end — reject if same as bill + due dates
    period_start = raw.get("billing_period_start") or raw.get("period_from")
    period_end = raw.get("billing_period_end") or raw.get("period_to")
    if not is_null(period_start) and not is_null(period_end):
        if not _matches_bill_and_due_dates(period_start, period_end, raw):
            ranged = _date_range(period_start, period_end)
            if ranged:
                return ranged

    # 3. Duration from billing_period field ("1.00 Month")
    if not is_null(value):
        text = str(value).strip()

        duration = _BILLING_PERIOD_DURATION.match(text)
        if duration:
            return f"{float(duration.group(1)):.2f} Month"

        if re.search(r"\bmonthly\b", text, re.I):
            return "1.00 Month"

        # Date range in text — only if not bill/due contamination
        range_match = _BILLING_PERIOD_RANGE.search(text)
        if range_match:
            if not _matches_bill_and_due_dates(range_match.group(1), range_match.group(2), raw):
                ranged = _date_range(range_match.group(1), range_match.group(2))
                if ranged:
                    return ranged

        # Plain duration text without regex match
        if re.match(r"^\d+(?:\.\d+)?\s*month", text, re.I):
            num = float(re.match(r"^(\d+(?:\.\d+)?)", text).group(1))
            return f"{num:.2f} Month"

    return None


def normalize_address(value: Any) -> str | None:
    """
    Format jammed OCR addresses: 241/1SHIVAJI NAGAR441912 → 241/1 SHIVAJI NAGAR, 441912
    """
    if is_null(value):
        return None

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    # Insert space between digit/slash run and following uppercase letter (241/1SHIVAJI)
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
    # Insert comma before 6-digit PIN at end (441912)
    if re.search(r"\d{6}$", text) and not re.search(r",\s*\d{6}$", text):
        if re.search(r"[A-Za-z]\d{6}$", text):
            text = re.sub(r"([A-Za-z])(\d{6})$", r"\1, \2", text)
        else:
            text = re.sub(r"(\s)(\d{6})$", r", \2", text)

    return re.sub(r"\s+", " ", text).strip()


def normalize_billing_cycle(value: Any, consumer_number: str | None = None) -> str | None:
    """
    Normalize billing cycle frequency/path; reject consumer numbers mis-assigned here.

    MSEDCL 'Billing Cycle' is typically Monthly / 1 Month / 1.00 Month — NOT consumer number.
    Some bills also show an org route with slashes (year/sub-division/division).
    """
    if is_null(value):
        return None

    text = str(value).strip()

    if is_consumer_number_like(text):
        logger.warning("billing_cycle rejected — matches consumer number: %s", text)
        return None

    if consumer_number and re.sub(r"\D", "", text) == consumer_number:
        logger.warning("billing_cycle rejected — duplicate of consumer_number")
        return None

    # Pure long digit string without slashes — not a valid cycle
    digits_only = re.sub(r"\D", "", text)
    if len(digits_only) >= 10 and "/" not in text:
        logger.warning("billing_cycle rejected — looks like account number: %s", text)
        return None

    lower = text.lower()
    if lower in ("monthly", "month", "1 month"):
        return "1.00 Month"
    if re.match(r"^\d+(?:\.\d+)?\s*month", lower):
        num = float(re.match(r"^(\d+(?:\.\d+)?)", text).group(1))
        return f"{num:.2f} Month"

    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        return " / ".join(parts)

    return text


def normalize_division(value: Any) -> str | None:
    """Ensure full MSEDCL division name e.g. BHANDARA DIVISION."""
    if is_null(value):
        return None

    text = str(value).strip().upper()
    text = re.sub(r"\s+", " ", text)

    if "DIVISION" not in text:
        text = f"{text} DIVISION"

    return text


def normalize_sub_division(value: Any) -> str | None:
    """Normalize sub-division e.g. TUMSAR SDN → TUMSAR S/DN."""
    if is_null(value):
        return None

    text = str(value).strip().upper()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bS/DN\b", "S/DN", text)
    text = re.sub(r"\bSDN\b", "S/DN", text)
    text = re.sub(r"\bS\s+DN\b", "S/DN", text)
    text = re.sub(r"\bSUB\s*DIV(?:ISION)?\b", "S/DN", text)

    if "S/DN" not in text and len(text.split()) <= 2:
        text = f"{text} S/DN"

    return text


def _digits_differ_by_one_ocr_error(actual: int, expected: int) -> bool:
    """True when two integers differ by exactly one OCR-confusable digit."""
    sa, sb = str(actual), str(expected)
    if len(sa) != len(sb):
        return False
    diffs = [(a, b) for a, b in zip(sa, sb, strict=True) if a != b]
    if len(diffs) != 1:
        return False
    pair = diffs[0]
    return pair in _OCR_DIGIT_PAIRS or (pair[1], pair[0]) in _OCR_DIGIT_PAIRS


def correct_meter_readings(result: dict[str, Any]) -> dict[str, str]:
    """
    Validate readings against units WITHOUT swapping Previous/Current labels.

    MSEDCL bills label "Previous Reading" and "Current Reading" explicitly — preserve
    those assignments even when previous > current (meter reset). Only fix single-digit
    OCR errors on the labeled field when units cross-check supports it.
    """
    confidence: dict[str, str] = {}
    prev = result.get("previous_reading")
    curr = result.get("current_reading")
    units = result.get("units_consumed")

    if not all(isinstance(v, (int, float)) for v in (prev, curr, units) if v is not None):
        return confidence
    if prev is None or curr is None or units is None:
        return confidence

    prev_i, curr_i, units_i = int(prev), int(curr), int(units)

    # Match bill labels: consumption = |current − previous| or current − previous
    diff_forward = curr_i - prev_i
    diff_reverse = prev_i - curr_i

    if diff_forward == units_i or diff_reverse == units_i:
        confidence["units_consumed"] = "high"
        confidence["previous_reading"] = "high"
        confidence["current_reading"] = "high"
        return confidence

    # OCR fix on PREVIOUS label only (e.g. 16429 → 18429 when current − units says so)
    expected_prev = curr_i - units_i
    if expected_prev >= 0 and expected_prev != prev_i:
        if _digits_differ_by_one_ocr_error(prev_i, expected_prev):
            logger.info(
                "Corrected previous reading (label preserved) %s → %s",
                prev_i,
                expected_prev,
            )
            result["previous_reading"] = expected_prev
            confidence["previous_reading"] = "corrected"
            confidence["current_reading"] = "high"
            confidence["units_consumed"] = "high"
            return confidence

    # OCR fix on CURRENT label only
    expected_curr = prev_i + units_i
    if expected_curr != curr_i and _digits_differ_by_one_ocr_error(curr_i, expected_curr):
        logger.info(
            "Corrected current reading (label preserved) %s → %s",
            curr_i,
            expected_curr,
        )
        result["current_reading"] = expected_curr
        confidence["current_reading"] = "corrected"
        confidence["previous_reading"] = "high"
        confidence["units_consumed"] = "high"
        return confidence

    confidence["units_consumed"] = "low"
    confidence["previous_reading"] = "low"
    confidence["current_reading"] = "low"
    logger.warning(
        "Units mismatch (labels kept): previous=%s, current=%s, units=%s",
        prev_i,
        curr_i,
        units_i,
    )
    return confidence


def harvest_load_values_from_raw(raw: dict[str, Any]) -> dict[str, float]:
    """
    Regex fallback: extract kW loads from text fields when structured keys are missing.
    """
    found: dict[str, float] = {}

    for _key, value in raw.items():
        if is_null(value):
            continue
        text = str(value)

        for label_re, field_name in _LOAD_LABEL_PATTERNS:
            if field_name in found:
                continue
            label_match = label_re.search(text)
            if not label_match:
                continue
            # Search for kW value after the label (within ~40 chars)
            snippet = text[label_match.start() : label_match.start() + 60]
            kw_match = _LOAD_KW_VALUE.search(snippet)
            if kw_match:
                num = float(kw_match.group(1))
                if 0.01 <= num <= 500:
                    found[field_name] = num

        # Generic "Load : 1.00 KW" on same line
        generic = re.search(
            r"(?:load|भार)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*k?w",
            text,
            re.I,
        )
        if generic and "contract_load" not in found:
            num = float(generic.group(1))
            if 0.01 <= num <= 500:
                found["contract_load"] = num

    return found
