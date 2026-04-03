"""SQLAlchemy ORM models for the pdf_ingestion service."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class PdfSourceDB(Base):
    """ORM mapping for the pdf_sources table."""

    __tablename__ = "pdf_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    title = Column(Text, nullable=False)
    rpg_system = Column(Text, nullable=True)
    source_type = Column(Text, nullable=True)
    filename = Column(Text, nullable=False)
    minio_path = Column(Text, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeChunkDB(Base):
    """
    ORM mapping for knowledge_chunks (without the pgvector embedding column).

    The embedding column (vector(1536)) is managed via raw SQL in the repository
    to avoid requiring the pgvector SQLAlchemy extension at ORM level.
    """

    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    source_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    rpg_system = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
