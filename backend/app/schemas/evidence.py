
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EvidenceCreate(BaseModel):
    claim: str = Field(min_length=1, max_length=5000)
    source_name: str = Field(min_length=1, max_length=255)
    source_url: HttpUrl
    excerpt: str | None = Field(default=None, max_length=20000)
    entity_name: str | None = Field(default=None, max_length=255)
    expected_entity: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    claim: str
    source_name: str
    source_url: str
    source_type: str
    published_at: datetime | None
    retrieved_at: datetime
    excerpt: str | None
    entity_name: str | None
    relevance_score: float | None
    credibility_score: float | None
    validation_status: str
    validation_reason: str | None
    created_at: datetime


class EvidenceList(BaseModel):
    items: list[EvidenceRead]
    total: int

class EvidenceCollectionRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    expected_entity: str = Field(min_length=2, max_length=200)
    max_results: int = Field(default=5, ge=1, le=10)

