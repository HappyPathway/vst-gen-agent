"""API key authentication and GitHub OAuth middleware for the VST Gen Device Registry."""

from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.request
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from storage import get_user_by_key_hash

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
GITHUB_BEARER = HTTPBearer(auto_error=False)

_GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "vst-gen-registry/1.0",
}

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
# GitHub OAuth token → user identity
# ---------------------------------------------------------------------------

def verify_github_token(token: str) -> dict:
    """
    Exchange a GitHub OAuth token for verified user identity.

    Calls GET /user (and GET /user/emails if the profile email is null).
    Requires 'read:user user:email' scopes on the token.

    Returns:
        { github_id: int, github_login: str, email: str }
    Raises HTTPException 401 if the token is invalid or expired.
    """
    headers = {**_GITHUB_API_HEADERS, "Authorization": f"Bearer {token}"}
    req = urllib.request.Request("https://api.github.com/user", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            user_data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub token invalid or expired (HTTP {exc.code}).",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not reach GitHub API: {exc}",
        ) from exc

    email: str | None = user_data.get("email")
    if not email:
        # Token has user:email scope — fetch primary verified email
        req2 = urllib.request.Request(
            "https://api.github.com/user/emails", headers=headers
        )
        try:
            with urllib.request.urlopen(req2, timeout=8) as resp:
                emails = json.loads(resp.read())
            primary = next(
                (e for e in emails if e.get("primary") and e.get("verified")), None
            )
            email = primary["email"] if primary else None
        except Exception:
            email = None

    return {
        "github_id": user_data["id"],
        "github_login": user_data["login"],
        "email": email or f"{user_data['login']}@users.noreply.github.com",
    }


async def require_github_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(GITHUB_BEARER)
    ],
) -> dict:
    """
    FastAPI dependency. Validates Authorization: Bearer <github_oauth_token>.
    Returns { github_id, github_login, email }.
    Requires the token to have 'read:user user:email' scopes.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization: Bearer <github_oauth_token> header is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_github_token(credentials.credentials)


# ---------------------------------------------------------------------------
# FastAPI dependency: require authenticated user (API key)
# ---------------------------------------------------------------------------

async def require_auth(
    raw_key: Annotated[str | None, Security(API_KEY_HEADER)],
) -> dict:
    """
    FastAPI dependency. Validates X-API-Key header and returns the user record.
    Raises 401 if missing or invalid, 403 if revoked.
    Injects '_key_hash' into the returned dict for downstream Firestore lookups.
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
    user["_key_hash"] = key_hash  # available to endpoints for Firestore lookups
    return user
