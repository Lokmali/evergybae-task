"""Tests for MSEDCL bill validation and normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.bill_validator import validate_and_normalize


def test_rejects_tariff_confused_as_load():
    raw = {
        "contract_load": "0.90 KW",
        "tariff_category": "90/LT I Res 1-Phase",
        "sanctioned_load": "3.30 KW",
        "tariff_code": "A50",
    }
    result = validate_and_normalize(raw)
    assert result["contract_load"] is None
    assert result["sanctioned_load"] == 3.30
    assert result["tariff_code"] == "A50"


def test_numeric_charges_without_symbols():
    raw = {
        "units_consumed": "25 kWh",
        "bill_amount": "₹1460.00",
        "previous_reading": "33674",
        "current_reading": "33699",
    }
    result = validate_and_normalize(raw)
    assert result["units_consumed"] == 25
    assert result["bill_amount"] == 1460
    assert result["previous_reading"] == 33674
    assert result["current_reading"] == 33699


def test_billing_cycle_formatting():
    raw = {"billing_cycle": "2020/TUMSAR SDN/BHANDARA DIVISION"}
    result = validate_and_normalize(raw)
    assert result["billing_cycle"] == "2020 / TUMSAR SDN / BHANDARA DIVISION"


def test_division_and_subdivision():
    raw = {
        "division": "BHANDARA DIVISION",
        "sub_division": "TUMSAR SDN",
    }
    result = validate_and_normalize(raw)
    assert result["division"] == "BHANDARA DIVISION"
    assert result["sub_division"] == "TUMSAR SDN"


def test_monthly_history():
    raw = {
        "monthly_history": [
            {"month": "February 2025", "units": 99},
            {"month": "January 2026", "units": 25, "amount": 1460},
        ]
    }
    result = validate_and_normalize(raw)
    assert len(result["monthly_history"]) == 2
    assert result["monthly_history"][0]["units"] == 99
    assert result["monthly_history"][1]["amount"] == 1460


def test_gst_alias():
    raw = {"gst_number": "27AABCU9603R1ZM"}
    result = validate_and_normalize(raw)
    assert result["GST_number"] == "27AABCU9603R1ZM"


if __name__ == "__main__":
    test_rejects_tariff_confused_as_load()
    test_numeric_charges_without_symbols()
    test_billing_cycle_formatting()
    test_division_and_subdivision()
    test_monthly_history()
    test_gst_alias()
    print("All validation tests passed.")
