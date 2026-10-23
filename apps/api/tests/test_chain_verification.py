from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from hexbytes import HexBytes
from web3 import Web3

from app.services.chain import (
    BASE_SEPOLIA_CHAIN_ID,
    PAYMENT_RECEIVED_TOPIC,
    InvalidChainPayment,
    PaymentVerifier,
)

PAYMENT_ID = "pi_test-chain-payment"
RPC_HASH = "0x" + "a" * 64
ROUTER = "0x" + "1" * 40
TOKEN = "0x" + "2" * 40
PAYER = "0x" + "3" * 40
RECIPIENT = "0x" + "4" * 40


def make_verifier(
    *,
    chain_id: int = BASE_SEPOLIA_CHAIN_ID,
    token_config: str = TOKEN,
    tx_to: str = ROUTER,
    event_id: str = PAYMENT_ID,
    event_payer: str = PAYER,
    event_recipient: str = RECIPIENT,
    event_token: str = TOKEN,
    event_amount: int = 1_250_000,
    block_number: int = 100,
    current_block: int = 102,
) -> PaymentVerifier:
    web3 = MagicMock()
    web3.is_connected.return_value = True
    web3.codec = Web3().codec
    web3.eth.chain_id = chain_id
    web3.eth.block_number = current_block
    web3.eth.get_transaction.return_value = {"to": tx_to, "from": PAYER}
    web3.eth.get_code.return_value = HexBytes("0x6000")
    web3.eth.get_block.return_value = {
        "timestamp": int(datetime.now(UTC).timestamp()),
        "hash": HexBytes("0x" + "b" * 64),
    }
    web3.eth.contract.return_value.functions.usdcToken.return_value.call.return_value = token_config

    def pad_address(address: str) -> bytes:
        return b"\x00" * 12 + bytes.fromhex(address[2:])

    encoded_data = web3.codec.encode(["address", "uint256"], [event_token, event_amount])
    event_log = {
        "address": ROUTER,
        "topics": [
            PAYMENT_RECEIVED_TOPIC,
            Web3.keccak(text=event_id),
            pad_address(event_payer),
            pad_address(event_recipient),
        ],
        "data": encoded_data,
        "logIndex": 3,
    }
    web3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": block_number,
        "blockHash": HexBytes("0x" + "b" * 64),
        "transactionHash": HexBytes(RPC_HASH),
        "logs": [event_log],
    }
    return PaymentVerifier(
        "http://rpc.invalid",
        ROUTER,
        TOKEN,
        minimum_confirmations=2,
        web3=web3,
    )


def test_verifies_receipt_event_and_confirmation_count() -> None:
    observation = make_verifier().verify(PAYMENT_ID, RPC_HASH, RECIPIENT)
    assert observation.chain_id == BASE_SEPOLIA_CHAIN_ID
    assert observation.transaction_hash == RPC_HASH
    assert observation.payer == Web3.to_checksum_address(PAYER)
    assert observation.recipient == Web3.to_checksum_address(RECIPIENT)
    assert observation.token == Web3.to_checksum_address(TOKEN)
    assert observation.amount == 1_250_000
    assert observation.confirmations == 3
    assert observation.log_index == 3


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"chain_id": 1}, "chain ID"),
        ({"tx_to": TOKEN}, "Payment Router"),
        ({"token_config": RECIPIENT}, "token configuration"),
        ({"event_id": "pi-someone-elses-payment"}, "matching PaymentReceived"),
        ({"event_payer": RECIPIENT}, "transaction sender"),
        ({"event_recipient": PAYER}, "recipient does not match"),
        ({"event_token": RECIPIENT}, "event token"),
    ],
)
def test_rejects_invalid_chain_evidence(overrides: dict, message: str) -> None:
    verifier = make_verifier(**overrides)
    with pytest.raises(InvalidChainPayment, match=message):
        verifier.verify(PAYMENT_ID, RPC_HASH, RECIPIENT)


def test_amount_mismatch_is_returned_as_observed_chain_evidence() -> None:
    observation = make_verifier(event_amount=1_249_999).verify(PAYMENT_ID, RPC_HASH, RECIPIENT)
    assert observation.amount == 1_249_999


def test_checks_transaction_membership_in_canonical_block() -> None:
    verifier = make_verifier()
    verifier.web3.eth.get_block.return_value["transactions"] = [{"hash": HexBytes(RPC_HASH)}]
    assert verifier.canonical_block_contains_transaction(100, RPC_HASH)
    verifier.web3.eth.get_block.return_value["transactions"] = []
    assert not verifier.canonical_block_contains_transaction(100, RPC_HASH)
