
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.evidence import ExternalEvidence
from backend.app.services.evidence_validator import (
    EvidenceInput,
    validate_evidence,
)


def create_evidence(
    session: Session,
    case_id: str,
    payload: EvidenceInput,
) -> tuple[ExternalEvidence, dict]:
    if session.get(Case, case_id) is None:
        raise ValueError("Case not found.")

    result = validate_evidence(payload)

    evidence = ExternalEvidence(
        case_id=case_id,
        claim=payload.claim,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_type="web",
        published_at=payload.published_at,
        retrieved_at=datetime.now(timezone.utc),
        excerpt=payload.excerpt,
        entity_name=payload.entity_name,
        relevance_score=result.relevance_score,
        credibility_score=result.credibility_score,
        validation_status=result.status,
        validation_reason="; ".join(result.reasons) or None,
    )

    session.add(evidence)
    session.commit()
    session.refresh(evidence)

    return evidence, {
        "status": result.status,
        "credibility_score": result.credibility_score,
        "relevance_score": result.relevance_score,
        "checks": result.checks,
        "reasons": result.reasons,
    }


def list_case_evidence(
    session: Session,
    case_id: str,
) -> list[ExternalEvidence]:
    if session.get(Case, case_id) is None:
        raise ValueError("Case not found.")

    statement = (
        select(ExternalEvidence)
        .where(ExternalEvidence.case_id == case_id)
        .order_by(ExternalEvidence.created_at.desc())
    )

    return list(session.scalars(statement).all())
