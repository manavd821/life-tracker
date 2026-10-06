import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PRIMARY_CATEGORY, PrimaryCategory
from app.models.user import User


class ActivityLabel(Base):
    __tablename__ = "activity_labels"

    activity_label_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    primary_category: Mapped[PrimaryCategory] = mapped_column(PRIMARY_CATEGORY)
    activity_label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="activity_labels")
    behaviors: Mapped[list["Behavior"]] = relationship(back_populates="activity_label")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="activity_label")  # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "primary_category",
            "activity_label",
            name="uq_activity_labels_user_category_label",
        ),
    )
