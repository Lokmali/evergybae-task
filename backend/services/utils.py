"""
Shared utilities for bill extraction, validation, and Excel output.
"""

from __future__ import annotations

import re
from typing import Any

# Shown in preview / Excel when a field is genuinely absent
NOT_AVAILABLE = "Not Available"

_NULL_STRINGS = frozenset(
    {"", "N/A", "n/a", "NA", "NONE", "NULL", "NULL.", "-", "—", "nil", "Nil", "unknown", "not available"}
)


def is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {s.lower() for s in _NULL_STRINGS}:
        return True
    return False


def strip_units_and_currency(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("₹", "").replace("Rs.", "").replace("rs.", "")
    cleaned = cleaned.replace("INR", "").replace("inr", "")
    cleaned = re.sub(r"\bkWh\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bKW\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bkW\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").strip()
    return cleaned


def parse_numeric(value: Any) -> int | float | None:
    """Parse numeric fields — strip ₹, commas, kWh; return int/float."""
    if is_null(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, 4)

    text = strip_units_and_currency(str(value))
    if not text:
        return None
    try:
        num = float(text)
        return int(num) if num.is_integer() else round(num, 4)
    except ValueError:
        return None


# Priority order for bill amount — FINAL payable beats earlier balances/charges.
# Lower rank = higher priority. Code picks the highest-priority non-null amount.
BILL_AMOUNT_PRIORITY: list[tuple[str, int]] = [
    ("final_amount_payable", 1),
    ("amount_payable", 2),
    ("net_amount", 3),
    ("final_amount", 4),
    ("total_amount_payable", 5),
    ("current_bill_amount", 6),
    ("total_amount_due", 7),
    ("amount_before_due_date", 8),
    ("bill_amount", 9),
    ("total_bill_amount", 10),
    ("total_amount", 11),
    # Deliberately LOW priority — often not the amount customer pays this cycle
    ("amount_after_due_date", 20),
    ("previous_balance", 25),
    ("current_bill", 15),
]


def resolve_bill_amount(raw: dict[str, Any]) -> tuple[int | float | None, str | None]:
    """
    Choose the final payable bill amount from multiple OCR/AI amount fields.

    Returns (amount, source_key) so callers can log why a value was chosen.
    """
    candidates: list[tuple[int, str, int | float]] = []

    for key, rank in BILL_AMOUNT_PRIORITY:
        val = parse_numeric(raw.get(key))
        if val is not None and val >= 0:
            candidates.append((rank, key, val))

    # Also scan keys containing payable/net/final in name
    for key, value in raw.items():
        if key in {c[1] for c in candidates}:
            continue
        kl = key.lower()
        if any(w in kl for w in ("payable", "net_amount", "final")) and "balance" not in kl:
            val = parse_numeric(value)
            if val is not None:
                candidates.append((12, key, val))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0])
    rank, source_key, amount = candidates[0]
    return amount, source_key


def confidence_label_to_percent(label: str) -> int:
    """Map internal confidence labels to display percentages."""
    return {
        "high": 98,
        "corrected": 92,
        "medium": 75,
        "low": 52,
        "missing": 0,
        "not_found": 0,
    }.get(label, 85)


def build_solar_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Compute solar assessment summary from extracted bill data."""
    units = data.get("units_consumed")
    bill = data.get("bill_amount")
    if isinstance(units, str):
        units = parse_numeric(units)
    if isinstance(bill, str):
        bill = parse_numeric(bill)

    units = float(units) if units is not None else None
    bill = float(bill) if bill is not None else None

    capacity = round(units / 120, 2) if units else None
    annual_savings = round(bill * 12, 0) if bill else None
    payback = None
    if capacity and annual_savings and annual_savings > 0:
        payback = round((capacity * 50000) / annual_savings, 1)

    return {
        "monthly_consumption_kwh": units,
        "recommended_solar_capacity_kw": capacity,
        "estimated_annual_savings_inr": annual_savings,
        "estimated_payback_years": payback,
    }
