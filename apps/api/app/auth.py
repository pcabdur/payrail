import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Merchant


def new_api_key() -> str:
    return "pr_test_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def current_merchant(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Merchant:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer API key required")
    key_hash = hash_api_key(authorization.removeprefix("Bearer "))
    merchant = db.scalar(select(Merchant).where(Merchant.api_key_hash == key_hash))
    if merchant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return merchant
