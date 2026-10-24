
import pytest

from backend.app.services.risk_assessment_service import (
    assess_financial_risk,
)


def metric(name, value, unit="ratio", period="2025"):
    return {
        "name": name,
        "value": str(value) if value is not None else None,
        "unit": unit,
        "status": "calculated" if value is not None else "not_calculated",
        "reporting_period": period,
        "formula": "test formula",
        "inputs": {},
    }


def analysis(
    margin="10",
    current_ratio="2",
    liabilities_to_assets="40",
):
    return {
        "metrics": [
            metric("net_profit_margin", margin, "percent"),
            metric("current_ratio", current_ratio),
            metric("debt_to_assets", liabilities_to_assets, "percent"),
        ]
    }


def test_no_configured_indicators_produces_no_findings():
    result = assess_financial_risk(analysis())

    assert result["finding_count"] == 0
    assert result["overall_status"] == "no_configured_indicators_triggered"


def test_negative_profit_margin_creates_high_finding():
    result = assess_financial_risk(analysis(margin="-5"))

    assert result["findings"][0]["code"] == "negative_profit_margin"
    assert result["findings"][0]["severity"] == "high"


def test_low_current_ratio_creates_liquidity_finding():
    result = assess_financial_risk(analysis(current_ratio="0.8"))

    assert any(
        item["code"] == "weak_current_ratio"
        for item in result["findings"]
    )


def test_high_liabilities_to_assets_creates_high_finding():
    result = assess_financial_risk(
        analysis(liabilities_to_assets="80")
    )

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "high_liabilities_to_assets"
    )
    assert finding["severity"] == "high"


def test_missing_metrics_are_not_treated_as_low_risk():
    result = assess_financial_risk(
        analysis(margin=None, current_ratio=None, liabilities_to_assets=None)
    )

    assert result["finding_count"] == 0
    assert result["overall_status"] == "insufficient_information"
    assert len(result["limitations"]) >= 3


def test_validated_source_is_not_treated_as_proven_fact():
    evidence = [{
        "id": "evidence-1",
        "claim": "The company is facing litigation.",
        "source_name": "Example Source",
        "source_url": "https://example.com/article",
        "validation_status": "valid",
    }]

    result = assess_financial_risk(analysis(), evidence)

    reviewed = result["external_evidence_review"][0]
    assert reviewed["disposition"] == "validated_source_requires_fact_review"
    assert "not been independently established" in " ".join(
        result["limitations"]
    )


def test_rejected_evidence_is_excluded_from_validated_evidence():
    evidence = [{
        "id": "evidence-2",
        "claim": "Unsupported claim",
        "source_name": "Unknown",
        "source_url": "https://example.invalid/article",
        "validation_status": "rejected",
    }]

    result = assess_financial_risk(analysis(), evidence)

    assert (
        result["external_evidence_review"][0]["disposition"]
        == "excluded_rejected_source"
    )


def test_invalid_threshold_configuration_is_rejected():
    with pytest.raises(ValueError):
        assess_financial_risk(
            analysis(),
            thresholds={
                "elevated_liabilities_to_assets_pct": 80,
                "high_liabilities_to_assets_pct": 70,
            },
        )
