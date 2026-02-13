"""add_task_and_dlq_tables

Revision ID: 0002_add_task_and_dlq
Revises: 0001_initial
Create Date: 2026-02-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_add_task_and_dlq"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymenttaskstatus') THEN
                CREATE TYPE paymenttaskstatus AS ENUM ('new', 'processing', 'done', 'failed');
            END IF;
        END $$;
        """
    )

    payment_task_status_enum = postgresql.ENUM(
        "new",
        "processing",
        "done",
        "failed",
        name="paymenttaskstatus",
        create_type=False,
    )

    op.create_table(
        "payment_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", payment_task_status_enum, nullable=False, server_default="new"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("payment_id", name="uq_payment_tasks_payment_id"),
    )

    op.create_table(
        "payment_dlq",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_type", sa.String(length=20), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("payment_id", name="uq_payment_dlq_payment_id"),
    )


def downgrade() -> None:
    op.drop_table("payment_dlq")
    op.drop_table("payment_tasks")
    op.execute("DROP TYPE IF EXISTS paymenttaskstatus")
