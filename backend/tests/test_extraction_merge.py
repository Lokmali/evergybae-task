"""Tests for extraction merge and image preprocessing helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ai_extractor import merge_extraction_results, _count_missing_priority


def test_merge_fills_gaps():
    primary = {"consumer_name": "Test", "consumer_number": None, "monthly_history": []}
    secondary = {
        "consumer_name": "Wrong",
        "consumer_number": "123456789012",
        "monthly_history": [{"month": "Jan 2025", "units": 100, "bill_amount": None}],
    }
    merged = merge_extraction_results(primary, secondary)
    assert merged["consumer_name"] == "Test"  # keep primary when filled
    assert merged["consumer_number"] == "123456789012"
    assert len(merged["monthly_history"]) == 1


def test_merge_monthly_history_dedupes():
    primary = {"monthly_history": [{"month": "Feb 2025", "units": 99, "bill_amount": None}]}
    secondary = {
        "monthly_history": [
            {"month": "Feb 2025", "units": 99, "bill_amount": 1400},
            {"month": "Mar 2025", "units": 151, "bill_amount": None},
        ]
    }
    merged = merge_extraction_results(primary, secondary)
    assert len(merged["monthly_history"]) == 2


def test_count_missing_priority():
    raw = {"consumer_name": "X", "consumer_number": None, "units_consumed": None}
    missing = _count_missing_priority(raw)
    assert "consumer_number" in missing
    assert "consumer_name" not in missing


if __name__ == "__main__":
    test_merge_fills_gaps()
    test_merge_monthly_history_dedupes()
    test_count_missing_priority()
    print("All extraction helper tests passed.")
