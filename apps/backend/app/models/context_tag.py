import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.behavior_context_tag_map import BehaviorContextTagMap
from app.models.enums import PRIMARY_CATEGORY, PrimaryCategory
from app.models.user import User


class BehaviorContextTag(Base):
    __tablename__ = "behavior_context_tags"

    behavior_context_tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    primary_category: Mapped[PrimaryCategory] = mapped_column(PRIMARY_CATEGORY)
    context_tag: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="context_tags")
    behaviors: Mapped[list["Behavior"]] = relationship(  # noqa: F821
        secondary=BehaviorContextTagMap.__table__,
        back_populates="context_tags",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "primary_category",
            "context_tag",
            name="uq_context_tags_user_category_tag",
        ),
    )
