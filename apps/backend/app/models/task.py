import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PRIMARY_CATEGORY, PrimaryCategory
from app.models.task_context_tag_map import TaskContextTagMap
from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    primary_category: Mapped[PrimaryCategory] = mapped_column(PRIMARY_CATEGORY)
    activity_label_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("activity_labels.activity_label_id", ondelete="SET NULL"),
        nullable=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="tasks")
    activity_label: Mapped["ActivityLabel | None"] = relationship(  # noqa: F821
        back_populates="tasks"
    )
    context_tags: Mapped[list["BehaviorContextTag"]] = relationship(  # noqa: F821
        secondary=TaskContextTagMap.__table__,
        back_populates="tasks",
    )

    __table_args__ = (
        Index("ix_tasks_user_start_time", "user_id", "start_time"),
    )

    @property
    def planned_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)