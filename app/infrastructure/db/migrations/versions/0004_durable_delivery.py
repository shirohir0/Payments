"""Durable outbox and gateway idempotency receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0004_durable_delivery"
down_revision = "0003_payment_guarantees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("relay_token", sa.String(36)),
        sa.Column("relay_lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome_uncertain", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_payment_outbox_due", "payment_outbox", ["completed_at", "available_at"])
    # Legacy jobs have neither provider idempotency guarantees nor trustworthy
    # reservations. Quarantine them for reconciliation; never automatically
    # charge again merely because the service was upgraded.
    op.execute("""
        INSERT INTO payment_outbox (payment_id, available_at, completed_at, last_error)
        SELECT id, now(), now(), 'reconciliation_required:legacy_payment_requires_reconciliation' FROM payments
        WHERE status IN ('new', 'processing')
    """)
    op.execute("""
        UPDATE payments SET status = 'processing',
        last_error = 'reconciliation_required:legacy_payment_requires_reconciliation',
        locked_at = NULL, next_retry_at = NULL
        WHERE status IN ('new', 'processing')
    """)
    op.create_table(
        "mock_gateway_receipts",
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "payment_resolutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(200), nullable=False),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # Keep every old task, attempt count and error for accounting review. The
    # new application never consumes this read-only archive.
    op.rename_table("payment_tasks", "legacy_payment_tasks")


def downgrade() -> None:
    has_evidence = op.get_bind().scalar(
        sa.text("""
        SELECT EXISTS (SELECT 1 FROM payment_outbox)
            OR EXISTS (SELECT 1 FROM payment_resolutions)
            OR EXISTS (SELECT 1 FROM mock_gateway_receipts)
    """)
    )
    if has_evidence:
        raise RuntimeError(
            "Refusing downgrade: durable delivery or provider evidence exists. "
            "Keep this schema and deploy a compatible application rollback; "
            "use a reviewed forward migration for schema changes."
        )
    # Renaming preserves the original rows, defaults, sequence, constraints and
    # enum. No historical task metadata is reconstructed or discarded.
    op.rename_table("legacy_payment_tasks", "payment_tasks")
    op.drop_table("payment_resolutions")
    op.drop_table("mock_gateway_receipts")
    op.drop_index("ix_payment_outbox_due", table_name="payment_outbox")
    op.drop_table("payment_outbox")
