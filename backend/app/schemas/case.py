from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated


BusinessName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class CaseCreate(BaseModel):
    business_name: BusinessName
    business_type: str | None = Field(default=None, max_length=100)
    loan_amount: float = Field(gt=0, allow_inf_nan=False)
    loan_purpose: str = Field(min_length=1, max_length=500)
    currency: Literal["INR"] = "INR"
    notes: str | None = Field(default=None, max_length=5000)


class CaseUpdate(BaseModel):
    business_name: BusinessName | None = None
    business_type: str | None = Field(default=None, max_length=100)
    loan_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    loan_purpose: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)


class CaseStatusUpdate(BaseModel):
    status: Literal[
        "created",
        "documents_pending",
        "analysis_pending",
        "investigating",
        "review_pending",
        "completed",
        "cancelled",
    ]


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    business_type: str | None
    loan_amount: float
    loan_purpose: str
    currency: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CaseList(BaseModel):
    items: list[CaseRead]
    total: int
    limit: int
    offset: int