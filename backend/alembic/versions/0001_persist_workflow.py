"""Persist DataQuay workflow metadata.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("workflow_status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=False),
        sa.Column("readiness_status", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_updated_at", "workspaces", ["updated_at"])
    op.create_table(
        "dataset_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("archive_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("archive_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_file_count", sa.Integer(), nullable=False),
        sa.Column("extracted_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_table(
        "clarifications",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("finding_type", sa.String(length=80), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("affected_column", sa.String(length=255), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("why_this_matters", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "question_id"),
    )
    op.create_table(
        "recommendation_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "generation", name="uq_batch_generation"),
    )
    op.create_index("ix_recommendation_batches_workspace_id", "recommendation_batches", ["workspace_id"])
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_key", sa.String(length=180), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("finding_type", sa.String(length=80), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("affected_column", sa.String(length=255), nullable=True),
        sa.Column("short_title", sa.String(length=120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("proposed_action", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("human_approval_required", sa.Boolean(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["recommendation_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "recommendation_key", name="uq_recommendation_key"),
    )
    op.create_index("ix_recommendations_batch_id", "recommendations", ["batch_id"])
    op.create_table(
        "human_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_key", sa.String(length=180), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["recommendation_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "recommendation_key", name="uq_decision_key"),
    )
    op.create_index("ix_human_decisions_batch_id", "human_decisions", ["batch_id"])
    op.create_index("ix_human_decisions_workspace_id", "human_decisions", ["workspace_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_workspace_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_human_decisions_workspace_id", table_name="human_decisions")
    op.drop_index("ix_human_decisions_batch_id", table_name="human_decisions")
    op.drop_table("human_decisions")
    op.drop_index("ix_recommendations_batch_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_recommendation_batches_workspace_id", table_name="recommendation_batches")
    op.drop_table("recommendation_batches")
    op.drop_table("clarifications")
    op.drop_table("dataset_records")
    op.drop_index("ix_workspaces_updated_at", table_name="workspaces")
    op.drop_table("workspaces")
