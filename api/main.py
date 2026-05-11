"""
VST Gen Device Registry — FastAPI application.

Endpoints:
  GET  /                       — health check
  GET  /devices                — list all devices (public)
  GET  /devices/{slug}         — get a device map (public)
  POST /devices                — submit a device map (auth required)
  PUT  /devices/{slug}         — update a device map (auth + ownership)
  DELETE /devices/{slug}       — delete a device map (auth + ownership)
  POST /auth/register          — register email → returns API key
  GET  /auth/me                — validate token, return profile
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

import storage
from auth import generate_api_key, hash_key, require_auth
from github_verify import RepoNotPublicError, verify_github_repo_string
from models import (
    DeviceMapCreate,
    DeviceMapPublic,
    HealthResponse,
    ListDevicesResponse,
    RegisterRequest,
    RegisterResponse,
    UserProfile,
)

VERSION = "0.1.0"

app = FastAPI(
    title="VST Gen Device Registry",
    description="Shared NRPN/CC parameter maps for hardware synthesizers.",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # public read API
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version=VERSION)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """
    Register an email address and receive an API key.
    The key is returned ONCE — save it immediately.
    """
    raw_key = generate_api_key()
    key_hash = hash_key(raw_key)
    # Check for duplicate registration (same email already has a key)
    # We check by querying Firestore for a matching email
    db = storage.get_db()
    existing = db.collection(storage.USERS_COLLECTION).where(
        "email", "==", body.email
    ).limit(1)
    docs = [d async for d in existing.stream()]
    if docs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An API key already exists for this email. Check your `.vst-gen-token` file.",
        )
    await storage.create_user(key_hash, body.email, body.display_name)
    return RegisterResponse(
        api_key=raw_key,
        message=(
            "Save this key — it won't be shown again. "
            "Store it in your vst-gen-agent settings as 'registry.apiKey'."
        ),
    )


@app.get("/auth/me", response_model=UserProfile)
async def me(user: Annotated[dict, Depends(require_auth)]):
    return UserProfile(
        email=user["email"],
        display_name=user.get("display_name", ""),
        created_at=user["created_at"],
        device_slugs=user.get("device_slugs", []),
    )


# ---------------------------------------------------------------------------
# Device listing (public)
# ---------------------------------------------------------------------------

@app.get("/devices", response_model=ListDevicesResponse)
async def list_devices(limit: int = 50, offset: int = 0):
    if limit > 200:
        limit = 200
    devices = await storage.list_devices(limit=limit, offset=offset)
    total = await storage.count_devices()
    return ListDevicesResponse(
        devices=[DeviceMapPublic.from_device(d) for d in devices],
        total=total,
    )


@app.get("/devices/{slug}", response_model=DeviceMapPublic)
async def get_device(slug: str):
    device = await storage.get_device(slug)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device '{slug}' not found.")
    return DeviceMapPublic.from_device(device)


# ---------------------------------------------------------------------------
# Device submission (authenticated)
# ---------------------------------------------------------------------------

@app.post("/devices", response_model=DeviceMapPublic, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceMapCreate,
    user: Annotated[dict, Depends(require_auth)],
):
    existing = await storage.get_device(body.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device slug '{body.slug}' already exists. Use PUT to update.",
        )
    # Verify the GitHub repo is public before indexing
    if body.github_repo:
        try:
            body.github_repo = verify_github_repo_string(body.github_repo)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RepoNotPublicError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=str(exc)) from exc
    data = body.model_dump()
    await storage.create_device(body.slug, data, owner_email=user["email"])
    # Track on user profile
    key_hash = hash_key(user.get("_raw_key", ""))  # added by require_auth if needed
    await storage.add_device_to_user(user["_key_hash"], body.slug)
    device = await storage.get_device(body.slug)
    return DeviceMapPublic.from_device(device)


@app.put("/devices/{slug}", response_model=DeviceMapPublic)
async def update_device(
    slug: str,
    body: DeviceMapCreate,
    user: Annotated[dict, Depends(require_auth)],
):
    existing = await storage.get_device_with_owner(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Device '{slug}' not found.")
    if existing.get("owner_email") != user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this device entry.",
        )
    # Re-verify repo if it changed
    if body.github_repo:
        try:
            body.github_repo = verify_github_repo_string(body.github_repo)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RepoNotPublicError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=str(exc)) from exc
    await storage.update_device(slug, body.model_dump())
    device = await storage.get_device(slug)
    return DeviceMapPublic.from_device(device)


@app.delete("/devices/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    slug: str,
    user: Annotated[dict, Depends(require_auth)],
):
    existing = await storage.get_device_with_owner(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Device '{slug}' not found.")
    if existing.get("owner_email") != user["email"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this device entry.",
        )
    await storage.delete_device(slug)


# ---------------------------------------------------------------------------
# Panel image upload
# ---------------------------------------------------------------------------

@app.post("/devices/{slug}/panel", status_code=status.HTTP_200_OK)
async def upload_panel(
    slug: str,
    file: UploadFile = File(...),
    user: Annotated[dict, Depends(require_auth)] = None,
):
    """Upload or replace the panel.png for a device."""
    existing = await storage.get_device_with_owner(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Device '{slug}' not found.")
    if existing.get("owner_email") != user["email"]:
        raise HTTPException(status_code=403, detail="You do not own this device entry.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted.")
    image_bytes = await file.read()
    url = storage.upload_panel_image(slug, image_bytes, file.content_type)
    return {"panel_url": url}
