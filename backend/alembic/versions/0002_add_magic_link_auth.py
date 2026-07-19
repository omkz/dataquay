"""Add Auth.js magic-link identities and workspace ownership.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("emailVerified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("userId", sa.Integer(), nullable=False),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sessionToken", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["userId"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sessionToken", name="uq_sessions_session_token"),
    )
    op.create_index("ix_sessions_userId", "sessions", ["userId"])
    op.create_table(
        "verification_token",
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("identifier", "token"),
    )

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_workspaces_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_workspaces_owner_id", ["owner_id"])


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_index("ix_workspaces_owner_id")
        batch_op.drop_constraint(
            "fk_workspaces_owner_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("owner_id")

    op.drop_table("verification_token")
    op.drop_index("ix_sessions_userId", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
