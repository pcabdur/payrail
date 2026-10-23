import secrets
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from app.database import Base
from app.models import BlockchainTransaction, Merchant, PaymentIntent, PaymentStatus
from app.services.chain import (
    ChainUnavailable,
    InvalidChainPayment,
    PaymentObservation,
    PendingTransaction,
    RevertedTransaction,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from payrail_worker.worker import claim_due_payments, run_reconciliation_batch

PAYMENT_HASH = "0x" + "a" * 64
BLOCK_HASH = "0x" + "b" * 64
PAYER = "0x" + "1" * 40
RECIPIENT = "0x" + "2" * 40
TOKEN = "0x" + "3" * 40


@pytest.fixture
def sessions() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def add_payment(
    sessions: sessionmaker[Session],
    *,
    status: str = PaymentStatus.CONFIRMING.value,
    with_record: bool = False,
) -> int:
    with sessions() as db:
        merchant = Merchant(name="Worker Test", api_key_hash=secrets.token_hex(32))
        db.add(merchant)
        db.flush()
        payment = PaymentIntent(
            public_id=f"pi_worker_{secrets.token_hex(4)}",
            merchant_id=merchant.id,
            amount=1_000_000,
            currency="USDC",
            network="base-sepolia",
            recipient=RECIPIENT,
            status=status,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            transaction_hash=PAYMENT_HASH,
        )
        db.add(payment)
        db.flush()
        if with_record:
            db.add(
                BlockchainTransaction(
                    payment_intent_id=payment.id,
                    chain_id=84532,
                    transaction_hash=PAYMENT_HASH,
                    log_index=0,
                    block_number=10,
                    block_hash=BLOCK_HASH,
                    payer=PAYER,
                    recipient=RECIPIENT,
                    token=TOKEN,
                    amount=1_000_000,
                    confirmations=2,
                    verification_status=PaymentStatus.SUCCEEDED.value,
                )
            )
        db.commit()
        return payment.id


class FakeVerifier:
    minimum_confirmations = 2

    def __init__(
        self,
        *,
        confirmations: int = 1,
        outcome: str = "ok",
        block_hash: str = BLOCK_HASH,
        block_number: int = 10,
        tx_in_canonical_block: bool = True,
    ):
        self.confirmations = confirmations
        self.outcome = outcome
        self.block_hash = block_hash
        self.block_number = block_number
        self.tx_in_canonical_block = tx_in_canonical_block
        self.verify_calls = 0

    def verify(
        self, public_id: str, transaction_hash: str, expected_recipient: str
    ) -> PaymentObservation:
        self.verify_calls += 1
        if self.outcome == "pending":
            raise PendingTransaction("not yet mined")
        if self.outcome == "rpc":
            raise ChainUnavailable("provider unavailable")
        if self.outcome == "invalid":
            raise InvalidChainPayment("event mismatch")
        if self.outcome == "reverted":
            raise RevertedTransaction("receipt reverted")
        if self.outcome == "canonical_mismatch":
            from app.services.chain import CanonicalBlockMismatch

            raise CanonicalBlockMismatch("block mismatch")
        return PaymentObservation(
            chain_id=84532,
            transaction_hash=transaction_hash,
            log_index=0,
            block_number=self.block_number,
            block_hash=self.block_hash,
            block_timestamp=datetime.now(UTC),
            payer=PAYER,
            recipient=expected_recipient,
            token=TOKEN,
            amount=1_000_000,
            confirmations=self.confirmations,
        )

    def canonical_block_hash(self, block_number: int) -> str:
        if self.outcome == "rpc":
            raise ChainUnavailable("provider unavailable")
        return self.block_hash

    def canonical_block_contains_transaction(
        self, block_number: int, transaction_hash: str
    ) -> bool:
        return self.tx_in_canonical_block


def run(sessions: sessionmaker[Session], verifier: FakeVerifier) -> dict[str, int]:
    return run_reconciliation_batch(
        sessions,
        lambda: verifier,
        interval=5,
        batch_size=10,
        lease_seconds=20,
    )


def make_due(sessions: sessionmaker[Session], payment_id: int) -> None:
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment
        payment.reconcile_next_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()


def test_confirmation_threshold_and_repeated_processing_are_idempotent(sessions) -> None:
    payment_id = add_payment(sessions)
    verifier = FakeVerifier(confirmations=1)

    assert run(sessions, verifier)["confirming"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.CONFIRMING.value
        assert db.scalar(select(func.count()).select_from(BlockchainTransaction)) == 1

    make_due(sessions, payment_id)
    verifier.confirmations = 2
    assert run(sessions, verifier)[PaymentStatus.SUCCEEDED.value] == 1
    make_due(sessions, payment_id)
    assert run(sessions, verifier)[PaymentStatus.SUCCEEDED.value] == 1
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(BlockchainTransaction)) == 1


def test_missing_receipt_is_retryable_and_claim_lease_prevents_duplicate_work(sessions) -> None:
    payment_id = add_payment(sessions)
    first = claim_due_payments(sessions, batch_size=10, lease_seconds=30)
    second = claim_due_payments(sessions, batch_size=10, lease_seconds=30)
    assert len(first) == 1
    assert second == []
    verifier = FakeVerifier(outcome="pending")
    assert run(sessions, verifier)["claimed"] == 0  # The first claim still owns the lease.
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.CONFIRMING.value

    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment
        payment.reconcile_lease_token = None
        payment.reconcile_lease_until = None
        payment.reconcile_next_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert run(sessions, verifier)["receipt_pending"] == 1


def test_rpc_timeout_does_not_downgrade_confirmed_payment(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    assert run(sessions, FakeVerifier(outcome="rpc"))["deferred"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.SUCCEEDED.value


def test_missing_receipt_with_unchanged_block_is_treated_as_rpc_inconsistency(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    verifier = FakeVerifier(outcome="pending", block_hash=BLOCK_HASH)
    assert run(sessions, verifier)["receipt_pending"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.SUCCEEDED.value


def test_temporary_rpc_failure_recovers_without_duplicate_accounting(sessions) -> None:
    payment_id = add_payment(sessions)
    verifier = FakeVerifier(outcome="rpc")
    assert run(sessions, verifier)["deferred"] == 1
    make_due(sessions, payment_id)
    verifier.outcome = "ok"
    verifier.confirmations = 2
    assert run(sessions, verifier)[PaymentStatus.SUCCEEDED.value] == 1
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(BlockchainTransaction)) == 1


def test_changed_canonical_block_marks_reorg_and_recovery_reconfirms(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    changed_hash = "0x" + "c" * 64
    verifier = FakeVerifier(outcome="pending", block_hash=changed_hash)
    assert run(sessions, verifier)["reorged"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        record = db.scalar(select(BlockchainTransaction))
        assert payment and payment.status == PaymentStatus.REORGED.value
        assert record and record.verification_status == PaymentStatus.REORGED.value
        assert record.reorg_detected_at is not None

    make_due(sessions, payment_id)
    verifier.outcome = "ok"
    verifier.confirmations = 2
    assert run(sessions, verifier)["confirming"] == 1
    make_due(sessions, payment_id)
    assert run(sessions, verifier)[PaymentStatus.SUCCEEDED.value] == 1
    with sessions() as db:
        record = db.scalar(select(BlockchainTransaction))
        assert record and record.block_hash == changed_hash
        assert record.reorg_detected_at is not None
        assert db.scalar(select(func.count()).select_from(BlockchainTransaction)) == 1


def test_invalid_event_clears_unverified_hash_and_reverted_receipt_fails(sessions) -> None:
    invalid_id = add_payment(sessions)
    assert run(sessions, FakeVerifier(outcome="invalid"))["invalid_evidence"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, invalid_id)
        assert payment and payment.transaction_hash is None
        assert payment.status == PaymentStatus.REQUIRES_PAYMENT.value

    reverted_id = add_payment(sessions)
    assert run(sessions, FakeVerifier(outcome="reverted"))["failed"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, reverted_id)
        assert payment and payment.status == PaymentStatus.FAILED.value


def test_pending_receipt_with_changed_block_is_a_reorg(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    verifier = FakeVerifier(outcome="pending", block_hash="0x" + "d" * 64)
    assert run(sessions, verifier)["reorged"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.REORGED.value


def test_missing_transaction_from_same_height_canonical_block_is_reorg(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    verifier = FakeVerifier(outcome="pending", tx_in_canonical_block=False)
    assert run(sessions, verifier)["reorged"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.REORGED.value


def test_reincluded_transaction_reenters_confirmation_before_final_state(sessions) -> None:
    payment_id = add_payment(sessions, status=PaymentStatus.SUCCEEDED.value, with_record=True)
    verifier = FakeVerifier(block_hash="0x" + "e" * 64, block_number=11, confirmations=5)
    assert run(sessions, verifier)["confirming"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        record = db.scalar(select(BlockchainTransaction))
        assert payment and payment.status == PaymentStatus.CONFIRMING.value
        assert record and record.reorg_detected_at is not None
        payment.reconcile_next_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert run(sessions, verifier)[PaymentStatus.SUCCEEDED.value] == 1


def test_parallel_claim_attempts_do_not_issue_two_leases(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-claims.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 10},
        pool_size=4,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    payment_id = add_payment(factory)
    start = Barrier(2)

    def claim():
        start.wait()
        try:
            return claim_due_payments(factory, batch_size=1, lease_seconds=30)
        except OperationalError:
            # SQLite lacks PostgreSQL row locks; a write conflict must not create two leases.
            return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim(), range(2)))
    assert sum(len(items) for items in claimed) == 1
    with factory() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.reconcile_lease_token
    Base.metadata.drop_all(engine)
    engine.dispose()
