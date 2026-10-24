from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.case import (
    CaseCreate,
    CaseList,
    CaseRead,
    CaseStatusUpdate,
    CaseUpdate,
)
from backend.app.services import case_service

router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])

DbSession = Annotated[Session, Depends(get_db)]


def get_case_or_404(db: Session, case_id: str):
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return case


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: DbSession):
    return case_service.create_case(db, payload)


@router.get("", response_model=CaseList)
def get_cases(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    case_status: str | None = Query(default=None, alias="status"),
):
    items, total = case_service.list_cases(
        db,
        limit=limit,
        offset=offset,
        status=case_status,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: str, db: DbSession):
    return get_case_or_404(db, case_id)


@router.patch("/{case_id}", response_model=CaseRead)
def patch_case(case_id: str, payload: CaseUpdate, db: DbSession):
    case = get_case_or_404(db, case_id)
    return case_service.update_case(db, case, payload)


@router.patch("/{case_id}/status", response_model=CaseRead)
def patch_case_status(
    case_id: str,
    payload: CaseStatusUpdate,
    db: DbSession,
):
    case = get_case_or_404(db, case_id)
    return case_service.update_case_status(db, case, payload.status)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_case(case_id: str, db: DbSession):
    case = get_case_or_404(db, case_id)
    case_service.delete_case(db, case)
    return Response(status_code=status.HTTP_204_NO_CONTENT)