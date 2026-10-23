from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BlockchainTransaction, PaymentIntent, PaymentStatus
from app.services.chain import PaymentObservation, PaymentVerifier


class PaymentStateConflict(Exception):
    pass


def record_verified_payment(
    db: Session,
    payment: PaymentIntent,
    transaction_hash: str,
    verifier: PaymentVerifier,
    observation: PaymentObservation | None = None,
) -> tuple[BlockchainTransaction, int, str]:
    """Verify chain evidence and persist one observed PaymentReceived log atomically."""
    if payment.status == PaymentStatus.CANCELED.value:
        raise PaymentStateConflict("Cannot verify a canceled payment intent")
    if payment.transaction_hash and payment.transaction_hash.lower() != transaction_hash.lower():
        raise PaymentStateConflict(
            "A different transaction hash is already associated with this payment"
        )

    if observation is None:
        observation = verifier.verify(payment.public_id, transaction_hash, payment.recipient)
    duplicate = db.scalar(
        select(BlockchainTransaction).where(
            BlockchainTransaction.chain_id == observation.chain_id,
            BlockchainTransaction.transaction_hash == observation.transaction_hash,
            BlockchainTransaction.log_index == observation.log_index,
        )
    )
    if duplicate and duplicate.payment_intent_id != payment.id:
        raise PaymentStateConflict("This blockchain event is already linked to another payment")
    if duplicate and (
        duplicate.payer.lower() != observation.payer.lower()
        or duplicate.recipient.lower() != observation.recipient.lower()
        or duplicate.token.lower() != observation.token.lower()
        or duplicate.amount != observation.amount
    ):
        raise PaymentStateConflict("Previously recorded transaction evidence changed")
    reused_transaction = db.scalar(
        select(BlockchainTransaction).where(
            BlockchainTransaction.chain_id == observation.chain_id,
            BlockchainTransaction.transaction_hash == observation.transaction_hash,
            BlockchainTransaction.payment_intent_id != payment.id,
        )
    )
    if reused_transaction:
        raise PaymentStateConflict("This transaction hash is already linked to another payment")

    expires_at = payment.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    mined_after_expiry = observation.block_timestamp > expires_at

    if mined_after_expiry:
        final_status = PaymentStatus.EXPIRED.value
    elif observation.amount < payment.amount:
        final_status = PaymentStatus.UNDERPAID.value
    elif observation.amount > payment.amount:
        final_status = PaymentStatus.OVERPAID.value
    else:
        final_status = PaymentStatus.SUCCEEDED.value

    re_included_at_new_location = duplicate is not None and (
        duplicate.block_number != observation.block_number
        or duplicate.block_hash.lower() != observation.block_hash.lower()
    )
    recovering_from_reorg = (
        payment.status == PaymentStatus.REORGED.value
        or (duplicate is not None and duplicate.verification_status == PaymentStatus.REORGED.value)
        or re_included_at_new_location
    )
    if recovering_from_reorg or observation.confirmations < verifier.minimum_confirmations:
        verification_status = "confirming"
    elif mined_after_expiry:
        verification_status = PaymentStatus.EXPIRED.value
    else:
        verification_status = final_status
    if duplicate:
        record = duplicate
        record.confirmations = observation.confirmations
        record.verification_status = verification_status
        record.block_hash = observation.block_hash
        record.block_number = observation.block_number
    else:
        record = BlockchainTransaction(
            payment_intent_id=payment.id,
            chain_id=observation.chain_id,
            transaction_hash=observation.transaction_hash,
            log_index=observation.log_index,
            block_number=observation.block_number,
            block_hash=observation.block_hash,
            payer=observation.payer,
            recipient=observation.recipient,
            token=observation.token,
            amount=observation.amount,
            confirmations=observation.confirmations,
            verification_status=verification_status,
        )
        db.add(record)

    payment.transaction_hash = observation.transaction_hash
    payment.status = verification_status
    db.flush()
    return record, verifier.minimum_confirmations, final_status
