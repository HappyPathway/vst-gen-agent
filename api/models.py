"""Pydantic models for the VST Gen Device Registry API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# NRPN / CC parameter entry
# ---------------------------------------------------------------------------

class NrpnParamEntry(BaseModel):
    paramId: str
    label: str
    type: Literal["nrpn", "cc"]
    # NRPN fields
    msb: int | None = None
    lsb: int | None = None
    # CC field
    cc: int | None = None
    minVal: int = 0
    maxVal: int = 127
    default: int | None = None
    verified: bool = False


# ---------------------------------------------------------------------------
# Device NRPN map (the shared unit)
# ---------------------------------------------------------------------------

class DeviceMap(BaseModel):
    slug: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$",
        description="URL-safe identifier, e.g. 'sequential-take5'",
    )
    device: str = Field(..., description="Human-readable device name, e.g. 'Sequential Take 5'")
    manufacturer: str = ""
    captured: str = ""           # ISO date
    midi_channel: int = 1
    notes: list[str] = []
    params: list[NrpnParamEntry]
    # Optional GitHub plugin repo — must be public, verified at submission time
    github_repo: Optional[str] = Field(
        default=None,
        description="Public GitHub repo storing the generated plugin code, e.g. 'HappyPathway/Take5-VST'",
    )
    # Metadata set by server
    owner: str = ""              # contributor email (obfuscated in public responses)
    submitted_at: datetime | None = None
    upvotes: int = 0
    version: int = 1

    @property
    def plugin_clone_url(self) -> Optional[str]:
        """HTTPS clone URL derived from github_repo, if present."""
        if self.github_repo:
            return f"https://github.com/{self.github_repo}"
        return None

    @property
    def panel_url(self) -> Optional[str]:
        """Raw panel.png URL served directly from the GitHub repo (free CDN)."""
        if self.github_repo:
            return f"https://raw.githubusercontent.com/{self.github_repo}/HEAD/panel.png"
        return None


class DeviceMapPublic(DeviceMap):
    """Variant returned to unauthenticated callers — owner is masked."""
    owner: str = ""              # always empty for public responses
    plugin_clone_url: Optional[str] = None
    panel_url: Optional[str] = None

    @classmethod
    def from_device(cls, data: dict) -> "DeviceMapPublic":
        obj = cls(**data)
        if obj.github_repo:
            obj.plugin_clone_url = f"https://github.com/{obj.github_repo}"
            obj.panel_url = f"https://raw.githubusercontent.com/{obj.github_repo}/HEAD/panel.png"
        return obj


class DeviceMapCreate(BaseModel):
    """Payload for POST /devices — owner derived from API key."""
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")
    device: str
    manufacturer: str = ""
    captured: str = ""
    midi_channel: int = 1
    notes: list[str] = []
    params: list[NrpnParamEntry]
    github_repo: Optional[str] = Field(
        default=None,
        description="Public GitHub repo for the generated plugin, e.g. 'HappyPathway/Take5-VST'",
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = ""


class RegisterResponse(BaseModel):
    api_key: str = Field(
        ..., description="Your API key. Save this — it won't be shown again."
    )
    message: str = "Registration successful."


class UserProfile(BaseModel):
    email: str
    display_name: str
    created_at: datetime
    device_slugs: list[str] = []


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class ListDevicesResponse(BaseModel):
    devices: list[DeviceMapPublic]
    total: int
