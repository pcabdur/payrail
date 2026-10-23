"""Persist verified PaymentRouter events and widen payment amounts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_blockchain_transactions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not any(
        column["name"] == "amount" and isinstance(column["type"], sa.BigInteger)
        for column in inspector.get_columns("payment_intents")
    ):
        with op.batch_alter_table("payment_intents") as batch_op:
            batch_op.alter_column(
                "amount",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=False,
            )

    if not inspector.has_table("blockchain_transactions"):
        op.create_table(
            "blockchain_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "payment_intent_id",
                sa.Integer(),
                sa.ForeignKey("payment_intents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("chain_id", sa.Integer(), nullable=False),
            sa.Column("transaction_hash", sa.String(length=66), nullable=False),
            sa.Column("log_index", sa.Integer(), nullable=False),
            sa.Column("block_number", sa.BigInteger(), nullable=False),
            sa.Column("block_hash", sa.String(length=66), nullable=False),
            sa.Column("payer", sa.String(length=42), nullable=False),
            sa.Column("recipient", sa.String(length=42), nullable=False),
            sa.Column("token", sa.String(length=42), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("confirmations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("verification_status", sa.String(length=32), nullable=False),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("chain_id", "transaction_hash", "log_index", name="uq_chain_log"),
        )
        op.create_index(
            "ix_blockchain_transactions_payment",
            "blockchain_transactions",
            ["payment_intent_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if inspect(bind).has_table("blockchain_transactions"):
        op.drop_index("ix_blockchain_transactions_payment", table_name="blockchain_transactions")
        op.drop_table("blockchain_transactions")
    # Amounts stay BIGINT on downgrade to avoid truncating existing USDC base units.
