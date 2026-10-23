import json
import shutil
import socket
import subprocess
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.database import Base
from app.models import BlockchainTransaction, Merchant, PaymentIntent, PaymentStatus
from app.services.chain import PaymentVerifier
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from web3 import HTTPProvider, Web3

from payrail_worker.worker import run_reconciliation_batch

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "contracts"
ARTIFACTS = CONTRACTS / "out"


def _artifact(file_name: str, contract_name: str) -> dict:
    path = ARTIFACTS / file_name / f"{contract_name}.json"
    return json.loads(path.read_text())


@pytest.fixture
def local_evm() -> Generator[tuple[Web3, subprocess.Popen], None, None]:
    anvil = shutil.which("anvil")
    forge = shutil.which("forge")
    if not anvil or not forge:
        pytest.skip("Anvil and Foundry are required for the local-EVM integration test")
    subprocess.run([forge, "build", "--force"], cwd=CONTRACTS, check=True, capture_output=True)
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
    except PermissionError:
        pytest.skip("Sandbox policy prevents starting a loopback Anvil node")
    process = subprocess.Popen(
        [anvil, "--host", "127.0.0.1", "--port", str(port), "--chain-id", "84532", "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    web3 = Web3(HTTPProvider(f"http://127.0.0.1:{port}", request_kwargs={"timeout": 1}))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and process.poll() is None:
        try:
            if web3.is_connected():
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        process.terminate()
        process.wait(timeout=5)
        pytest.fail("Anvil did not start on its loopback port")
    try:
        yield web3, process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


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


def _deploy(web3: Web3, artifact: dict, sender: str, *args: object) -> str:
    factory = web3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
    tx_hash = factory.constructor(*args).transact({"from": sender})
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1
    return receipt.contractAddress


def test_local_anvil_payment_is_confirmed_only_at_threshold(local_evm, sessions) -> None:
    web3, _ = local_evm
    owner, payer, recipient = web3.eth.accounts[:3]
    token_address = _deploy(
        web3, _artifact("MockERC20.sol", "MockERC20"), owner, "Mock USDC", "USDC"
    )
    router_address = _deploy(
        web3, _artifact("PaymentRouter.sol", "PaymentRouter"), owner, token_address
    )
    token = web3.eth.contract(
        address=token_address, abi=_artifact("MockERC20.sol", "MockERC20")["abi"]
    )
    router = web3.eth.contract(
        address=router_address, abi=_artifact("PaymentRouter.sol", "PaymentRouter")["abi"]
    )
    amount = 1_250_000
    public_id = "pi_anvil_reconcile"
    mint_hash = token.functions.mint(payer, amount).transact({"from": owner})
    assert web3.eth.wait_for_transaction_receipt(mint_hash).status == 1
    approval_hash = token.functions.approve(router_address, amount).transact({"from": payer})
    assert web3.eth.wait_for_transaction_receipt(approval_hash).status == 1
    assert token.functions.balanceOf(payer).call() == amount
    assert token.functions.allowance(payer, router_address).call() == amount
    payment_tx = router.functions.pay(
        Web3.keccak(text=public_id), token_address, recipient, amount
    ).transact({"from": payer})
    receipt = web3.eth.wait_for_transaction_receipt(payment_tx)
    assert receipt.status == 1

    with sessions() as db:
        merchant = Merchant(name="Anvil test", api_key_hash="e" * 64)
        db.add(merchant)
        db.flush()
        payment = PaymentIntent(
            public_id=public_id,
            merchant_id=merchant.id,
            amount=amount,
            currency="USDC",
            network="base-sepolia",
            recipient=recipient,
            status=PaymentStatus.CONFIRMING.value,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            transaction_hash=Web3.to_hex(payment_tx),
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

    verifier = PaymentVerifier(
        "http://127.0.0.1",
        router_address,
        token_address,
        minimum_confirmations=2,
        web3=web3,
    )

    def factory() -> PaymentVerifier:
        return verifier

    first = run_reconciliation_batch(sessions, factory, interval=5, batch_size=10, lease_seconds=20)
    assert first["confirming"] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        assert payment and payment.status == PaymentStatus.CONFIRMING.value
        payment.reconcile_next_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    web3.provider.make_request("evm_mine", [])
    second = run_reconciliation_batch(
        sessions, factory, interval=5, batch_size=10, lease_seconds=20
    )
    assert second[PaymentStatus.SUCCEEDED.value] == 1
    with sessions() as db:
        payment = db.get(PaymentIntent, payment_id)
        transaction = db.scalar(select(BlockchainTransaction))
        assert payment and payment.status == PaymentStatus.SUCCEEDED.value
        assert transaction and transaction.confirmations == 2
