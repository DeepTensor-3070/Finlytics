
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal_value(field: dict[str, Any]) -> Decimal | None:
    if field.get("status") != "extracted":
        return None

    value = field.get("value")
    if value is None:
        return None

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

    return number if number.is_finite() else None


def _select_period_field(
    field: dict[str, Any],
    period: str | None,
) -> dict[str, Any]:
    """Select a value for an explicit period without guessing."""
    if not period:
        return field

    period_values = field.get("period_values")
    if not period_values:
        # A single-period result has no explicit period metadata.
        # Do not assume it belongs to the requested period.
        return {
            "value": None,
            "currency": None,
            "status": "period_unavailable",
            "candidates": [],
        }

    selected = period_values.get(period)
    if not selected:
        return {
            "value": None,
            "currency": None,
            "status": "period_unavailable",
            "candidates": [],
        }

    return {
        **selected,
        "candidates": field.get("candidates", []),
    }


def _currency_compatible(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    first_currency = first.get("currency")
    second_currency = second.get("currency")

    return not (
        first_currency
        and second_currency
        and first_currency != second_currency
    )


def _metric(
    *,
    name: str,
    numerator: Decimal | None,
    denominator: Decimal | None,
    formula: str,
    explanation: str,
    percentage: bool = False,
    numerator_field: dict[str, Any] | None = None,
    denominator_field: dict[str, Any] | None = None,
    reporting_period: str | None = None,
) -> dict[str, Any]:
    result = {
        "name": name,
        "value": None,
        "unit": "percent" if percentage else "ratio",
        "status": "not_calculated",
        "formula": formula,
        "explanation": explanation,
        "reporting_period": reporting_period,
        "inputs": {},
        "reason": None,
    }

    if numerator_field is not None:
        result["inputs"]["numerator"] = {
            "value": numerator_field.get("value"),
            "status": numerator_field.get("status"),
            "currency": numerator_field.get("currency"),
            "candidates": numerator_field.get("candidates", []),
        }

    if denominator_field is not None:
        result["inputs"]["denominator"] = {
            "value": denominator_field.get("value"),
            "status": denominator_field.get("status"),
            "currency": denominator_field.get("currency"),
            "candidates": denominator_field.get("candidates", []),
        }

    if numerator is None or denominator is None:
        result["reason"] = (
            "One or more required inputs are missing, ambiguous, "
            "or unavailable for the selected period."
        )
        return result

    if (
        numerator_field
        and denominator_field
        and not _currency_compatible(
            numerator_field,
            denominator_field,
        )
    ):
        result["reason"] = "Input currencies differ."
        return result

    if denominator == 0:
        result["reason"] = "The denominator is zero."
        return result

    value = numerator / denominator
    if percentage:
        value *= Decimal("100")

    result["value"] = str(value.quantize(Decimal("0.01")))
    result["status"] = "calculated"
    return result


def _calculate_revenue_growth(
    revenue_field: dict[str, Any],
    current_period: str | None,
    previous_period: str | None,
) -> dict[str, Any]:
    result = {
        "name": "revenue_growth",
        "value": None,
        "unit": "percent",
        "status": "not_calculated",
        "formula": (
            "(current revenue - previous revenue) "
            "/ previous revenue * 100"
        ),
        "explanation": (
            "Measures the percentage change in revenue "
            "between two selected reporting periods."
        ),
        "reporting_period": current_period,
        "inputs": {},
        "reason": None,
    }

    if not current_period or not previous_period:
        result["reason"] = (
            "Specify current_period and previous_period to calculate growth."
        )
        return result

    current = _select_period_field(revenue_field, current_period)
    previous = _select_period_field(revenue_field, previous_period)

    current_value = _decimal_value(current)
    previous_value = _decimal_value(previous)

    result["inputs"] = {
        "current_period": {
            "period": current_period,
            "value": current.get("value"),
            "status": current.get("status"),
            "currency": current.get("currency"),
        },
        "previous_period": {
            "period": previous_period,
            "value": previous.get("value"),
            "status": previous.get("status"),
            "currency": previous.get("currency"),
        },
    }

    if current_value is None or previous_value is None:
        result["reason"] = (
            "Revenue must be unambiguous and available for both periods."
        )
        return result

    if not _currency_compatible(current, previous):
        result["reason"] = "Revenue currencies differ between periods."
        return result

    if previous_value == 0:
        result["reason"] = "Previous-period revenue is zero."
        return result

    growth = (
        (current_value - previous_value)
        / previous_value
        * Decimal("100")
    )

    result["value"] = str(growth.quantize(Decimal("0.01")))
    result["status"] = "calculated"
    return result


def analyze_financials(
    extracted_fields: dict[str, Any],
    *,
    current_period: str | None = None,
    previous_period: str | None = None,
) -> dict[str, Any]:
    """Calculate basic ratios using values from a selected period.

    This service calculates metrics; it does not independently verify
    source figures or make lending decisions.
    """
    period_fields = {
        name: _select_period_field(
            extracted_fields.get(name, {}),
            current_period,
        )
        for name in (
            "revenue",
            "net_profit",
            "total_assets",
            "total_liabilities",
            "current_assets",
            "current_liabilities",
        )
    }

    fields = period_fields

    revenue = _decimal_value(fields["revenue"])
    net_profit = _decimal_value(fields["net_profit"])
    total_assets = _decimal_value(fields["total_assets"])
    total_liabilities = _decimal_value(fields["total_liabilities"])
    current_assets = _decimal_value(fields["current_assets"])
    current_liabilities = _decimal_value(fields["current_liabilities"])

    metrics = [
        _metric(
            name="net_profit_margin",
            numerator=net_profit,
            denominator=revenue,
            formula="net profit / revenue * 100",
            explanation="Net profit or loss as a percentage of revenue.",
            percentage=True,
            numerator_field=fields["net_profit"],
            denominator_field=fields["revenue"],
            reporting_period=current_period,
        ),
        _metric(
            name="current_ratio",
            numerator=current_assets,
            denominator=current_liabilities,
            formula="current assets / current liabilities",
            explanation="Compares current assets with current liabilities.",
            numerator_field=fields["current_assets"],
            denominator_field=fields["current_liabilities"],
            reporting_period=current_period,
        ),
        _metric(
            name="debt_to_assets",
            numerator=total_liabilities,
            denominator=total_assets,
            formula="total liabilities / total assets * 100",
            explanation=(
                "Reported liabilities as a percentage of total assets; "
                "this is not necessarily interest-bearing debt."
            ),
            percentage=True,
            numerator_field=fields["total_liabilities"],
            denominator_field=fields["total_assets"],
            reporting_period=current_period,
        ),
        _calculate_revenue_growth(
            extracted_fields.get("revenue", {}),
            current_period,
            previous_period,
        ),
    ]

    return {
        "reporting_period": current_period,
        "metrics": metrics,
        "limitations": [
            "Ratios depend on the accuracy of extracted source figures.",
            "Missing or ambiguous values are not used in calculations.",
            "When a period is selected, values without matching period "
            "metadata are not assumed to belong to that period.",
            "Unknown currency does not establish that values use the same currency.",
            "Revenue growth requires explicit reporting-period selection.",
            "Ratios alone do not establish creditworthiness.",
        ],
    }

