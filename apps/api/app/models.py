from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class PaymentStatus(StrEnum):
    REQUIRES_PAYMENT = "requires_payment"
    CONFIRMING = "confirming"
    SUCCEEDED = "succeeded"
    EXPIRED = "expired"
    CANCELED = "canceled"
    UNDERPAID = "underpaid"
    OVERPAID = "overpaid"
    FAILED = "failed"
    REORGED = "reorged"


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payments: Mapped[list["PaymentIntent"]] = relationship(back_populates="merchant")


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    __table_args__ = (
        Index("ix_payment_intents_merchant_created", "merchant_id", "created_at"),
        Index("ix_payment_reconciliation_due", "status", "reconcile_next_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(BigInteger)  # Integer USDC base units; never float.
    currency: Mapped[str] = mapped_column(String(8), default="USDC")
    network: Mapped[str] = mapped_column(String(32), default="base-sepolia")
    recipient: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.REQUIRES_PAYMENT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transaction_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reconcile_next_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reconcile_lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reconcile_lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reconcile_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    merchant: Mapped[Merchant] = relationship(back_populates="payments")
    blockchain_transactions: Mapped[list["BlockchainTransaction"]] = relationship(
        back_populates="payment_intent"
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("merchant_id", "key", name="uq_idempotency_merchant_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    payment_intent_id: Mapped[int] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BlockchainTransaction(Base):
    __tablename__ = "blockchain_transactions"
    __table_args__ = (
        UniqueConstraint("chain_id", "transaction_hash", "log_index", name="uq_chain_log"),
        UniqueConstraint("chain_id", "transaction_hash", name="uq_chain_transaction"),
        Index("ix_blockchain_transactions_payment", "payment_intent_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_intent_id: Mapped[int] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="CASCADE")
    )
    chain_id: Mapped[int] = mapped_column(Integer)
    transaction_hash: Mapped[str] = mapped_column(String(66))
    log_index: Mapped[int] = mapped_column(Integer)
    block_number: Mapped[int] = mapped_column(BigInteger)
    block_hash: Mapped[str] = mapped_column(String(66))
    payer: Mapped[str] = mapped_column(String(42))
    recipient: Mapped[str] = mapped_column(String(42))
    token: Mapped[str] = mapped_column(String(42))
    amount: Mapped[int] = mapped_column(BigInteger)
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    verification_status: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reorg_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    payment_intent: Mapped[PaymentIntent] = relationship(back_populates="blockchain_transactions")
