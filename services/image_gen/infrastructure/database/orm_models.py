"""SQLAlchemy ORM models for image_gen service."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GeneratedImageDB(Base):
    __tablename__ = "generated_images"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=False)
    minio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True)
    location_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
