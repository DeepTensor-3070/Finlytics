from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.evidence import (
    EvidenceCollectionRequest,
    EvidenceCreate,
    EvidenceList,
    EvidenceRead,
)
from backend.app.services.evidence_collection_service import (
    collect_external_evidence,
)
from backend.app.services.evidence_service import (
    create_evidence,
    list_case_evidence,
)
from backend.app.services.evidence_validator import EvidenceInput
from backend.app.services.tinyfish_client import TinyFishError

router = APIRouter(prefix="/api/v1/cases", tags=["External Evidence"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/{case_id}/evidence",
    status_code=status.HTTP_201_CREATED,
)
def submit_evidence(
    case_id: str,
    payload: EvidenceCreate,
    db: DbSession,
):
    validator_input = EvidenceInput(
        claim=payload.claim,
        source_name=payload.source_name,
        source_url=str(payload.source_url),
        excerpt=payload.excerpt,
        entity_name=payload.entity_name,
        expected_entity=payload.expected_entity,
        published_at=payload.published_at,
    )

    try:
        evidence, validation = create_evidence(
            db, case_id, validator_input
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "evidence": EvidenceRead.model_validate(evidence),
        "validation": validation,
    }


@router.get(
    "/{case_id}/evidence",
    response_model=EvidenceList,
)
def get_case_evidence(case_id: str, db: DbSession):
    try:
        items = list_case_evidence(db, case_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {"items": items, "total": len(items)}


@router.post(
    "/{case_id}/evidence/collect",
    status_code=status.HTTP_200_OK,
)
async def collect_case_evidence(
    case_id: str,
    payload: EvidenceCollectionRequest,
    db: DbSession,
):
    try:
        return await collect_external_evidence(
            session=db,
            case_id=case_id,
            query=payload.query,
            expected_entity=payload.expected_entity,
            max_results=payload.max_results,
        )
    except ValueError as exc:
        # The collection service currently uses ValueError for
        # a missing case and invalid input.
        message = str(exc)
        error_status = (
            status.HTTP_404_NOT_FOUND
            if message == "Case not found."
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=error_status,
            detail=message,
        ) from exc
    except TinyFishError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
