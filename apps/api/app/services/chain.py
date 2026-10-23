import os
from dataclasses import dataclass
from datetime import UTC, datetime

from hexbytes import HexBytes
from requests.exceptions import RequestException
from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound, Web3Exception

BASE_SEPOLIA_CHAIN_ID = 84532
BASE_SEPOLIA_USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
PAYMENT_ROUTER_ABI = [
    {
        "type": "event",
        "name": "PaymentReceived",
        "anonymous": False,
        "inputs": [
            {"name": "paymentId", "type": "bytes32", "indexed": True},
            {"name": "payer", "type": "address", "indexed": True},
            {"name": "recipient", "type": "address", "indexed": True},
            {"name": "token", "type": "address", "indexed": False},
            {"name": "amount", "type": "uint256", "indexed": False},
        ],
    },
    {
        "type": "function",
        "name": "usdcToken",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    },
]
PAYMENT_RECEIVED_TOPIC = Web3.keccak(
    text="PaymentReceived(bytes32,address,address,address,uint256)"
)


class ChainConfigurationError(Exception):
    pass


class ChainUnavailable(Exception):
    pass


class PendingTransaction(Exception):
    pass


class InvalidChainPayment(Exception):
    pass


class CanonicalBlockMismatch(InvalidChainPayment):
    """The receipt's block is no longer canonical at that block height."""


class RevertedTransaction(InvalidChainPayment):
    """The transaction is mined on the expected chain but reverted."""


@dataclass(frozen=True)
class PaymentObservation:
    chain_id: int
    transaction_hash: str
    log_index: int
    block_number: int
    block_hash: str
    block_timestamp: datetime
    payer: str
    recipient: str
    token: str
    amount: int
    confirmations: int


class PaymentVerifier:
    def __init__(
        self,
        rpc_url: str,
        router_address: str,
        token_address: str,
        minimum_confirmations: int = 2,
        timeout_seconds: int = 10,
        web3: Web3 | None = None,
    ) -> None:
        if minimum_confirmations < 1:
            raise ChainConfigurationError("PAYMENT_MIN_CONFIRMATIONS must be at least 1")
        if not Web3.is_address(router_address) or not Web3.is_address(token_address):
            raise ChainConfigurationError("Configured router and USDC addresses must be valid")
        self.router_address = Web3.to_checksum_address(router_address)
        self.token_address = Web3.to_checksum_address(token_address)
        self.minimum_confirmations = minimum_confirmations
        self.web3 = web3 or Web3(HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))

    def canonical_block_hash(self, block_number: int) -> str:
        """Return a block hash only after checking the RPC's chain identity."""
        try:
            if not self.web3.is_connected():
                raise ChainUnavailable("Base Sepolia RPC is unavailable")
            if int(self.web3.eth.chain_id) != BASE_SEPOLIA_CHAIN_ID:
                raise ChainUnavailable("Configured RPC changed chain identity")
            block = self.web3.eth.get_block(block_number)
            return "0x" + HexBytes(block["hash"]).hex().removeprefix("0x")
        except ChainUnavailable:
            raise
        except (
            Web3Exception,
            RequestException,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ChainUnavailable("Base Sepolia RPC could not read the canonical block") from exc

    def canonical_block_contains_transaction(
        self, block_number: int, transaction_hash: str
    ) -> bool:
        """Check full canonical block contents when a previously seen receipt disappears."""
        try:
            if not self.web3.is_connected():
                raise ChainUnavailable("Base Sepolia RPC is unavailable")
            if int(self.web3.eth.chain_id) != BASE_SEPOLIA_CHAIN_ID:
                raise ChainUnavailable("Configured RPC changed chain identity")
            block = self.web3.eth.get_block(block_number, full_transactions=True)
            expected = HexBytes(transaction_hash)
            for tx in block["transactions"]:
                tx_hash = tx.get("hash") if isinstance(tx, dict) else getattr(tx, "hash", tx)
                if HexBytes(tx_hash) == expected:
                    return True
            return False
        except ChainUnavailable:
            raise
        except (
            Web3Exception,
            RequestException,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ChainUnavailable(
                "Base Sepolia RPC could not inspect canonical block transactions"
            ) from exc

    @classmethod
    def from_environment(cls) -> "PaymentVerifier":
        rpc_url = os.getenv("BASE_SEPOLIA_RPC_URL", "").strip()
        router_address = os.getenv("PAYMENT_ROUTER_ADDRESS", "").strip()
        token_address = os.getenv("USDC_TOKEN_ADDRESS", "").strip()
        if not rpc_url or not router_address or not token_address:
            raise ChainConfigurationError(
                "BASE_SEPOLIA_RPC_URL, PAYMENT_ROUTER_ADDRESS, and USDC_TOKEN_ADDRESS are required"
            )
        if not Web3.is_address(token_address) or (
            Web3.to_checksum_address(token_address)
            != Web3.to_checksum_address(BASE_SEPOLIA_USDC_ADDRESS)
        ):
            raise ChainConfigurationError(
                "USDC_TOKEN_ADDRESS must be the documented Base Sepolia USDC contract"
            )
        try:
            minimum_confirmations = int(os.getenv("PAYMENT_MIN_CONFIRMATIONS", "2"))
            timeout_seconds = int(os.getenv("RPC_TIMEOUT_SECONDS", "10"))
        except ValueError as exc:
            raise ChainConfigurationError(
                "RPC confirmation and timeout values must be integers"
            ) from exc
        return cls(
            rpc_url,
            router_address,
            token_address,
            minimum_confirmations,
            timeout_seconds,
        )

    def verify(
        self,
        payment_public_id: str,
        transaction_hash: str,
        expected_recipient: str,
    ) -> PaymentObservation:
        try:
            if not self.web3.is_connected():
                raise ChainUnavailable("Base Sepolia RPC is unavailable")

            chain_id = int(self.web3.eth.chain_id)
            if chain_id != BASE_SEPOLIA_CHAIN_ID:
                raise InvalidChainPayment(f"Expected Base Sepolia chain ID {BASE_SEPOLIA_CHAIN_ID}")

            tx_hash = HexBytes(transaction_hash)
            transaction = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            if int(receipt["status"]) != 1:
                raise RevertedTransaction("Transaction receipt indicates a reverted transaction")

            destination = transaction.get("to") or receipt.get("to")
            if not destination or Web3.to_checksum_address(destination) != self.router_address:
                raise InvalidChainPayment(
                    "Transaction was not sent to the configured Payment Router"
                )

            block_number = int(receipt["blockNumber"])
            block = self.web3.eth.get_block(block_number)
            receipt_block_hash = "0x" + HexBytes(receipt["blockHash"]).hex().removeprefix("0x")
            canonical_block_hash = "0x" + HexBytes(block["hash"]).hex().removeprefix("0x")
            if receipt_block_hash.lower() != canonical_block_hash.lower():
                raise CanonicalBlockMismatch("Receipt block is no longer canonical")
            block_timestamp = datetime.fromtimestamp(int(block["timestamp"]), tz=UTC)
            router = self.web3.eth.contract(address=self.router_address, abi=PAYMENT_ROUTER_ABI)
            configured_token = router.functions.usdcToken().call(block_identifier=block_number)
            if Web3.to_checksum_address(configured_token) != self.token_address:
                raise InvalidChainPayment("Payment Router token configuration does not match USDC")
            if not self.web3.eth.get_code(self.token_address, block_identifier=block_number):
                raise InvalidChainPayment("Configured USDC address has no contract code")

            if not Web3.is_address(transaction["from"]):
                raise InvalidChainPayment("Transaction sender is not a valid address")

            expected_payment_id = Web3.keccak(text=payment_public_id)
            expected_recipient = Web3.to_checksum_address(expected_recipient)
            payment_logs = []
            for log in receipt["logs"]:
                if Web3.to_checksum_address(log["address"]) != self.router_address:
                    continue
                topics = log["topics"]
                if len(topics) != 4 or HexBytes(topics[0]) != PAYMENT_RECEIVED_TOPIC:
                    continue
                if HexBytes(topics[1]) == expected_payment_id:
                    payment_logs.append(log)
            if len(payment_logs) != 1:
                raise InvalidChainPayment(
                    "Receipt must contain exactly one matching PaymentReceived event"
                )

            log = payment_logs[0]
            payer = Web3.to_checksum_address(HexBytes(log["topics"][2])[-20:])
            recipient = Web3.to_checksum_address(HexBytes(log["topics"][3])[-20:])
            token, amount = self.web3.codec.decode(["address", "uint256"], log["data"])
            token = Web3.to_checksum_address(token)
            if payer != Web3.to_checksum_address(transaction["from"]):
                raise InvalidChainPayment("Payment event payer does not match transaction sender")
            if recipient != expected_recipient:
                raise InvalidChainPayment(
                    "Payment event recipient does not match the payment intent"
                )
            if token != self.token_address:
                raise InvalidChainPayment("Payment event token does not match configured USDC")

            current_block = int(self.web3.eth.block_number)
            confirmations = max(0, current_block - block_number + 1)
            block_hash = "0x" + HexBytes(receipt["blockHash"]).hex().removeprefix("0x")
            canonical_hash = "0x" + HexBytes(receipt["transactionHash"]).hex().removeprefix("0x")
            requested_hash = "0x" + HexBytes(tx_hash).hex().removeprefix("0x")
            if canonical_hash.lower() != requested_hash.lower():
                raise InvalidChainPayment("Receipt transaction hash does not match requested hash")

            return PaymentObservation(
                chain_id=chain_id,
                transaction_hash=canonical_hash,
                log_index=int(log["logIndex"]),
                block_number=block_number,
                block_hash=block_hash,
                block_timestamp=block_timestamp,
                payer=payer,
                recipient=recipient,
                token=token,
                amount=int(amount),
                confirmations=confirmations,
            )
        except CanonicalBlockMismatch:
            raise
        except (ChainUnavailable, ChainConfigurationError, PendingTransaction, InvalidChainPayment):
            raise
        except TransactionNotFound as exc:
            raise PendingTransaction(
                "Transaction is not mined yet; retry verification later"
            ) from exc
        except Web3Exception as exc:
            raise ChainUnavailable("Base Sepolia RPC request failed; retry verification") from exc
        except RequestException as exc:
            raise ChainUnavailable("Base Sepolia RPC request failed; retry verification") from exc
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ChainUnavailable("Base Sepolia RPC returned malformed transaction data") from exc
