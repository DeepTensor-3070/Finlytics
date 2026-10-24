
from backend.app.services.financial_analysis_service import analyze_financials


def field(value, currency="INR", status="extracted"):
    return {
        "value": str(value) if value is not None else None,
        "currency": currency,
        "status": status,
        "candidates": [],
    }


def test_calculates_basic_financial_ratios():
    extracted = {
        "revenue": field("1000000"),
        "net_profit": field("100000"),
        "total_assets": field("2000000"),
        "total_liabilities": field("800000"),
        "current_assets": field("600000"),
        "current_liabilities": field("300000"),
    }

    result = analyze_financials(extracted)
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["value"] == "10.00"
    assert metrics["current_ratio"]["value"] == "2.00"
    assert metrics["debt_to_assets"]["value"] == "40.00"
    assert metrics["revenue_growth"]["status"] == "not_calculated"


def test_missing_or_ambiguous_values_are_not_used():
    extracted = {
        "revenue": field("1000000"),
        "net_profit": field(None, status="ambiguous"),
    }

    result = analyze_financials(extracted)
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["value"] is None
    assert metrics["net_profit_margin"]["status"] == "not_calculated"


def test_zero_denominator_is_handled():
    extracted = {
        "revenue": field("0"),
        "net_profit": field("100000"),
    }

    result = analyze_financials(extracted)
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["value"] is None
    assert metrics["net_profit_margin"]["reason"] == "The denominator is zero."


def test_different_currencies_are_not_combined():
    extracted = {
        "revenue": field("1000000", currency="USD"),
        "net_profit": field("100000", currency="INR"),
    }

    result = analyze_financials(extracted)
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["status"] == "not_calculated"
    assert metrics["net_profit_margin"]["reason"] == "Input currencies differ."


def test_calculates_revenue_growth_for_selected_periods():
    extracted = {
        "revenue": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2024": {
                    "value": "100000",
                    "currency": "INR",
                    "status": "extracted",
                },
                "2025": {
                    "value": "125000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        }
    }

    result = analyze_financials(
        extracted,
        current_period="2025",
        previous_period="2024",
    )
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["revenue_growth"]["status"] == "calculated"
    assert metrics["revenue_growth"]["value"] == "25.00"


def test_revenue_growth_rejects_zero_previous_revenue():
    extracted = {
        "revenue": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2024": {
                    "value": "0",
                    "currency": "INR",
                    "status": "extracted",
                },
                "2025": {
                    "value": "125000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        }
    }

    result = analyze_financials(
        extracted,
        current_period="2025",
        previous_period="2024",
    )
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["revenue_growth"]["status"] == "not_calculated"
    assert metrics["revenue_growth"]["reason"] == "Previous-period revenue is zero."


def test_calculates_ratios_for_selected_reporting_period():
    extracted = {
        "revenue": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2024": {
                    "value": "100000",
                    "currency": "INR",
                    "status": "extracted",
                },
                "2025": {
                    "value": "200000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        },
        "net_profit": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2024": {
                    "value": "10000",
                    "currency": "INR",
                    "status": "extracted",
                },
                "2025": {
                    "value": "40000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        },
    }

    result = analyze_financials(extracted, current_period="2025")
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["value"] == "20.00"
    assert metrics["net_profit_margin"]["reporting_period"] == "2025"


def test_does_not_assume_single_period_values_match_requested_period():
    extracted = {
        "revenue": field("100000"),
        "net_profit": field("10000"),
    }

    result = analyze_financials(extracted, current_period="2025")
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["status"] == "not_calculated"
    assert "selected period" in metrics["net_profit_margin"]["reason"]


def test_ratio_is_unavailable_when_selected_period_is_missing():
    extracted = {
        "revenue": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2024": {
                    "value": "100000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        },
        "net_profit": {
            "value": None,
            "currency": None,
            "status": "multi_period",
            "period_values": {
                "2025": {
                    "value": "20000",
                    "currency": "INR",
                    "status": "extracted",
                },
            },
        },
    }

    result = analyze_financials(extracted, current_period="2025")
    metrics = {item["name"]: item for item in result["metrics"]}

    assert metrics["net_profit_margin"]["status"] == "not_calculated"
    assert metrics["net_profit_margin"]["value"] is None
