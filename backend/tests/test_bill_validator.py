"""Tests for MSEDCL bill validation and normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.bill_validator import validate_and_normalize


def test_rejects_tariff_confused_as_load():
    raw = {
        "contract_load_kw": "0.90 KW",
        "tariff_category": "90/LT I Res 1-Phase",
        "sanctioned_load_kw": "3.30 KW",
        "tariff_code": "A50",
    }
    result = validate_and_normalize(raw)
    # Invalid 0.90 kW rejected; sanctioned 3.30 kW propagated to contract/connected
    assert result["contract_load"] == 3.30
    assert result["sanctioned_load"] == 3.30
    assert result["connected_load"] == 3.30
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


def test_readings_preserve_bill_labels_no_swap():
    """Previous/Current labels from bill must not be swapped by validator."""
    raw = {
        "previous_reading": 18292,
        "current_reading": 18429,
        "units_consumed": 137,
    }
    result = validate_and_normalize(raw)
    assert result["previous_reading"] == 18292
    assert result["current_reading"] == 18429
    confidence = result.get("_field_confidence", {})
    assert confidence.get("units_consumed") == 98


def test_readings_mismatch_keeps_labels():
    raw = {
        "previous_reading": 33674,
        "current_reading": 33699,
        "units_consumed": 99,
    }
    result = validate_and_normalize(raw)
    assert result["previous_reading"] == 33674
    assert result["current_reading"] == 33699
    confidence = result.get("_field_confidence", {})
    assert confidence.get("units_consumed") == 52


def test_units_mismatch_flags_low_confidence():
    raw = {
        "previous_reading": 33674,
        "current_reading": 33699,
        "units_consumed": 99,
    }
    result = validate_and_normalize(raw)
    confidence = result.get("_field_confidence", {})
    assert confidence.get("units_consumed") == 52


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
    assert result["sub_division"] == "TUMSAR S/DN"


def test_monthly_history_with_bill_amount():
    raw = {
        "monthly_history": [
            {"month": "February 2025", "units": 99, "bill_amount": None},
            {"month": "January 2026", "units": 25, "bill_amount": 1460},
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


def test_consumer_number_digits_only():
    raw = {"consumer_number": "12345-67890-12"}
    result = validate_and_normalize(raw)
    assert result["consumer_number"] == "123456789012"


def test_strip_internal_metadata():
    from services.bill_validator import strip_internal_metadata

    data = {"consumer_name": "Test", "_field_confidence": {"units_consumed": 52}}
    cleaned = strip_internal_metadata(data)
    assert "_field_confidence" not in cleaned
    assert cleaned["consumer_name"] == "Test"


def test_bill_amount_priority_final_payable():
    raw = {
        "previous_balance": 5000,
        "bill_amount": 5000,
        "final_amount_payable": 3450,
    }
    result = validate_and_normalize(raw)
    assert result["bill_amount"] == 3450


def test_bill_amount_prefers_amount_payable_over_previous_balance():
    raw = {
        "previous_balance": 12000,
        "amount_payable": 18429,
        "current_bill_amount": 15000,
    }
    result = validate_and_normalize(raw)
    assert result["bill_amount"] == 18429


def test_load_propagation_single_value():
    raw = {"contract_load_kw": 1.0}
    result = validate_and_normalize(raw)
    assert result["contract_load"] == 1.0
    assert result["connected_load"] == 1.0
    assert result["sanctioned_load"] == 1.0


def test_billing_period_uses_reading_dates():
    raw = {
        "billing_period": "1.00 Month",
        "previous_reading_date": "06-12-2025",
        "current_reading_date": "05-01-2026",
    }
    result = validate_and_normalize(raw)
    assert result["billing_period"] == "06-12-2025 to 05-01-2026"


def test_billing_period_ignores_bill_due_dates():
    raw = {
        "billing_period": "1.00 Month",
        "bill_date": "10-01-2026",
        "due_date": "30-01-2026",
        "billing_period_start": "10-01-2026",
        "billing_period_end": "30-01-2026",
    }
    result = validate_and_normalize(raw)
    assert result["billing_period"] == "1.00 Month"


def test_billing_period_duration_only():
    result = validate_and_normalize({"billing_period": "1 Month"})
    assert result["billing_period"] == "1.00 Month"


def test_address_formatting():
    raw = {"address": "241/1SHIVAJI NAGAR441912"}
    result = validate_and_normalize(raw)
    assert result["address"] == "241/1 SHIVAJI NAGAR, 441912"


def test_power_factor_rejects_billing_month():
    raw = {
        "power_factor": "1.00 Month",
        "billing_period": "1.00 Month",
        "billing_cycle": "1.00 Month",
    }
    result = validate_and_normalize(raw)
    assert result["power_factor"] == "Not Available"


def test_load_and_fixed_charges_not_available():
    result = validate_and_normalize({})
    assert result["contract_load"] == "Not Available"
    assert result["fixed_charges"] == "Not Available"
    assert result["voltage"] == "Not Available"


def test_solar_summary_generated():
    raw = {"units_consumed": 137, "bill_amount": 3450}
    result = validate_and_normalize(raw)
    summary = result.get("_solar_summary", {})
    assert summary["monthly_consumption_kwh"] == 137
    assert summary["recommended_solar_capacity_kw"] == 1.14
    assert summary["estimated_annual_savings_inr"] == 41400


def test_billing_cycle_rejects_consumer_number():
    raw = {
        "consumer_number": "123456789012",
        "billing_cycle": "123456789012",
    }
    result = validate_and_normalize(raw)
    assert result["consumer_number"] == "123456789012"
    assert result["billing_cycle"] is None


def test_billing_cycle_monthly_normalized():
    result = validate_and_normalize({"billing_cycle": "Monthly"})
    assert result["billing_cycle"] == "1.00 Month"


def test_billing_period_duration():
    result = validate_and_normalize({"billing_period": "1 Month"})
    assert result["billing_period"] == "1.00 Month"


def test_division_adds_division_suffix():
    result = validate_and_normalize({"division": "BHANDARA"})
    assert result["division"] == "BHANDARA DIVISION"


def test_reading_ocr_correction_via_units():
    # OCR misread 18429 as 16429 (6 vs 8); units cross-check fixes it
    raw = {
        "previous_reading": 16429,
        "current_reading": 18566,
        "units_consumed": 137,
    }
    result = validate_and_normalize(raw)
    assert result["previous_reading"] == 18429
    assert result["current_reading"] == 18566
    assert result["_field_confidence"]["previous_reading"] == 92


def test_harvest_load_from_text():
    raw = {
        "tariff_category": "Contract Load 1.00 KW, 90/LT I Res 1-Phase",
    }
    result = validate_and_normalize(raw)
    assert result["contract_load"] == 1.0
    assert result["connected_load"] == 1.0
    assert result["sanctioned_load"] == 1.0


if __name__ == "__main__":
    test_rejects_tariff_confused_as_load()
    test_numeric_charges_without_symbols()
    test_readings_preserve_bill_labels_no_swap()
    test_readings_mismatch_keeps_labels()
    test_units_mismatch_flags_low_confidence()
    test_billing_cycle_formatting()
    test_division_and_subdivision()
    test_monthly_history_with_bill_amount()
    test_gst_alias()
    test_consumer_number_digits_only()
    test_strip_internal_metadata()
    test_bill_amount_priority_final_payable()
    test_bill_amount_prefers_amount_payable_over_previous_balance()
    test_load_propagation_single_value()
    test_load_and_fixed_charges_not_available()
    test_solar_summary_generated()
    test_billing_cycle_rejects_consumer_number()
    test_billing_cycle_monthly_normalized()
    test_billing_period_duration()
    test_division_adds_division_suffix()
    test_reading_ocr_correction_via_units()
    test_harvest_load_from_text()
    test_billing_period_uses_reading_dates()
    test_billing_period_ignores_bill_due_dates()
    test_billing_period_duration_only()
    test_address_formatting()
    test_power_factor_rejects_billing_month()
    print("All validation tests passed.")
