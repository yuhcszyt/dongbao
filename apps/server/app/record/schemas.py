from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

RecordType = Literal["feeding", "complementary_food", "sleep", "stool", "diaper", "crying", "growth", "vaccine", "medication", "custom"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class FeedingPayload(StrictModel):
    kind: Literal["feeding"]
    feeding_type: Literal["breast", "formula", "mixed", "unknown"] = "unknown"
    amount_ml: int | None = Field(default=None, ge=0, le=3000)

class FoodPayload(StrictModel):
    kind: Literal["complementary_food"]
    food_name: str = Field(min_length=1, max_length=100)
    amount_text: str | None = Field(default=None, max_length=100)

class SleepPayload(StrictModel):
    kind: Literal["sleep"]
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)

    @model_validator(mode="after")
    def valid_period(self):
        if self.duration_minutes is None and not (self.start_at and self.end_at):
            raise ValueError("请填写睡眠时长或起止时间")
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("睡眠结束时间不能早于开始时间")
        return self

class StoolPayload(StrictModel):
    kind: Literal["stool"]
    color: str = Field(min_length=1, max_length=40)
    consistency: str = Field(min_length=1, max_length=40)

class DiaperPayload(StrictModel):
    kind: Literal["diaper"]
    content: str = Field(min_length=1, max_length=100)

class CryingPayload(StrictModel):
    kind: Literal["crying"]
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    description: str | None = Field(default=None, max_length=500)

class GrowthPayload(StrictModel):
    kind: Literal["growth"]
    height_cm: Decimal | None = Field(default=None, gt=0, le=300)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=300)

    @model_validator(mode="after")
    def one_value(self):
        if self.height_cm is None and self.weight_kg is None:
            raise ValueError("身高或体重至少填写一项")
        return self

class VaccinePayload(StrictModel):
    kind: Literal["vaccine"]
    name: str = Field(min_length=1, max_length=100)
    dose: str | None = Field(default=None, max_length=50)

class MedicationPayload(StrictModel):
    kind: Literal["medication"]
    name: str = Field(min_length=1, max_length=100)
    dosage_text: str | None = Field(default=None, max_length=100)

class CustomPayload(StrictModel):
    kind: Literal["custom"]
    title: str = Field(min_length=1, max_length=100)
    details: str | None = Field(default=None, max_length=1000)

Payload = Annotated[Union[FeedingPayload, FoodPayload, SleepPayload, StoolPayload, DiaperPayload, CryingPayload, GrowthPayload, VaccinePayload, MedicationPayload, CustomPayload], Field(discriminator="kind")]
payload_adapter = TypeAdapter(Payload)

class BabyCreate(StrictModel):
    nickname: str = Field(min_length=1, max_length=30)
    birth_date: date | None = Field(default=None)
    gender: Literal["male", "female", "unknown"] = "unknown"

    @model_validator(mode="after")
    def birthday_not_future(self):
        if self.birth_date is not None and self.birth_date > date.today():
            raise ValueError("生日不能晚于今天")
        return self

class BabyUpdate(BabyCreate):
    pass

class BabyOut(BabyCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RecordCreate(StrictModel):
    record_type: RecordType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Payload
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def matching_kind(self):
        if self.record_type != self.payload.kind:
            raise ValueError("record_type 与 payload.kind 必须一致")
        return self

class RecordUpdate(StrictModel):
    occurred_at: datetime
    payload: Payload
    note: str | None = Field(default=None, max_length=2000)

class MediaOut(BaseModel):
    id: UUID
    baby_id: UUID
    media_type: Literal["audio", "image"]
    mime_type: str
    size_bytes: int
    duration_ms: int | None
    url: str

class RecordOut(BaseModel):
    id: UUID
    baby_id: UUID
    record_type: RecordType
    occurred_at: datetime
    source: Literal["manual", "voice", "photo", "system"]
    payload: dict
    note: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    media: list[MediaOut] = Field(default_factory=list)
    transcript: str | None = None
    model_config = ConfigDict(from_attributes=True)

class DraftRequest(StrictModel):
    baby_id: UUID
    media_id: UUID
    occurred_at: datetime | None = None

class DraftOut(BaseModel):
    id: UUID
    baby_id: UUID
    media_id: UUID | None
    record_type: RecordType | None
    occurred_at: datetime | None
    payload: dict
    note: str | None
    missing_fields: list[str]
    source: Literal["voice", "photo", "manual"]
    transcript: str | None
    recognition_warnings: list[str]
    status: Literal["captured", "processing", "draft", "confirmed", "saved"]
    model_config = ConfigDict(from_attributes=True)

class DraftConfirm(RecordCreate):
    pass

class DailySummary(BaseModel):
    date: date
    timezone: str
    feeding_ml: int
    sleep_minutes: int
    diaper_count: int
    complementary_food_count: int
