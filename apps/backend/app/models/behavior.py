import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.behavior_context_tag_map import BehaviorContextTagMap
from app.models.enums import (
    BEHAVIOR_SOURCE,
    EMOTION_STATE,
    ENERGY_LEVEL,
    ENVIRONMENT,
    FOCUS_STATE,
    PRECISION,
    PRIMARY_CATEGORY,
    BehaviorSource,
    EmotionState,
    EnergyLevel,
    Environment,
    FocusState,
    Precision,
    PrimaryCategory,
)
from app.models.user import User


class Behavior(Base):
    __tablename__ = "behaviors"

    behavior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    primary_category: Mapped[PrimaryCategory] = mapped_column(PRIMARY_CATEGORY)
    activity_label_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("activity_labels.activity_label_id", ondelete="SET NULL"),
        nullable=True,
    )
    energy_level: Mapped[EnergyLevel | None] = mapped_column(
        ENERGY_LEVEL, nullable=True
    )
    emotion_state: Mapped[EmotionState | None] = mapped_column(
        EMOTION_STATE, nullable=True
    )
    focus_state: Mapped[FocusState | None] = mapped_column(FOCUS_STATE, nullable=True)
    environment: Mapped[Environment | None] = mapped_column(ENVIRONMENT, nullable=True)
    precision: Mapped[Precision] = mapped_column(
        PRECISION, default=Precision.HIGH, server_default=Precision.HIGH.value
    )
    source: Mapped[BehaviorSource] = mapped_column(
        BEHAVIOR_SOURCE, default=BehaviorSource.manual, server_default=BehaviorSource.manual.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="behaviors")
    activity_label: Mapped["ActivityLabel | None"] = relationship(  # noqa: F821
        back_populates="behaviors"
    )
    context_tags: Mapped[list["BehaviorContextTag"]] = relationship(  # noqa: F821
        secondary=BehaviorContextTagMap.__table__,
        back_populates="behaviors",
    )

    __table_args__ = (
        Index("ix_behaviors_user_start_time", "user_id", "start_time"),
    )

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)
