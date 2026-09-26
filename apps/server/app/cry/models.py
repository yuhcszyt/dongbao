from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from ..record.database import Base
from ..record.models import JsonType, now


class CryAnalysis(Base):
    __tablename__ = "cry_analyses"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    baby_id: Mapped[UUID] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, unique=True)
    result: Mapped[dict] = mapped_column(JsonType)
    explanation: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
