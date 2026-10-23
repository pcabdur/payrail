"""Add durable payment reconciliation scheduling and reorg audit fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_payment_reconciliation"
down_revision = "0003_unique_chain_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    payment_columns = {column["name"] for column in inspector.get_columns("payment_intents")}
    with op.batch_alter_table("payment_intents") as batch:
        if "reconcile_next_at" not in payment_columns:
            batch.add_column(sa.Column("reconcile_next_at", sa.DateTime(timezone=True)))
        if "reconcile_lease_until" not in payment_columns:
            batch.add_column(sa.Column("reconcile_lease_until", sa.DateTime(timezone=True)))
        if "reconcile_lease_token" not in payment_columns:
            batch.add_column(sa.Column("reconcile_lease_token", sa.String(length=36)))
        if "reconcile_attempts" not in payment_columns:
            batch.add_column(
                sa.Column("reconcile_attempts", sa.Integer(), server_default="0", nullable=False)
            )
    inspector = inspect(op.get_bind())
    if not any(
        index["name"] == "ix_payment_reconciliation_due"
        for index in inspector.get_indexes("payment_intents")
    ):
        op.create_index(
            "ix_payment_reconciliation_due",
            "payment_intents",
            ["status", "reconcile_next_at"],
        )

    transaction_columns = {
        column["name"] for column in inspector.get_columns("blockchain_transactions")
    }
    with op.batch_alter_table("blockchain_transactions") as batch:
        if "last_checked_at" not in transaction_columns:
            batch.add_column(sa.Column("last_checked_at", sa.DateTime(timezone=True)))
        if "reorg_detected_at" not in transaction_columns:
            batch.add_column(sa.Column("reorg_detected_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if any(
        index["name"] == "ix_payment_reconciliation_due"
        for index in inspector.get_indexes("payment_intents")
    ):
        op.drop_index("ix_payment_reconciliation_due", table_name="payment_intents")
    with op.batch_alter_table("blockchain_transactions") as batch:
        batch.drop_column("reorg_detected_at")
        batch.drop_column("last_checked_at")
    with op.batch_alter_table("payment_intents") as batch:
        batch.drop_column("reconcile_attempts")
        batch.drop_column("reconcile_lease_token")
        batch.drop_column("reconcile_lease_until")
        batch.drop_column("reconcile_next_at")
