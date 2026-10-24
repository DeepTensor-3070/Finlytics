from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.document import DocumentList, DocumentRead
from backend.app.services import document_service

router = APIRouter(prefix="/api/v1/cases", tags=["Documents"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/{case_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_case_document(
    case_id: str,
    db: DbSession,
    file: Annotated[UploadFile, File(...)],
):
    return await document_service.upload_document(db, case_id, file)


@router.get(
    "/{case_id}/documents",
    response_model=DocumentList,
)
def get_case_documents(case_id: str, db: DbSession):
    items, total = document_service.list_documents(db, case_id)
    return {"items": items, "total": total}


@router.get(
    "/{case_id}/documents/{document_id}",
    response_model=DocumentRead,
)
def get_case_document(case_id: str, document_id: str, db: DbSession):
    return document_service.get_document(db, case_id, document_id)