from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskContextTagMap(Base):
    __tablename__ = "task_context_tag_map"

    task_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        primary_key=True,
    )
    behavior_context_tag_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("behavior_context_tags.behavior_context_tag_id", ondelete="CASCADE"),
        primary_key=True,
    )