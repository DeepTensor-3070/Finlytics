from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.schemas.case import CaseCreate, CaseUpdate


def create_case(db: Session, payload: CaseCreate) -> Case:
    case = Case(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, case_id: str) -> Case | None:
    return db.get(Case, case_id)


def list_cases(
    db: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[Case], int]:
    query = select(Case)
    count_query = select(func.count()).select_from(Case)

    if status is not None:
        query = query.where(Case.status == status)
        count_query = count_query.where(Case.status == status)

    items = list(
        db.scalars(
            query.order_by(Case.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    total = db.scalar(count_query) or 0

    return items, total


def update_case(
    db: Session,
    case: Case,
    payload: CaseUpdate,
) -> Case:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)
    return case


def update_case_status(db: Session, case: Case, status: str) -> Case:
    case.status = status
    db.commit()
    db.refresh(case)
    return case


def delete_case(db: Session, case: Case) -> None:
    db.delete(case)
    db.commit()