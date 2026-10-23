"""Prevent one transaction hash from settling multiple payment intents."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003_unique_chain_transactions"
down_revision = "0002_blockchain_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    constraints = inspector.get_unique_constraints("blockchain_transactions")
    if any(constraint.get("name") == "uq_chain_transaction" for constraint in constraints):
        return

    duplicate = bind.execute(
        sa.text(
            "SELECT chain_id, transaction_hash "
            "FROM blockchain_transactions "
            "GROUP BY chain_id, transaction_hash HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Cannot add uq_chain_transaction: existing transaction hashes link to multiple "
            "payment events. Review blockchain_transactions before retrying this migration."
        )

    with op.batch_alter_table("blockchain_transactions") as batch:
        batch.create_unique_constraint("uq_chain_transaction", ["chain_id", "transaction_hash"])


def downgrade() -> None:
    constraints = inspect(op.get_bind()).get_unique_constraints("blockchain_transactions")
    if any(constraint.get("name") == "uq_chain_transaction" for constraint in constraints):
        with op.batch_alter_table("blockchain_transactions") as batch:
            batch.drop_constraint("uq_chain_transaction", type_="unique")
