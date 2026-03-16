"""Exact amounts, wallet reservations and one transaction per payment."""

import sqlalchemy as sa
from alembic import op

revision = "0003_payment_guarantees"
down_revision = "0002_add_task_and_dlq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stop on inconsistent legacy records. Choosing an operation or deleting an
    # extra transaction here would silently change financial history.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT payment_id FROM transactions
                WHERE payment_id IS NOT NULL
                GROUP BY payment_id HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Resolve duplicate payment transactions before migration';
            END IF;
            IF EXISTS (
                SELECT 1 FROM payments p
                WHERE NOT EXISTS (SELECT 1 FROM transactions t WHERE t.payment_id = p.id)
            ) THEN
                RAISE EXCEPTION 'Reconcile payments without transactions before migration';
            END IF;
        END $$
    """)
    op.add_column(
        "users",
        sa.Column("reserved_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("payments", sa.Column("operation", sa.String(20), nullable=True))
    op.add_column(
        "payments",
        sa.Column("funds_reserved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("""
        UPDATE payments p SET operation = t.type::text
        FROM transactions t WHERE t.payment_id = p.id
    """)
    op.alter_column("payments", "operation", nullable=False)
    op.create_check_constraint("ck_users_balance_nonnegative", "users", "balance >= 0")
    op.create_check_constraint("ck_users_reserved_nonnegative", "users", "reserved_balance >= 0")
    op.create_check_constraint(
        "ck_users_reservation_within_balance", "users", "reserved_balance <= balance"
    )
    op.create_check_constraint("ck_payments_amount_positive", "payments", "amount > 0")
    op.create_check_constraint("ck_payments_commission_nonnegative", "payments", "commission >= 0")
    op.create_check_constraint(
        "ck_payments_operation", "payments", "operation IN ('deposit', 'withdraw')"
    )
    op.create_check_constraint(
        "ck_payments_reservation_operation",
        "payments",
        "NOT funds_reserved OR operation = 'withdraw'",
    )
    op.create_check_constraint("ck_transactions_amount_positive", "transactions", "amount > 0")
    op.create_check_constraint(
        "ck_transactions_commission_nonnegative", "transactions", "commission >= 0"
    )
    op.create_unique_constraint("uq_transactions_payment_id", "transactions", ["payment_id"])
    op.create_index("ix_payments_status_retry", "payments", ["status", "next_retry_at"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])


def downgrade() -> None:
    # An application rollback must never discard outstanding wallet holds.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM users WHERE reserved_balance <> 0) THEN
                RAISE EXCEPTION 'Reconcile outstanding wallet reservations before downgrade';
            END IF;
        END $$
    """)
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_status_retry", table_name="payments")
    op.drop_constraint("uq_transactions_payment_id", "transactions", type_="unique")
    for table, name in (
        ("transactions", "ck_transactions_commission_nonnegative"),
        ("transactions", "ck_transactions_amount_positive"),
        ("payments", "ck_payments_reservation_operation"),
        ("payments", "ck_payments_operation"),
        ("payments", "ck_payments_commission_nonnegative"),
        ("payments", "ck_payments_amount_positive"),
        ("users", "ck_users_reservation_within_balance"),
        ("users", "ck_users_reserved_nonnegative"),
        ("users", "ck_users_balance_nonnegative"),
    ):
        op.drop_constraint(name, table, type_="check")
    op.drop_column("payments", "funds_reserved")
    op.drop_column("payments", "operation")
    op.drop_column("users", "reserved_balance")
