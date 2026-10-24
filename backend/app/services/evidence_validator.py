
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
import re


# Configure these domains for the sources your application actually trusts.
DEFAULT_TRUSTED_DOMAINS = {
    "rbi.org.in",
    "sebi.gov.in",
    "mca.gov.in",
    "nclt.gov.in",
    "ibbi.gov.in",
    "indiacode.nic.in",
    "crisil.com",
    "icra.in",
    "nseindia.com",
    "bseindia.com",
    "indiaratings.co.in",
}


@dataclass
class EvidenceInput:
    claim: str
    source_url: str
    source_name: str
    excerpt: str | None = None
    entity_name: str | None = None
    expected_entity: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None


@dataclass
class ValidationResult:
    status: str
    credibility_score: float
    relevance_score: float
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


def normalize_text(value: str | None) -> str:
    """Normalize text for comparison."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().casefold()


def domain_is_trusted(
    hostname: str,
    trusted_domains: set[str],
) -> bool:
    """Match an exact trusted domain or one of its subdomains."""
    hostname = hostname.casefold().rstrip(".")

    return any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in trusted_domains
    )


def validate_evidence(
    evidence: EvidenceInput,
    trusted_domains: set[str] | None = None,
    max_age_days: int = 730,
) -> ValidationResult:
    """Validate evidence metadata and calculate preliminary scores.

    A valid result means the configured checks passed. It does not prove
    that the source is authentic or that its content establishes the claim.
    """
    trusted_domains = (
        DEFAULT_TRUSTED_DOMAINS
        if trusted_domains is None
        else trusted_domains
    )

    reasons: list[str] = []
    checks: dict[str, bool] = {}

    claim = normalize_text(evidence.claim)
    excerpt = normalize_text(evidence.excerpt)

    # 1. Required content
    checks["claim_present"] = bool(claim)
    checks["source_name_present"] = bool(
        normalize_text(evidence.source_name)
    )
    checks["excerpt_present"] = bool(excerpt)

    if not checks["claim_present"]:
        reasons.append("Claim is missing.")

    if not checks["source_name_present"]:
        reasons.append("Source name is missing.")

    if not checks["excerpt_present"]:
        reasons.append("Supporting excerpt is missing.")

    # 2. URL validation
    source_url = (evidence.source_url or "").strip()

    try:
        parsed = urlparse(source_url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        url_valid = (
            parsed.scheme.casefold() == "https"
            and bool(hostname)
            and not any(char.isspace() for char in source_url)
            and parsed.username is None
            and parsed.password is None
            and bool(parsed.netloc)
        )
    except ValueError:
        hostname = ""
        url_valid = False

    checks["url_valid"] = url_valid

    if not checks["url_valid"]:
        reasons.append("Source URL must be a valid HTTPS URL.")

    # 3. Source domain
    checks["trusted_domain"] = (
        checks["url_valid"]
        and domain_is_trusted(hostname, trusted_domains)
    )

    if not checks["trusted_domain"]:
        reasons.append(
            "Source domain is not in the trusted-domain allowlist."
        )

    # 4. Entity matching
    expected_entity = normalize_text(evidence.expected_entity)
    actual_entity = normalize_text(evidence.entity_name)

    checks["entity_match"] = (
        bool(expected_entity)
        and bool(actual_entity)
        and expected_entity == actual_entity
    )

    if not checks["entity_match"]:
        reasons.append(
            "Entity identity is missing or does not exactly match."
        )

    # 5. Publication date freshness
    now = datetime.now(timezone.utc)
    published_at = evidence.published_at

    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    checks["publication_date_present"] = published_at is not None

    checks["publication_date_not_future"] = (
        published_at is not None and published_at <= now
    )

    checks["fresh_enough"] = (
        published_at is not None
        and published_at <= now
        and (now - published_at).days <= max_age_days
    )

    if not checks["publication_date_present"]:
        reasons.append("Publication date is unavailable.")
    elif not checks["publication_date_not_future"]:
        reasons.append("Publication date is in the future.")
    elif not checks["fresh_enough"]:
        reasons.append(
            "Evidence is older than the configured freshness limit."
        )

    # 6. Preliminary claim/excerpt relevance.
    # Combine claim and expected entity because search-result titles
    # are often short. This is a lexical heuristic, not semantic proof.
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this",
        "was", "were", "are", "has", "have", "had", "its",
        "into", "about", "their", "they", "will", "would",
        "limited", "ltd", "company",
    }

    relevance_text = " ".join(
        part
        for part in (evidence.claim, evidence.expected_entity)
        if part
    )

    claim_terms = {
        word
        for word in re.findall(
            r"\b[a-z0-9]+\b",
            normalize_text(relevance_text),
        )
        if len(word) > 2 and word not in stop_words
    }

    excerpt_terms = set(
        re.findall(r"\b[a-z0-9]+\b", excerpt)
    )

    overlap = claim_terms & excerpt_terms

    relevance_score = (
        len(overlap) / len(claim_terms)
        if claim_terms
        else 0.0
    )

    checks["lexical_relevance"] = relevance_score >= 0.30

    if not checks["lexical_relevance"]:
        reasons.append(
            "Excerpt has insufficient keyword overlap with the claim and entity."
        )

    # 7. Preliminary credibility score.
    # This reflects allowlist membership only, not factual truth.
    credibility_score = (
        1.0 if checks["trusted_domain"] else 0.0
    )

    # 8. Determine validation status.
    # Missing publication dates and untrusted domains require review.
    # A publication date in the future is a hard failure only when present.
    hard_failures = (
        not checks["claim_present"]
        or not checks["source_name_present"]
        or not checks["excerpt_present"]
        or not checks["url_valid"]
        or not checks["entity_match"]
        or (
            checks["publication_date_present"]
            and not checks["publication_date_not_future"]
        )
    )

    if hard_failures:
        status = "rejected"
    elif not (
        checks["trusted_domain"]
        and checks["fresh_enough"]
        and checks["lexical_relevance"]
    ):
        status = "needs_review"
    else:
        status = "valid"

    return ValidationResult(
        status=status,
        credibility_score=credibility_score,
        relevance_score=round(relevance_score, 3),
        reasons=reasons,
        checks=checks,
    )
