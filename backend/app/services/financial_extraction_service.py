
import re
from decimal import Decimal, InvalidOperation
from typing import Any


FINANCIAL_FIELDS = {
    "revenue": (
        "revenue from operations",
        "total revenue",
        "revenue",
        "turnover",
        "net sales",
        "total sales",
    ),
    "net_profit": (
        "profit after tax",
        "profit for the year",
        "net profit",
        "net income",
        "net loss",
        "loss for the year",
    ),
    "total_assets": ("total assets", "assets total"),
    "total_liabilities": ("total liabilities", "liabilities total"),
    "current_assets": ("total current assets", "current assets"),
    "current_liabilities": (
        "total current liabilities",
        "current liabilities",
    ),
}

NUMBER_PATTERN = re.compile(
    r"""
    (?<![\w/])
    \(?-?
    (?:
        \d{1,3}(?:,\d{2,3})+
        |
        \d+
    )
    (?:\.\d+)?
    \)?
    (?![\w/])
    """,
    re.VERBOSE,
)

CURRENCY_PATTERN = re.compile(r"(?i)(₹|rs\.?|inr|usd|\$|eur|€|gbp|£)")

UNIT_MULTIPLIERS = {
    "thousand": Decimal("1000"),
    "thousands": Decimal("1000"),
    "lakh": Decimal("100000"),
    "lakhs": Decimal("100000"),
    "lac": Decimal("100000"),
    "lacs": Decimal("100000"),
    "million": Decimal("1000000"),
    "millions": Decimal("1000000"),
    "crore": Decimal("10000000"),
    "crores": Decimal("10000000"),
    "billion": Decimal("1000000000"),
    "billions": Decimal("1000000000"),
}

PERIOD_PATTERNS = (
    re.compile(
        r"\bFY\s*[-:]?\s*((?:19|20)\d{2})"
        r"(?:\s*[-/]\s*((?:19|20)?\d{2}))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b((?:19|20)\d{2})\s*[-/]\s*((?:19|20)?\d{2})\b"
    ),
    re.compile(
        r"\b(?:31\s+March|March\s+31|31st\s+March)"
        r"\s*,?\s*((?:19|20)\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:year ended|year ending|as at|as of|as on)"
        r"\s+(?:31\s+March\s+)?((?:19|20)\d{2})\b",
        re.IGNORECASE,
    ),
)


def _normalize_label(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _parse_number(raw_value: str) -> Decimal | None:
    value = raw_value.strip().replace(",", "")
    negative = value.startswith("(") and value.endswith(")")

    if negative:
        value = value[1:-1]

    try:
        number = Decimal(value)
    except InvalidOperation:
        return None

    if negative:
        number = -abs(number)

    return number if number.is_finite() else None


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _extract_currency(text: str) -> str | None:
    match = CURRENCY_PATTERN.search(text)
    if not match:
        return None

    symbol = match.group(1).casefold().rstrip(".")
    return {
        "₹": "INR",
        "rs": "INR",
        "inr": "INR",
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
    }.get(symbol)


def _extract_unit_multiplier(text: str) -> Decimal:
    normalized = text.casefold()

    for unit, multiplier in sorted(
        UNIT_MULTIPLIERS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if re.search(rf"\b{re.escape(unit)}\b", normalized):
            return multiplier

    return Decimal("1")


def _normalize_year(year: str) -> int:
    value = int(year)
    if value < 100:
        return 2000 + value if value <= 69 else 1900 + value
    return value


def _detect_period(text: str) -> str | None:
    """Detect an explicitly stated reporting period; do not infer one."""
    for pattern in PERIOD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        groups = match.groups()

        if len(groups) > 1 and groups[1]:
            start_year = _normalize_year(groups[0])
            end_year = _normalize_year(groups[1])

            # For forms such as 2024-25, interpret 25 as 2025.
            if len(groups[1]) == 2 and end_year < start_year:
                end_year = (start_year // 100) * 100 + int(groups[1])
                if end_year < start_year:
                    end_year += 100

            return f"{start_year}-{end_year}"

        return str(_normalize_year(groups[0]))

    return None


def _split_pages(text: str) -> list[tuple[int | None, str]]:
    marker = re.compile(r"(?m)^--- Page (\d+) ---\s*$")
    matches = list(marker.finditer(text))

    if not matches:
        return [(None, text)]

    pages = []
    for index, match in enumerate(matches):
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        pages.append((int(match.group(1)), text[start:end]))

    return pages


def _find_label_matches(
    text: str,
    field_name: str,
    aliases: tuple[str, ...],
) -> list[dict[str, Any]]:
    candidates = []

    for page_number, page_text in _split_pages(text):
        current_period = None

        for line in page_text.splitlines():
            line_period = _detect_period(line)
            if line_period:
                current_period = line_period

            normalized_line = _normalize_label(line)
            matching_aliases = [
                alias
                for alias in aliases
                if re.search(
                    rf"(?<![a-z0-9])"
                    rf"{re.escape(_normalize_label(alias))}"
                    rf"(?![a-z0-9])",
                    normalized_line,
                )
            ]

            if not matching_aliases:
                continue

            alias = max(matching_aliases, key=len)
            normalized_alias = _normalize_label(alias)
            alias_pattern = re.escape(normalized_alias).replace(
                r"\ ", r"\s+"
            )
            label_match = re.search(alias_pattern, line, re.IGNORECASE)

            if not label_match:
                continue

            remainder = line[label_match.end():]
            number_matches = list(NUMBER_PATTERN.finditer(remainder))
            if not number_matches:
                continue

            number_match = number_matches[0]
            raw_value = number_match.group(0)
            value = _parse_number(raw_value)

            if value is None:
                continue

            context = line.strip()
            multiplier = _extract_unit_multiplier(context)

            candidates.append({
                "field": field_name,
                "label": alias,
                "raw_value": raw_value,
                "value": value * multiplier,
                "currency": _extract_currency(context),
                "unit_multiplier": _format_decimal(multiplier),
                "page_number": page_number,
                "source_text": context,
                "reporting_period": line_period or current_period,
            })

    return candidates


def extract_financial_fields(extracted_text: str) -> dict[str, Any]:
    """Extract candidate values without claiming factual verification."""
    results: dict[str, Any] = {}

    for field_name, aliases in FINANCIAL_FIELDS.items():
        candidates = _find_label_matches(
            extracted_text, field_name, aliases
        )

        if not candidates:
            results[field_name] = {
                "value": None,
                "currency": None,
                "status": "not_found",
                "candidates": [],
            }
            continue

        # Do not treat different reporting periods as conflicting values.
        by_period: dict[str | None, list[dict[str, Any]]] = {}
        for candidate in candidates:
            by_period.setdefault(
                candidate["reporting_period"], []
            ).append(candidate)

        period_results = {}
        for period, period_candidates in by_period.items():
            distinct_values = {
                (item["value"], item["currency"])
                for item in period_candidates
            }

            if len(distinct_values) > 1:
                period_results[period or "unspecified"] = {
                    "value": None,
                    "currency": None,
                    "status": "ambiguous",
                }
            else:
                period_results[period or "unspecified"] = {
                    "value": _format_decimal(
                        period_candidates[0]["value"]
                    ),
                    "currency": period_candidates[0]["currency"],
                    "status": "extracted",
                }

        all_periods_specified = all(
            candidate["reporting_period"] is not None
            for candidate in candidates
        )

        if len(by_period) == 1:
            only_period_candidates = next(iter(by_period.values()))
            distinct_values = {
                (item["value"], item["currency"])
                for item in only_period_candidates
            }
            if len(distinct_values) > 1:
                status, value, currency = "ambiguous", None, None
            else:
                status = "extracted"
                value = _format_decimal(only_period_candidates[0]["value"])
                currency = only_period_candidates[0]["currency"]
        elif all_periods_specified:
            status, value, currency = "multi_period", None, None
        else:
            # Period association is incomplete, so retain uncertainty.
            status, value, currency = "ambiguous", None, None

        results[field_name] = {
            "value": value,
            "currency": currency,
            "status": status,
            "period_values": period_results,
            "candidates": [
                {
                    **candidate,
                    "value": _format_decimal(candidate["value"]),
                }
                for candidate in candidates
            ],
        }

    return results
