from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    original_filename: str
    document_type: str
    content_type: str
    file_size: int
    sha256: str
    status: str
    extracted_text: str | None
    extraction_error: str | None
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int