from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    workflow_status: Mapped[str] = mapped_column(String(40), default="uploaded")
    current_stage: Mapped[str] = mapped_column(String(40), default="inspection")
    readiness_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DatasetRecord(Base):
    __tablename__ = "dataset_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True
    )
    original_file_name: Mapped[str] = mapped_column(String(255))
    archive_size_bytes: Mapped[int] = mapped_column(BigInteger)
    archive_checksum_sha256: Mapped[str] = mapped_column(String(64))
    extracted_file_count: Mapped[int] = mapped_column(Integer)
    extracted_size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClarificationRecord(Base):
    __tablename__ = "clarifications"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    finding_type: Mapped[str] = mapped_column(String(80))
    file_name: Mapped[str] = mapped_column(String(500))
    affected_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    why_this_matters: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="unanswered")
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecommendationBatch(Base):
    __tablename__ = "recommendation_batches"
    __table_args__ = (
        UniqueConstraint("workspace_id", "generation", name="uq_batch_generation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    generation: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RecommendationRecord(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("batch_id", "recommendation_key", name="uq_recommendation_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_batches.id", ondelete="CASCADE"), index=True
    )
    recommendation_key: Mapped[str] = mapped_column(String(180))
    ordinal: Mapped[int] = mapped_column(Integer)
    finding_type: Mapped[str] = mapped_column(String(80))
    file_name: Mapped[str] = mapped_column(String(500))
    affected_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_title: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str] = mapped_column(Text)
    proposed_action: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    human_approval_required: Mapped[bool] = mapped_column(Boolean)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)


class HumanDecision(Base):
    __tablename__ = "human_decisions"
    __table_args__ = (
        UniqueConstraint("batch_id", "recommendation_key", name="uq_decision_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_batches.id", ondelete="CASCADE"), index=True
    )
    recommendation_key: Mapped[str] = mapped_column(String(180))
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String(500))


Index("ix_workspaces_updated_at", Workspace.updated_at)
