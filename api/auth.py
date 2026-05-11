"""API key authentication middleware for the VST Gen Device Registry."""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from storage import get_user_by_key_hash

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def generate_api_key() -> str:
    """Generate a cryptographically secure API key (vst_<40 hex chars>)."""
    return f"vst_{secrets.token_hex(20)}"


def hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key — safe to store in Firestore."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# FastAPI dependency: require authenticated user
# ---------------------------------------------------------------------------

async def require_auth(
    raw_key: Annotated[str | None, Security(API_KEY_HEADER)],
) -> dict:
    """
    FastAPI dependency. Validates X-API-Key header and returns the user record.
    Raises 401 if missing or invalid, 403 if revoked.
    """
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    key_hash = hash_key(raw_key)
    user = await get_user_by_key_hash(key_hash)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if user.get("revoked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has been revoked.",
        )
    return user
