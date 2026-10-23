"""ARQ-driven periodic confirmation and canonical-chain reconciliation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from logging import LogRecord
from typing import Any

from app.database import SessionLocal
from app.models import BlockchainTransaction, PaymentIntent, PaymentStatus
from app.services.chain import (
    BASE_SEPOLIA_CHAIN_ID,
    CanonicalBlockMismatch,
    ChainConfigurationError,
    ChainUnavailable,
    InvalidChainPayment,
    PaymentVerifier,
    PendingTransaction,
    RevertedTransaction,
)
from app.services.payments import record_verified_payment
from arq.connections import RedisSettings
from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("payrail.worker")
RECONCILABLE_STATUSES = (
    PaymentStatus.CONFIRMING.value,
    PaymentStatus.SUCCEEDED.value,
    PaymentStatus.UNDERPAID.value,
    PaymentStatus.OVERPAID.value,
    PaymentStatus.EXPIRED.value,
    PaymentStatus.REORGED.value,
)
MAX_BATCH_SIZE = 5
MAX_BACKOFF_SECONDS = 300
MAX_RPC_CONCURRENCY = 5


class JsonFormatter(logging.Formatter):
    """Emit structured logs without RPC URLs, credentials, or full transaction hashes."""

    def format(self, record: LogRecord) -> str:
        fields = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
        }
        for key in ("payment_id", "result", "count", "duration_ms", "error_type"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def _config_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _retry_delay(interval: int, attempts: int) -> int:
    return min(interval * (2 ** min(max(attempts - 1, 0), 5)), MAX_BACKOFF_SECONDS)


def claim_due_payments(
    session_factory: sessionmaker[Session],
    *,
    batch_size: int,
    lease_seconds: int,
) -> list[tuple[int, str]]:
    """Claim due rows using database locks and a lease token, then commit before RPC work."""
    now = datetime.now(UTC)
    claimed: list[tuple[int, str]] = []
    with session_factory() as db:
        rows = list(
            db.scalars(
                select(PaymentIntent)
                .where(
                    PaymentIntent.status.in_(RECONCILABLE_STATUSES),
                    PaymentIntent.transaction_hash.is_not(None),
                    or_(
                        PaymentIntent.reconcile_next_at.is_(None),
                        PaymentIntent.reconcile_next_at <= now,
                    ),
                    or_(
                        PaymentIntent.reconcile_lease_until.is_(None),
                        PaymentIntent.reconcile_lease_until <= now,
                    ),
                )
                .order_by(PaymentIntent.reconcile_next_at, PaymentIntent.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for payment in rows:
            lease_token = secrets.token_hex(18)
            result = db.execute(
                update(PaymentIntent)
                .where(
                    PaymentIntent.id == payment.id,
                    or_(
                        PaymentIntent.reconcile_lease_until.is_(None),
                        PaymentIntent.reconcile_lease_until <= now,
                    ),
                    or_(
                        PaymentIntent.reconcile_next_at.is_(None),
                        PaymentIntent.reconcile_next_at <= now,
                    ),
                )
                .values(
                    reconcile_lease_token=lease_token,
                    reconcile_lease_until=now + timedelta(seconds=lease_seconds),
                    reconcile_attempts=case(
                        (
                            PaymentIntent.reconcile_attempts < 31,
                            PaymentIntent.reconcile_attempts + 1,
                        ),
                        else_=31,
                    ),
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                claimed.append((payment.id, lease_token))
        db.commit()
    return claimed


def _owns_lease(db: Session, payment_id: int, lease_token: str) -> bool:
    """Atomically revalidate and lock a lease before applying any RPC-derived state."""
    result = db.execute(
        update(PaymentIntent)
        .where(
            PaymentIntent.id == payment_id,
            PaymentIntent.reconcile_lease_token == lease_token,
        )
        .values(reconcile_lease_token=lease_token)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _release_claim(
    db: Session,
    payment: PaymentIntent,
    lease_token: str,
    interval: int,
    *,
    delay_seconds: int | None = None,
) -> None:
    if not _owns_lease(db, payment.id, lease_token):
        return
    payment.reconcile_next_at = datetime.now(UTC) + timedelta(
        seconds=delay_seconds or _retry_delay(interval, payment.reconcile_attempts)
    )
    payment.reconcile_lease_token = None
    payment.reconcile_lease_until = None


def _mark_reorg(
    db: Session,
    payment: PaymentIntent,
    record: BlockchainTransaction,
    lease_token: str,
    interval: int,
) -> None:
    if not _owns_lease(db, payment.id, lease_token):
        db.rollback()
        return
    now = datetime.now(UTC)
    newly_detected = payment.status != PaymentStatus.REORGED.value
    payment.status = PaymentStatus.REORGED.value
    payment.reconcile_next_at = now + timedelta(seconds=interval)
    payment.reconcile_lease_token = None
    payment.reconcile_lease_until = None
    record.verification_status = PaymentStatus.REORGED.value
    record.confirmations = 0
    record.last_checked_at = now
    record.reorg_detected_at = record.reorg_detected_at or now
    db.commit()
    if newly_detected:
        logger.error(
            "Previously observed payment is no longer canonical; reconcile merchant fulfillment",
            extra={"event": "payment_reorg_detected", "payment_id": payment.public_id},
        )


def _recorded_transaction_is_orphaned(
    verifier: PaymentVerifier, record: BlockchainTransaction
) -> bool:
    canonical_hash = verifier.canonical_block_hash(record.block_number)
    if canonical_hash.lower() != record.block_hash.lower():
        return True
    return not verifier.canonical_block_contains_transaction(
        record.block_number, record.transaction_hash
    )


def reconcile_claim(
    session_factory: sessionmaker[Session],
    payment_id: int,
    lease_token: str,
    verifier: PaymentVerifier,
    *,
    interval: int,
) -> str:
    """Reconcile one leased payment; transient RPC results never change payment finality."""
    with session_factory() as db:
        payment = db.scalar(select(PaymentIntent).where(PaymentIntent.id == payment_id))
        if payment is None or payment.reconcile_lease_token != lease_token:
            return "lease_lost"
        if not payment.transaction_hash:
            _release_claim(db, payment, lease_token, interval)
            db.commit()
            return "missing_hash"

        record = db.scalar(
            select(BlockchainTransaction).where(
                BlockchainTransaction.payment_intent_id == payment.id
            )
        )
        try:
            observation = verifier.verify(
                payment.public_id, payment.transaction_hash, payment.recipient
            )
            if not _owns_lease(db, payment.id, lease_token):
                db.rollback()
                return "lease_lost"
            if observation.chain_id != BASE_SEPOLIA_CHAIN_ID:
                raise InvalidChainPayment("Verifier returned an unexpected chain")
            previous_location = (record.block_number, record.block_hash.lower()) if record else None
            stored_record, _, final_status = record_verified_payment(
                db, payment, payment.transaction_hash, verifier, observation=observation
            )
            now = datetime.now(UTC)
            stored_record.last_checked_at = now
            if previous_location and previous_location != (
                observation.block_number,
                observation.block_hash.lower(),
            ):
                stored_record.reorg_detected_at = stored_record.reorg_detected_at or now
                logger.error(
                    "Payment transaction was re-included at a different canonical block",
                    extra={"event": "payment_reincluded", "payment_id": payment.public_id},
                )
            confirmation_delay = (
                interval
                if payment.status == PaymentStatus.CONFIRMING.value
                else min(max(interval, 60), MAX_BACKOFF_SECONDS)
            )
            _release_claim(db, payment, lease_token, interval, delay_seconds=confirmation_delay)
            db.commit()
            return (
                "confirming" if payment.status == PaymentStatus.CONFIRMING.value else final_status
            )
        except PendingTransaction:
            if record:
                try:
                    orphaned = _recorded_transaction_is_orphaned(verifier, record)
                except ChainUnavailable:
                    _release_claim(db, payment, lease_token, interval)
                    record.last_checked_at = datetime.now(UTC)
                    db.commit()
                    return "rpc_unavailable"
                if orphaned:
                    _mark_reorg(db, payment, record, lease_token, interval)
                    return "reorged"
            _release_claim(db, payment, lease_token, interval)
            if record:
                record.last_checked_at = datetime.now(UTC)
            db.commit()
            return "receipt_pending"
        except CanonicalBlockMismatch:
            if record:
                _mark_reorg(db, payment, record, lease_token, interval)
                return "reorged"
            _release_claim(db, payment, lease_token, interval)
            db.commit()
            return "canonicality_uncertain"
        except RevertedTransaction:
            if record:
                try:
                    orphaned = _recorded_transaction_is_orphaned(verifier, record)
                except ChainUnavailable:
                    _release_claim(db, payment, lease_token, interval)
                    record.last_checked_at = datetime.now(UTC)
                    db.commit()
                    return "rpc_unavailable"
                if orphaned:
                    _mark_reorg(db, payment, record, lease_token, interval)
                    return "reorged"
                _release_claim(db, payment, lease_token, interval)
                db.commit()
                return "deferred"
            if not _owns_lease(db, payment.id, lease_token):
                db.rollback()
                return "lease_lost"
            payment.status = PaymentStatus.FAILED.value
            payment.reconcile_lease_token = None
            payment.reconcile_lease_until = None
            payment.reconcile_next_at = None
            db.commit()
            logger.warning(
                "Payment transaction has a canonical reverted receipt",
                extra={"event": "payment_reverted", "payment_id": payment.public_id},
            )
            return "failed"
        except ChainConfigurationError:
            _release_claim(db, payment, lease_token, interval)
            db.commit()
            raise
        except (ChainUnavailable, InvalidChainPayment) as exc:
            # A previously recorded final state remains untouched on provider inconsistency.
            if record is None and isinstance(exc, InvalidChainPayment):
                if not _owns_lease(db, payment.id, lease_token):
                    db.rollback()
                    return "lease_lost"
                expires_at = payment.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                payment.transaction_hash = None
                payment.status = (
                    PaymentStatus.EXPIRED.value
                    if datetime.now(UTC) >= expires_at
                    else PaymentStatus.REQUIRES_PAYMENT.value
                )
                payment.reconcile_attempts = 0
                payment.reconcile_next_at = None
                payment.reconcile_lease_token = None
                payment.reconcile_lease_until = None
                db.commit()
                logger.warning(
                    "Submitted transaction did not contain valid payment evidence",
                    extra={"event": "invalid_payment_evidence", "payment_id": payment.public_id},
                )
                return "invalid_evidence"
            if record and isinstance(exc, InvalidChainPayment):
                try:
                    orphaned = _recorded_transaction_is_orphaned(verifier, record)
                except ChainUnavailable:
                    orphaned = False
                if orphaned:
                    _mark_reorg(db, payment, record, lease_token, interval)
                    return "reorged"
            _release_claim(db, payment, lease_token, interval)
            if record:
                record.last_checked_at = datetime.now(UTC)
            db.commit()
            logger.warning(
                "Payment reconciliation deferred after transient or inconsistent RPC evidence",
                extra={
                    "event": "reconciliation_deferred",
                    "payment_id": payment.public_id,
                },
            )
            return "deferred"


def run_reconciliation_batch(
    session_factory: sessionmaker[Session] = SessionLocal,
    verifier_factory: Any = PaymentVerifier.from_environment,
    *,
    interval: int | None = None,
    batch_size: int | None = None,
    lease_seconds: int | None = None,
) -> dict[str, int]:
    interval = interval or _config_int("PAYMENT_RECONCILE_INTERVAL_SECONDS", 15, 5, 3600)
    batch_size = batch_size or _config_int("PAYMENT_RECONCILE_BATCH_SIZE", 5, 1, MAX_BATCH_SIZE)
    rpc_timeout = _config_int("RPC_TIMEOUT_SECONDS", 10, 1, 120)
    batch_size = min(batch_size, MAX_RPC_CONCURRENCY)
    lease_seconds = lease_seconds or max(interval * 4, rpc_timeout * 10 + 30)
    claims = claim_due_payments(session_factory, batch_size=batch_size, lease_seconds=lease_seconds)
    if not claims:
        return {"claimed": 0}

    try:
        verifier = verifier_factory()
    except ChainConfigurationError as exc:
        logger.error(
            "Payment reconciliation is not configured",
            extra={"event": "worker_configuration_error", "error_type": type(exc).__name__},
        )
        for payment_id, token in claims:
            with session_factory() as db:
                payment = db.get(PaymentIntent, payment_id)
                if payment and payment.reconcile_lease_token == token:
                    _release_claim(db, payment, token, interval)
                    db.commit()
        return {"claimed": len(claims), "configuration_error": len(claims)}

    results: dict[str, int] = {"claimed": len(claims)}

    def process(claim: tuple[int, str]) -> str:
        payment_id, token = claim
        try:
            return reconcile_claim(session_factory, payment_id, token, verifier, interval=interval)
        except Exception as exc:  # Keep one payment from stopping the bounded batch.
            logger.error(
                "Unhandled payment reconciliation error",
                extra={"event": "reconciliation_error", "error_type": type(exc).__name__},
            )
            with session_factory() as db:
                payment = db.get(PaymentIntent, payment_id)
                if payment and payment.reconcile_lease_token == token:
                    _release_claim(db, payment, token, interval)
                    db.commit()
            return "unexpected_error"

    with ThreadPoolExecutor(max_workers=min(MAX_RPC_CONCURRENCY, len(claims))) as executor:
        futures = [executor.submit(process, claim) for claim in claims]
        for future in as_completed(futures):
            result = future.result()
            results[result] = results.get(result, 0) + 1
    logger.info(
        "Payment reconciliation batch completed",
        extra={"event": "batch_complete", "count": results},
    )
    return results


async def _periodic_reconcile(ctx: dict[str, Any]) -> None:
    interval = _config_int("PAYMENT_RECONCILE_INTERVAL_SECONDS", 15, 5, 3600)
    while True:
        try:
            batch_task = asyncio.create_task(asyncio.to_thread(run_reconciliation_batch))
            try:
                result = await asyncio.shield(batch_task)
            except asyncio.CancelledError:
                await asyncio.shield(batch_task)
                raise
            redis = ctx.get("redis")
            if redis:
                await redis.set(
                    "payrail:worker:heartbeat", datetime.now(UTC).isoformat(), ex=interval * 3
                )
                await redis.set(
                    "payrail:worker:metrics",
                    json.dumps({"updated_at": datetime.now(UTC).isoformat(), **result}),
                    ex=interval * 12,
                )
            logger.info("Worker heartbeat", extra={"event": "worker_heartbeat", "count": result})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Reconciliation cycle failed",
                extra={"event": "reconciliation_cycle_error", "error_type": type(exc).__name__},
            )
        await asyncio.sleep(interval)


async def reconcile_job(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ callable for operators wishing to enqueue a bounded one-off reconciliation."""
    return await asyncio.to_thread(run_reconciliation_batch)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    ctx["service"] = "worker"
    ctx["reconcile_task"] = asyncio.create_task(_periodic_reconcile(ctx))
    logger.info("Payment reconciliation worker started", extra={"event": "worker_started"})


async def shutdown(ctx: dict[str, Any]) -> None:
    task = ctx.get("reconcile_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Payment reconciliation worker stopped", extra={"event": "worker_stopped"})


class WorkerSettings:
    functions = [reconcile_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
