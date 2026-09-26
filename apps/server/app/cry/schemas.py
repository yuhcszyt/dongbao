from typing import Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

CryCategory = Literal["hungry", "discomfort", "tired", "belly_pain", "burping"]
CryPossibility = Literal["较可能", "有可能", "可能性较低"]


class CryAnalysisRequest(BaseModel):
    baby_id: UUID
    media_id: UUID


class CryCandidate(BaseModel):
    category: CryCategory
    label: str
    score: float = Field(ge=0, le=1)
    possibility: CryPossibility


class CryAnalysisResponse(BaseModel):
    id: UUID | None = None
    baby_id: UUID | None = None
    created_at: datetime | None = None
    explanation: dict | None = None
    status: Literal["experimental", "uncertain"]
    primary_category: CryCategory | None
    summary: str
    candidates: list[CryCandidate]
    model_id: str
    model_revision: str
    disclaimer: str
