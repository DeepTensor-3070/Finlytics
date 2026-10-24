
from decimal import Decimal, InvalidOperation
from typing import Any


DEFAULT_THRESHOLDS = {
    "minimum_current_ratio": Decimal("1.0"),
    "elevated_liabilities_to_assets_pct": Decimal("60"),
    "high_liabilities_to_assets_pct": Decimal("75"),
}


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None

    return number if number.is_finite() else None


def _get_metric(
    analysis: dict[str, Any],
    name: str,
) -> dict[str, Any] | None:
    for metric in analysis.get("metrics", []):
        if metric.get("name") == name:
            return metric
    return None


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    code: str,
    category: str,
    severity: str,
    title: str,
    explanation: str,
    metric: dict[str, Any] | None = None,
) -> None:
    findings.append({
        "code": code,
        "category": category,
        "severity": severity,
        "title": title,
        "explanation": explanation,
        "metric": (
            {
                "name": metric.get("name"),
                "value": metric.get("value"),
                "unit": metric.get("unit"),
                "reporting_period": metric.get("reporting_period"),
                "formula": metric.get("formula"),
                "inputs": metric.get("inputs", {}),
            }
            if metric
            else None
        ),
    })


def assess_financial_risk(
    financial_analysis: dict[str, Any],
    external_evidence: list[dict[str, Any]] | None = None,
    *,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a preliminary, explainable risk assessment.

    External evidence is included as a separate evidence review.
    This function does not verify facts or make lending decisions.
    """
    config = {
        **DEFAULT_THRESHOLDS,
        **(thresholds or {}),
    }

    minimum_current_ratio = _decimal(
        config["minimum_current_ratio"]
    )
    elevated_liabilities_pct = _decimal(
        config["elevated_liabilities_to_assets_pct"]
    )
    high_liabilities_pct = _decimal(
        config["high_liabilities_to_assets_pct"]
    )

    if any(
        value is None
        for value in (
            minimum_current_ratio,
            elevated_liabilities_pct,
            high_liabilities_pct,
        )
    ):
        raise ValueError("Risk thresholds must be valid finite numbers.")

    if (
        minimum_current_ratio < 0
        or elevated_liabilities_pct < 0
        or high_liabilities_pct < elevated_liabilities_pct
        or high_liabilities_pct > 100
    ):
        raise ValueError("Risk thresholds are inconsistent or out of range.")

    findings: list[dict[str, Any]] = []
    limitations: list[str] = []

    # Profitability
    margin = _get_metric(financial_analysis, "net_profit_margin")
    margin_value = (
        _decimal(margin.get("value"))
        if margin and margin.get("status") == "calculated"
        else None
    )

    if margin_value is not None and margin_value < 0:
        _add_finding(
            findings,
            code="negative_profit_margin",
            category="profitability",
            severity="high",
            title="Negative net profit margin",
            explanation=(
                "Reported net profit is negative relative to revenue. "
                "Review the financial statements and possible one-off losses."
            ),
            metric=margin,
        )
    elif margin_value is None:
        limitations.append(
            "Profitability could not be assessed from an available, "
            "unambiguous net profit margin."
        )

    # Liquidity
    current_ratio = _get_metric(financial_analysis, "current_ratio")
    current_ratio_value = (
        _decimal(current_ratio.get("value"))
        if current_ratio and current_ratio.get("status") == "calculated"
        else None
    )

    if (
        current_ratio_value is not None
        and current_ratio_value < minimum_current_ratio
    ):
        _add_finding(
            findings,
            code="weak_current_ratio",
            category="liquidity",
            severity="high",
            title="Current ratio below configured threshold",
            explanation=(
                f"The current ratio is below the configured threshold "
                f"of {minimum_current_ratio}. This may indicate liquidity "
                "pressure and requires further review."
            ),
            metric=current_ratio,
        )
    elif current_ratio_value is None:
        limitations.append(
            "Liquidity could not be assessed from an available, "
            "unambiguous current ratio."
        )

    # Liabilities relative to assets
    leverage = _get_metric(financial_analysis, "debt_to_assets")
    leverage_value = (
        _decimal(leverage.get("value"))
        if leverage and leverage.get("status") == "calculated"
        else None
    )

    if leverage_value is not None:
        if leverage_value >= high_liabilities_pct:
            _add_finding(
                findings,
                code="high_liabilities_to_assets",
                category="leverage",
                severity="high",
                title="High liabilities relative to assets",
                explanation=(
                    f"Reported liabilities represent {leverage_value}% "
                    "of reported total assets, meeting or exceeding the "
                    "configured high-risk threshold. This ratio includes "
                    "all reported liabilities, not only interest-bearing debt."
                ),
                metric=leverage,
            )
        elif leverage_value >= elevated_liabilities_pct:
            _add_finding(
                findings,
                code="elevated_liabilities_to_assets",
                category="leverage",
                severity="medium",
                title="Elevated liabilities relative to assets",
                explanation=(
                    f"Reported liabilities represent {leverage_value}% "
                    "of reported total assets, meeting the configured "
                    "elevated threshold."
                ),
                metric=leverage,
            )
    else:
        limitations.append(
            "Leverage could not be assessed from an available, "
            "unambiguous liabilities-to-assets ratio."
        )

    # External evidence review: do not treat claims as proven facts.
    evidence_review = []
    for item in external_evidence or []:
        status = str(
            item.get("validation_status", "unknown")
        ).casefold()

        if status == "valid":
            disposition = "validated_source_requires_fact_review"
        elif status == "rejected":
            disposition = "excluded_rejected_source"
        else:
            disposition = "requires_manual_review"

        evidence_review.append({
            "evidence_id": item.get("id"),
            "claim": item.get("claim"),
            "source_name": item.get("source_name"),
            "source_url": item.get("source_url"),
            "validation_status": status,
            "disposition": disposition,
            "explanation": (
                "Source validation does not establish that the claim "
                "is true. Review the source content and its relevance "
                "before using it in a risk decision."
            ),
        })

    if any(
        item["disposition"] == "requires_manual_review"
        for item in evidence_review
    ):
        limitations.append(
            "Some external evidence requires manual review before use."
        )

    if any(
        item["disposition"]
        == "validated_source_requires_fact_review"
        for item in evidence_review
    ):
        limitations.append(
            "Some sources passed configured validation checks, but "
            "their claims have not been independently established as facts."
        )

    if findings:
        overall_status = "findings_require_review"
    elif limitations:
        overall_status = "insufficient_information"
    else:
        overall_status = "no_configured_indicators_triggered"

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(
        key=lambda finding: severity_order[finding["severity"]]
    )

    return {
        "assessment_type": "preliminary_financial_risk",
        "overall_status": overall_status,
        "findings": findings,
        "finding_count": len(findings),
        "external_evidence_review": evidence_review,
        "limitations": limitations,
        "thresholds": {
            key: str(value)
            for key, value in config.items()
        },
        "disclaimer": (
            "This is a preliminary rule-based assessment, not a credit "
            "decision, audit opinion, or independent verification of "
            "financial statements or external claims."
        ),
    }
