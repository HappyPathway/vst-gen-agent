"""Firestore data access layer for the VST Gen Device Registry."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore

_FIRESTORE_DB: firestore.AsyncClient | None = None

DEVICES_COLLECTION = "vst_gen_devices"
USERS_COLLECTION = "vst_gen_users"


# ---------------------------------------------------------------------------
# Client singletons
# ---------------------------------------------------------------------------

def get_db() -> firestore.AsyncClient:
    global _FIRESTORE_DB
    if _FIRESTORE_DB is None:
        _FIRESTORE_DB = firestore.AsyncClient()
    return _FIRESTORE_DB


# ---------------------------------------------------------------------------
# Device operations
# ---------------------------------------------------------------------------

async def list_devices(limit: int = 100, offset: int = 0,
                       include_stale: bool = False) -> list[dict]:
    db = get_db()
    query = db.collection(DEVICES_COLLECTION)
    if not include_stale:
        query = query.where("status", "==", "active")
    query = (
        query
        .order_by("submitted_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .offset(offset)
    )
    docs = [doc.to_dict() async for doc in query.stream()]
    # Strip owner PII for public listing
    for d in docs:
        d.pop("owner_email", None)
        d["owner"] = ""
    return docs


async def get_device(slug: str) -> dict | None:
    db = get_db()
    doc = await db.collection(DEVICES_COLLECTION).document(slug).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data.pop("owner_email", None)  # never expose raw email in public response
    data["owner"] = ""
    return data


async def get_device_with_owner(slug: str) -> dict | None:
    """Internal variant that includes owner_email (used for ownership checks)."""
    db = get_db()
    doc = await db.collection(DEVICES_COLLECTION).document(slug).get()
    return doc.to_dict() if doc.exists else None


async def create_device(slug: str, data: dict, owner_email: str,
                        panel_warning: str = "") -> None:
    db = get_db()
    payload = {
        **data,
        "slug": slug,
        "owner_email": owner_email,
        "submitted_at": datetime.now(UTC),
        "last_validated_at": datetime.now(UTC),
        "status": "active",
        "panel_warning": panel_warning,
        "upvotes": 0,
        "version": 1,
    }
    await db.collection(DEVICES_COLLECTION).document(slug).set(payload)


async def update_device(slug: str, data: dict) -> None:
    db = get_db()
    await db.collection(DEVICES_COLLECTION).document(slug).update({
        **data,
        "version": firestore.Increment(1),
    })


async def delete_device(slug: str) -> None:
    db = get_db()
    await db.collection(DEVICES_COLLECTION).document(slug).delete()


async def count_devices(include_stale: bool = False) -> int:
    db = get_db()
    query = db.collection(DEVICES_COLLECTION)
    if not include_stale:
        query = query.where("status", "==", "active")
    result = await query.count().get()
    return result[0][0].value


# ---------------------------------------------------------------------------
# User / API key operations
# ---------------------------------------------------------------------------

async def get_user_by_key_hash(key_hash: str) -> dict | None:
    db = get_db()
    doc = await db.collection(USERS_COLLECTION).document(key_hash).get()
    return doc.to_dict() if doc.exists else None


async def create_user(key_hash: str, email: str, display_name: str) -> None:
    db = get_db()
    await db.collection(USERS_COLLECTION).document(key_hash).set({
        "email": email,
        "display_name": display_name,
        "created_at": datetime.now(UTC),
        "device_slugs": [],
        "revoked": False,
    })


async def add_device_to_user(key_hash: str, slug: str) -> None:
    db = get_db()
    await db.collection(USERS_COLLECTION).document(key_hash).update({
        "device_slugs": firestore.ArrayUnion([slug]),
    })


# ---------------------------------------------------------------------------
# Revalidation helpers
# ---------------------------------------------------------------------------

async def list_all_with_github_repo() -> list[dict]:
    """Return all device docs that have a github_repo set (active or stale)."""
    db = get_db()
    query = db.collection(DEVICES_COLLECTION).where("github_repo", "!=", None)
    return [doc.to_dict() async for doc in query.stream()]


async def mark_device_stale(slug: str, reason: str) -> None:
    db = get_db()
    await db.collection(DEVICES_COLLECTION).document(slug).update({
        "status": "stale",
        "last_validated_at": datetime.now(UTC),
        "stale_reason": reason,
    })


async def restore_device_active(slug: str) -> None:
    db = get_db()
    await db.collection(DEVICES_COLLECTION).document(slug).update({
        "status": "active",
        "last_validated_at": datetime.now(UTC),
        "stale_reason": firestore.DELETE_FIELD,
    })
