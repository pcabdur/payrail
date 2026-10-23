from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

Recipient = Annotated[
    str,
    StringConstraints(min_length=3, max_length=128, pattern=r"^0x[0-9a-fA-F]{40}$"),
]


class MerchantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MerchantCreated(BaseModel):
    id: int
    name: str
    api_key: str
    created_at: datetime


class PaymentCreate(BaseModel):
    amount: StrictInt = Field(gt=0, description="USDC base units (1 USDC = 1,000,000 units)")
    currency: str = Field(default="USDC", pattern="^USDC$")
    network: str = Field(default="base-sepolia", pattern="^base-sepolia$")
    recipient: Recipient
    description: str | None = Field(default=None, max_length=500)
    metadata: dict[str, str] | None = None
    expires_in_seconds: int = Field(default=1800, ge=60, le=86400)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    amount: int
    currency: str
    network: str
    recipient: str
    description: str | None
    metadata: dict[str, str] | None = Field(default=None, validation_alias="metadata_json")
    status: str
    created_at: datetime
    expires_at: datetime
    transaction_hash: str | None


class TransactionVerify(BaseModel):
    transaction_hash: str = Field(pattern=r"^0x[0-9a-fA-F]{64}$")


class PaymentVerificationRead(BaseModel):
    public_id: str
    status: str
    transaction_hash: str
    confirmations: int
    required_confirmations: int
    message: str


class CheckoutRead(BaseModel):
    public_id: str
    merchant_name: str
    amount: str
    currency: str
    network: str
    recipient: str
    status: str
    created_at: datetime
    expires_at: datetime
    transaction_hash: str | None
    chain_id: int
    token_address: str | None
    router_address: str | None
