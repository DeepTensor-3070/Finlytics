
from backend.app.services.financial_extraction_service import (
    extract_financial_fields,
)


def test_extracts_financial_values_and_page_provenance():
    text = """--- Page 2 ---
Revenue from operations ₹ 12,50,000
Net profit 250000
Total assets 5000000
Total liabilities 2000000
Current assets 1500000
Current liabilities 800000
"""

    result = extract_financial_fields(text)

    assert result["revenue"]["status"] == "extracted"
    assert result["revenue"]["value"] == "1250000"
    assert result["revenue"]["currency"] == "INR"
    assert result["revenue"]["candidates"][0]["page_number"] == 2

    assert result["net_profit"]["value"] == "250000"
    assert result["total_assets"]["value"] == "5000000"
    assert result["total_liabilities"]["value"] == "2000000"
    assert result["current_assets"]["value"] == "1500000"
    assert result["current_liabilities"]["value"] == "800000"


def test_missing_fields_are_not_invented():
    result = extract_financial_fields(
        "This report mentions the company name only."
    )

    assert result["revenue"]["status"] == "not_found"
    assert result["revenue"]["value"] is None


def test_conflicting_values_are_marked_ambiguous():
    text = """--- Page 1 ---
Revenue 100000
--- Page 2 ---
Revenue 150000
"""

    result = extract_financial_fields(text)

    assert result["revenue"]["status"] == "ambiguous"
    assert result["revenue"]["value"] is None
    assert len(result["revenue"]["candidates"]) == 2


def test_parenthesized_negative_value():
    result = extract_financial_fields(
        "--- Page 1 ---\nNet profit (25000)\n"
    )

    assert result["net_profit"]["status"] == "extracted"
    assert result["net_profit"]["value"] == "-25000"


def test_amounts_with_explicit_units_are_normalized():
    result = extract_financial_fields(
        "--- Page 1 ---\nRevenue (in lakhs) 12.5\n"
    )

    assert result["revenue"]["value"] == "1250000"


def test_detects_financial_year_periods():
    text = """--- Page 1 ---
FY 2024
Revenue 100000
FY 2025
Revenue 150000
"""

    result = extract_financial_fields(text)

    assert result["revenue"]["status"] == "multi_period"
    assert result["revenue"]["period_values"]["2024"]["value"] == "100000"
    assert result["revenue"]["period_values"]["2025"]["value"] == "150000"


def test_detects_financial_year_ranges():
    text = """FY 2024-25
Revenue 1250000
"""

    result = extract_financial_fields(text)

    candidate = result["revenue"]["candidates"][0]
    assert candidate["reporting_period"] == "2024-2025"


def test_same_period_conflicting_values_remain_ambiguous():
    text = """FY 2025
Revenue 100000
Revenue 150000
"""

    result = extract_financial_fields(text)

    assert result["revenue"]["status"] == "ambiguous"
    assert result["revenue"]["value"] is None


def test_period_provenance_is_preserved():
    text = """--- Page 3 ---
Year ended 2025
Net profit 250000
"""

    result = extract_financial_fields(text)

    candidate = result["net_profit"]["candidates"][0]

    assert candidate["reporting_period"] == "2025"
    assert candidate["page_number"] == 3
