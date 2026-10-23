from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, get_payment_verifier
from app.services.chain import PaymentObservation


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Generator[Session, None, None]:
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def register(client: TestClient, name: str = "Test Merchant") -> str:
    response = client.post("/v1/merchants", json={"name": name})
    assert response.status_code == 201
    return response.json()["api_key"]


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "api"}
    assert client.get("/ready").status_code == 200


def test_cors_allows_configured_development_origin(client: TestClient) -> None:
    response = client.options(
        "/checkout/pi_example/verify",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_payment_creation_is_idempotent_and_scoped(client: TestClient) -> None:
    key = register(client)
    auth = {"Authorization": f"Bearer {key}", "Idempotency-Key": "order-123"}
    payload = {"amount": 1_250_000, "recipient": "0x" + "a" * 40}

    first = client.post("/v1/payment_intents", headers=auth, json=payload)
    replay = client.post("/v1/payment_intents", headers=auth, json=payload)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["public_id"] == first.json()["public_id"]
    assert first.json()["status"] == "requires_payment"

    conflict = client.post(
        "/v1/payment_intents", headers=auth, json={**payload, "amount": 1_250_001}
    )
    assert conflict.status_code == 409

    other_key = register(client, "Another Merchant")
    hidden = client.get(
        f"/v1/payment_intents/{first.json()['public_id']}",
        headers={"Authorization": f"Bearer {other_key}"},
    )
    assert hidden.status_code == 404


def test_amount_must_be_positive_and_api_key_is_required(client: TestClient) -> None:
    assert (
        client.post(
            "/v1/payment_intents",
            headers={"Idempotency-Key": "bad"},
            json={"amount": 0, "recipient": "0x" + "b" * 40},
        ).status_code
        == 401
    )

    key = register(client)
    response = client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {key}", "Idempotency-Key": "bad"},
        json={"amount": 0, "recipient": "0x" + "b" * 40},
    )
    assert response.status_code == 422


def test_list_retrieve_and_cancel_pending_payment(client: TestClient) -> None:
    key = register(client)
    headers = {"Authorization": f"Bearer {key}", "Idempotency-Key": "cancel-me"}
    created = client.post(
        "/v1/payment_intents",
        headers=headers,
        json={
            "amount": 2_000_000,
            "recipient": "0x" + "c" * 40,
            "metadata": {"order": "A-1"},
        },
    )
    payment_id = created.json()["public_id"]

    assert client.get("/v1/payment_intents", headers=headers).json()[0]["public_id"] == payment_id
    assert client.get(f"/v1/payment_intents/{payment_id}", headers=headers).json()["metadata"] == {
        "order": "A-1"
    }
    canceled = client.post(f"/v1/payment_intents/{payment_id}/cancel", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert (
        client.post(f"/v1/payment_intents/{payment_id}/cancel", headers=headers).status_code == 409
    )


class FakeVerifier:
    minimum_confirmations = 2

    def __init__(self, amount: int = 1_250_000, block_timestamp: datetime | None = None) -> None:
        self.amount = amount
        self.block_timestamp = block_timestamp or datetime.now(UTC)

    def verify(self, public_id: str, transaction_hash: str, recipient: str) -> PaymentObservation:
        return PaymentObservation(
            chain_id=84532,
            transaction_hash=transaction_hash,
            log_index=0,
            block_number=100,
            block_timestamp=self.block_timestamp,
            block_hash="0x" + "b" * 64,
            payer="0x" + "a" * 40,
            recipient=recipient,
            token="0x" + "c" * 40,
            amount=self.amount,
            confirmations=2,
        )


def test_public_checkout_verifies_and_persists_payment(client: TestClient) -> None:
    app.dependency_overrides[get_payment_verifier] = lambda: FakeVerifier()
    key = register(client)
    created = client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {key}", "Idempotency-Key": "checkout"},
        json={"amount": 1_250_000, "recipient": "0x" + "d" * 40},
    )
    public_id = created.json()["public_id"]
    checkout = client.get(f"/checkout/{public_id}")
    assert checkout.status_code == 200
    assert checkout.json()["amount"] == "1250000"

    tx_hash = "0x" + "e" * 64
    verified = client.post(f"/checkout/{public_id}/verify", json={"transaction_hash": tx_hash})
    assert verified.status_code == 200
    assert verified.json()["status"] == "succeeded"
    assert client.get(f"/checkout/{public_id}").json()["transaction_hash"] == tx_hash

    replay = client.post(f"/checkout/{public_id}/verify", json={"transaction_hash": tx_hash})
    assert replay.status_code == 200
    assert replay.json()["status"] == "succeeded"


def test_public_checkout_records_underpayment_after_confirmations(client: TestClient) -> None:
    app.dependency_overrides[get_payment_verifier] = lambda: FakeVerifier(amount=1_249_999)
    key = register(client)
    created = client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {key}", "Idempotency-Key": "underpayment"},
        json={"amount": 1_250_000, "recipient": "0x" + "d" * 40},
    )
    verified = client.post(
        f"/checkout/{created.json()['public_id']}/verify",
        json={"transaction_hash": "0x" + "f" * 64},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "underpaid"


def test_one_transaction_cannot_be_reused_for_another_intent(client: TestClient) -> None:
    app.dependency_overrides[get_payment_verifier] = lambda: FakeVerifier()
    key = register(client)
    tx_hash = "0x" + "9" * 64
    payment_ids = []
    for idempotency_key in ("first-tx", "second-tx"):
        created = client.post(
            "/v1/payment_intents",
            headers={
                "Authorization": f"Bearer {key}",
                "Idempotency-Key": idempotency_key,
            },
            json={"amount": 1_250_000, "recipient": "0x" + "d" * 40},
        )
        payment_ids.append(created.json()["public_id"])

    first = client.post(f"/checkout/{payment_ids[0]}/verify", json={"transaction_hash": tx_hash})
    second = client.post(f"/checkout/{payment_ids[1]}/verify", json={"transaction_hash": tx_hash})
    assert first.status_code == 200
    assert second.status_code == 409


def test_late_onchain_payment_is_recorded_as_expired(client: TestClient) -> None:
    app.dependency_overrides[get_payment_verifier] = lambda: FakeVerifier(
        block_timestamp=datetime.now(UTC) + timedelta(days=2)
    )
    key = register(client)
    created = client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {key}", "Idempotency-Key": "late"},
        json={"amount": 1_250_000, "recipient": "0x" + "d" * 40},
    )
    result = client.post(
        f"/checkout/{created.json()['public_id']}/verify",
        json={"transaction_hash": "0x" + "8" * 64},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "expired"
    assert client.get(f"/checkout/{created.json()['public_id']}").json()["transaction_hash"]
