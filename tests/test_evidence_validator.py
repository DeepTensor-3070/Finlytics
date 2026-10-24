
from datetime import datetime, timezone

from backend.app.services.evidence_validator import (
    EvidenceInput,
    validate_evidence,
)


def test_trusted_relevant_evidence_passes():
    evidence = EvidenceInput(
        claim="RBI imposed a penalty on the company for noncompliance",
        source_url="https://rbi.org.in/example",
        source_name="Reserve Bank of India",
        excerpt=(
            "RBI imposed a penalty on the company for "
            "noncompliance with regulatory requirements."
        ),
        entity_name="Example Company",
        expected_entity="Example Company",
        published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    result = validate_evidence(evidence)

    assert result.status == "valid"
    assert result.checks["trusted_domain"] is True
    assert result.checks["entity_match"] is True


def test_untrusted_domain_requires_review():
    evidence = EvidenceInput(
        claim="Company reported financial losses",
        source_url="https://unknown-example.com/news",
        source_name="Unknown publication",
        excerpt="The company reported financial losses.",
        entity_name="Example Company",
        expected_entity="Example Company",
        published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    result = validate_evidence(evidence)

    assert result.status == "needs_review"
    assert result.checks["trusted_domain"] is False


def test_entity_mismatch_is_rejected():
    evidence = EvidenceInput(
        claim="Company reported financial losses",
        source_url="https://rbi.org.in/example",
        source_name="Reserve Bank of India",
        excerpt="The company reported financial losses.",
        entity_name="Different Company",
        expected_entity="Example Company",
        published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    result = validate_evidence(evidence)

    assert result.status == "rejected"
    assert result.checks["entity_match"] is False
