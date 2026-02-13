"""initial_schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-08 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём базовую таблицу пользователей.
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    # Типы ENUM для платежей и транзакций.
    # Используем idempotent-DDL в Postgres через PL/pgSQL‑блоки,
    # чтобы миграция не падала, если тип уже существует.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymentstatus') THEN
                CREATE TYPE paymentstatus AS ENUM ('new', 'processing', 'success', 'failed');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transactiontype') THEN
                CREATE TYPE transactiontype AS ENUM ('deposit', 'withdraw');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transactionstatus') THEN
                CREATE TYPE transactionstatus AS ENUM ('success', 'failed', 'processing');
            END IF;
        END $$;
        """
    )

    payment_status_enum_no_create = postgresql.ENUM(
        "new",
        "processing",
        "success",
        "failed",
        name="paymentstatus",
        create_type=False,
    )
    transaction_type_enum_no_create = postgresql.ENUM(
        "deposit",
        "withdraw",
        name="transactiontype",
        create_type=False,
    )
    transaction_status_enum_no_create = postgresql.ENUM(
        "success",
        "failed",
        "processing",
        name="transactionstatus",
        create_type=False,
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", payment_status_enum_no_create, nullable=False, server_default="new"),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_payments_user_idempotency_key"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission", sa.Numeric(12, 2), nullable=False),
        sa.Column("type", transaction_type_enum_no_create, nullable=False),
        sa.Column("status", transaction_status_enum_no_create, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("payments")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS transactionstatus")
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
