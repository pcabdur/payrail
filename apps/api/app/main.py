import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from web3 import Web3

from app.auth import current_merchant, hash_api_key, new_api_key
from app.database import get_db
from app.models import IdempotencyRecord, Merchant, PaymentIntent, PaymentStatus
from app.schemas import (
    CheckoutRead,
    MerchantCreate,
    MerchantCreated,
    PaymentCreate,
    PaymentRead,
    PaymentVerificationRead,
    TransactionVerify,
)
from app.services.chain import (
    BASE_SEPOLIA_CHAIN_ID,
    BASE_SEPOLIA_USDC_ADDRESS,
    ChainConfigurationError,
    ChainUnavailable,
    InvalidChainPayment,
    PaymentVerifier,
    PendingTransaction,
)
from app.services.payments import PaymentStateConflict, record_verified_payment

app = FastAPI(title="PayRail API", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3001").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


def get_payment_verifier() -> PaymentVerifier:
    try:
        return PaymentVerifier.from_environment()
    except ChainConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _expire_payment_if_due(payment: PaymentIntent, db: Session) -> None:
    expires_at = payment.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if payment.status == PaymentStatus.REQUIRES_PAYMENT.value and datetime.now(UTC) >= expires_at:
        payment.status = PaymentStatus.EXPIRED.value
        db.commit()


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Report process health only; dependencies are checked by /ready."""
    return {"status": "ok", "service": "api"}


@app.get("/ready", tags=["operations"])
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Check the configured database connection, not blockchain or Redis dependencies."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.post("/v1/merchants", response_model=MerchantCreated, status_code=201, tags=["merchants"])
def register_merchant(body: MerchantCreate, db: Session = Depends(get_db)) -> MerchantCreated:
    """Create a development merchant and reveal its API key once."""
    api_key = new_api_key()
    merchant = Merchant(name=body.name, api_key_hash=hash_api_key(api_key))
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return MerchantCreated(
        id=merchant.id, name=merchant.name, api_key=api_key, created_at=merchant.created_at
    )


@app.post("/v1/payment_intents", response_model=PaymentRead, status_code=201, tags=["payments"])
def create_payment_intent(
    body: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    merchant: Merchant = Depends(current_merchant),
    db: Session = Depends(get_db),
) -> PaymentIntent:
    if not idempotency_key or len(idempotency_key) > 255:
        raise HTTPException(status_code=400, detail="A valid Idempotency-Key header is required")

    payload = body.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.merchant_id == merchant.id,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(
                status_code=409, detail="Idempotency key reused with different input"
            )
        payment = db.get(PaymentIntent, previous.payment_intent_id)
        if payment is None:
            raise HTTPException(status_code=409, detail="Idempotency record is no longer valid")
        response.status_code = status.HTTP_200_OK
        return payment

    now = datetime.now(UTC)
    payment = PaymentIntent(
        public_id="pi_" + secrets.token_urlsafe(18),
        merchant_id=merchant.id,
        amount=body.amount,
        currency=body.currency,
        network=body.network,
        recipient=body.recipient,
        description=body.description,
        metadata_json=body.metadata,
        status=PaymentStatus.REQUIRES_PAYMENT.value,
        created_at=now,
        expires_at=now + timedelta(seconds=body.expires_in_seconds),
    )
    db.add(payment)
    db.flush()
    db.add(
        IdempotencyRecord(
            merchant_id=merchant.id,
            key=idempotency_key,
            request_hash=request_hash,
            payment_intent_id=payment.id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.merchant_id == merchant.id,
                IdempotencyRecord.key == idempotency_key,
            )
        )
        if previous and previous.request_hash == request_hash:
            response.status_code = status.HTTP_200_OK
            return db.get(PaymentIntent, previous.payment_intent_id)
        if previous:
            raise HTTPException(
                status_code=409, detail="Idempotency key reused with different input"
            )
        raise
    db.refresh(payment)
    return payment


@app.get("/v1/payment_intents", response_model=list[PaymentRead], tags=["payments"])
def list_payment_intents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    merchant: Merchant = Depends(current_merchant),
    db: Session = Depends(get_db),
) -> list[PaymentIntent]:
    payments = list(
        db.scalars(
            select(PaymentIntent)
            .where(PaymentIntent.merchant_id == merchant.id)
            .order_by(PaymentIntent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    for payment in payments:
        _expire_payment_if_due(payment, db)
    return payments


@app.get("/v1/payment_intents/{public_id}", response_model=PaymentRead, tags=["payments"])
def get_payment_intent(
    public_id: str,
    merchant: Merchant = Depends(current_merchant),
    db: Session = Depends(get_db),
) -> PaymentIntent:
    payment = db.scalar(
        select(PaymentIntent).where(
            PaymentIntent.public_id == public_id, PaymentIntent.merchant_id == merchant.id
        )
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    _expire_payment_if_due(payment, db)
    return payment


@app.post("/v1/payment_intents/{public_id}/cancel", response_model=PaymentRead, tags=["payments"])
def cancel_payment_intent(
    public_id: str,
    merchant: Merchant = Depends(current_merchant),
    db: Session = Depends(get_db),
) -> PaymentIntent:
    payment = db.scalar(
        select(PaymentIntent).where(
            PaymentIntent.public_id == public_id, PaymentIntent.merchant_id == merchant.id
        )
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    _expire_payment_if_due(payment, db)
    if payment.status != PaymentStatus.REQUIRES_PAYMENT.value:
        raise HTTPException(status_code=409, detail="Payment intent can no longer be canceled")
    payment.status = PaymentStatus.CANCELED.value
    db.commit()
    db.refresh(payment)
    return payment


def _verify_for_payment(
    payment: PaymentIntent,
    body: TransactionVerify,
    response: Response,
    db: Session,
    verifier: PaymentVerifier,
) -> PaymentVerificationRead:
    locked_payment = db.scalar(
        select(PaymentIntent)
        .where(PaymentIntent.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    payment = locked_payment
    try:
        transaction, required_confirmations, final_status = record_verified_payment(
            db, payment, body.transaction_hash, verifier
        )
        db.commit()
    except PendingTransaction as exc:
        if (
            payment.transaction_hash
            and payment.transaction_hash.lower() != body.transaction_hash.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail="A different transaction hash is already associated with this payment",
            ) from exc
        payment.transaction_hash = body.transaction_hash
        payment.status = PaymentStatus.CONFIRMING.value
        db.commit()
        _expire_payment_if_due(payment, db)
        response.status_code = status.HTTP_202_ACCEPTED
        return PaymentVerificationRead(
            public_id=payment.public_id,
            status=payment.status,
            transaction_hash=body.transaction_hash,
            confirmations=0,
            required_confirmations=verifier.minimum_confirmations,
            message=str(exc),
        )
    except (ChainUnavailable, ChainConfigurationError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidChainPayment as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PaymentStateConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Blockchain event was already processed"
        ) from exc

    db.refresh(payment)
    is_confirming = payment.status == "confirming"
    response.status_code = status.HTTP_202_ACCEPTED if is_confirming else status.HTTP_200_OK
    message = (
        f"Waiting for {required_confirmations} confirmations"
        if is_confirming
        else f"Payment verified with status {final_status}"
    )
    return PaymentVerificationRead(
        public_id=payment.public_id,
        status=payment.status,
        transaction_hash=transaction.transaction_hash,
        confirmations=transaction.confirmations,
        required_confirmations=required_confirmations,
        message=message,
    )


@app.post(
    "/v1/payment_intents/{public_id}/verify",
    response_model=PaymentVerificationRead,
    tags=["payments"],
)
def verify_payment_intent(
    public_id: str,
    body: TransactionVerify,
    response: Response,
    merchant: Merchant = Depends(current_merchant),
    db: Session = Depends(get_db),
    verifier: PaymentVerifier = Depends(get_payment_verifier),
) -> PaymentVerificationRead:
    payment = db.scalar(
        select(PaymentIntent).where(
            PaymentIntent.public_id == public_id, PaymentIntent.merchant_id == merchant.id
        )
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    _expire_payment_if_due(payment, db)
    return _verify_for_payment(payment, body, response, db, verifier)


@app.get("/checkout/{public_id}", response_model=CheckoutRead, tags=["checkout"])
def get_checkout(public_id: str, db: Session = Depends(get_db)) -> CheckoutRead:
    payment = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == public_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
        _expire_payment_if_due(payment, db)
    token = os.getenv("USDC_TOKEN_ADDRESS")
    router = os.getenv("PAYMENT_ROUTER_ADDRESS")
    for label, address in (("USDC_TOKEN_ADDRESS", token), ("PAYMENT_ROUTER_ADDRESS", router)):
        if address and not Web3.is_address(address):
            raise HTTPException(status_code=503, detail=f"{label} is not a valid EVM address")
    if token and Web3.to_checksum_address(token) != Web3.to_checksum_address(
        BASE_SEPOLIA_USDC_ADDRESS
    ):
        raise HTTPException(
            status_code=503,
            detail="USDC_TOKEN_ADDRESS must be the documented Base Sepolia USDC contract",
        )
    return CheckoutRead(
        public_id=payment.public_id,
        merchant_name=payment.merchant.name,
        amount=str(payment.amount),
        currency=payment.currency,
        network=payment.network,
        recipient=payment.recipient,
        status=payment.status,
        created_at=payment.created_at,
        expires_at=payment.expires_at,
        transaction_hash=payment.transaction_hash,
        chain_id=BASE_SEPOLIA_CHAIN_ID,
        token_address=Web3.to_checksum_address(token) if token else None,
        router_address=Web3.to_checksum_address(router) if router else None,
    )


@app.post(
    "/checkout/{public_id}/verify",
    response_model=PaymentVerificationRead,
    tags=["checkout"],
)
def verify_checkout_payment(
    public_id: str,
    body: TransactionVerify,
    response: Response,
    db: Session = Depends(get_db),
    verifier: PaymentVerifier = Depends(get_payment_verifier),
) -> PaymentVerificationRead:
    payment = db.scalar(select(PaymentIntent).where(PaymentIntent.public_id == public_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    _expire_payment_if_due(payment, db)
    return _verify_for_payment(payment, body, response, db, verifier)
