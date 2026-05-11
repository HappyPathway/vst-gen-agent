#!/usr/bin/env python3
"""
registry_client.py — VST Gen Device Registry CLI tool.

Lets the @vst-gen agent (and users directly) interact with the shared
device NRPN/CC parameter registry hosted on Cloud Run.

Usage:
  python3 tools/registry_client.py login
  python3 tools/registry_client.py list
  python3 tools/registry_client.py get sequential-take5
  python3 tools/registry_client.py push nrpn_map.json
  python3 tools/registry_client.py upload-panel sequential-take5 panel.png
  python3 tools/registry_client.py pull sequential-take5 --output nrpn_map.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass  # stdlib — always available

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_REGISTRY_URL = "https://vst-gen-registry-<hash>-uc.a.run.app"
TOKEN_FILE = Path.home() / ".vst-gen-token"
CONFIG_FILE = Path.home() / ".vst-gen-config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    CONFIG_FILE.chmod(0o600)


def get_registry_url() -> str:
    return os.environ.get("VST_GEN_REGISTRY_URL") or load_config().get(
        "registry_url", DEFAULT_REGISTRY_URL
    )


def get_api_key() -> str | None:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return os.environ.get("VST_GEN_API_KEY")


def save_api_key(key: str) -> None:
    TOKEN_FILE.write_text(key)
    TOKEN_FILE.chmod(0o600)
    print(f"API key saved to {TOKEN_FILE}")


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no requests dependency)
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: dict | None = None,
             api_key: str | None = None) -> dict:
    url = get_registry_url().rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        sys.exit(f"HTTP {e.code}: {detail}")


def _upload_file(path: str, file_path: Path) -> dict:
    """Multipart file upload using urllib (minimal, no requests)."""
    import mimetypes
    import uuid

    url = get_registry_url().rstrip("/") + path
    api_key = get_api_key()

    boundary = uuid.uuid4().hex
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_login(args):
    """Register an email address and store the returned API key."""
    email = input("Email address: ").strip()
    display = input("Display name (optional): ").strip()
    resp = _request("POST", "/auth/register", {"email": email, "display_name": display})
    api_key = resp.get("api_key", "")
    if not api_key:
        sys.exit("Registration failed — no key returned.")
    save_api_key(api_key)
    print(resp.get("message", "Done."))


def cmd_whoami(args):
    key = get_api_key()
    if not key:
        sys.exit("Not logged in. Run: python3 tools/registry_client.py login")
    resp = _request("GET", "/auth/me", api_key=key)
    print(f"Email:    {resp['email']}")
    print(f"Name:     {resp['display_name']}")
    print(f"Devices:  {', '.join(resp['device_slugs']) or '(none)'}")


def cmd_list(args):
    resp = _request("GET", "/devices")
    devices = resp.get("devices", [])
    if not devices:
        print("No devices in registry yet.")
        return
    print(f"{'Slug':<35}  {'Device':<40}  Params")
    print("-" * 85)
    for d in devices:
        print(f"{d['slug']:<35}  {d['device']:<40}  {len(d.get('params', []))}")


def cmd_get(args):
    resp = _request("GET", f"/devices/{args.slug}")
    if args.output:
        Path(args.output).write_text(json.dumps(resp, indent=2))
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(resp, indent=2))


def cmd_push(args):
    key = get_api_key()
    if not key:
        sys.exit("Not logged in. Run: python3 tools/registry_client.py login")
    data = json.loads(Path(args.map).read_text())
    # Normalize to API schema
    slug = args.slug or data.get("slug") or data.get("instrument")
    if not slug:
        sys.exit("Could not determine slug. Use --slug or add 'slug' to the JSON.")
    data["slug"] = slug
    method = "PUT" if args.update else "POST"
    resp = _request(method, f"/devices/{slug}" if args.update else "/devices",
                    body=data, api_key=key)
    print(f"✓ {'Updated' if args.update else 'Submitted'}: {resp['slug']} ({resp['device']})")


def cmd_upload_panel(args):
    key = get_api_key()
    if not key:
        sys.exit("Not logged in.")
    panel = Path(args.panel)
    if not panel.exists():
        sys.exit(f"File not found: {panel}")
    resp = _upload_file(f"/devices/{args.slug}/panel", panel)
    print(f"✓ Panel image uploaded: {resp.get('panel_url')}")


def cmd_pull(args):
    cmd_get(args)  # pull = get with mandatory --output


def cmd_set_url(args):
    cfg = load_config()
    cfg["registry_url"] = args.url
    save_config(cfg)
    print(f"Registry URL set to: {args.url}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="VST Gen Device Registry client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login",  help="Register email → receive API key")
    sub.add_parser("whoami", help="Show current user profile")
    sub.add_parser("list",   help="List all devices in the registry")

    p_get = sub.add_parser("get", help="Fetch a device map by slug")
    p_get.add_argument("slug")
    p_get.add_argument("--output", "-o", help="Save to file instead of stdout")

    p_push = sub.add_parser("push", help="Submit or update a device map")
    p_push.add_argument("map", help="Path to nrpn_map.json")
    p_push.add_argument("--slug", help="Override slug (default: from JSON)")
    p_push.add_argument("--update", action="store_true", help="PUT (update) instead of POST (create)")

    p_panel = sub.add_parser("upload-panel", help="Upload panel.png for a device")
    p_panel.add_argument("slug")
    p_panel.add_argument("panel", help="Path to panel.png")

    p_pull = sub.add_parser("pull", help="Pull a device map to a local file")
    p_pull.add_argument("slug")
    p_pull.add_argument("--output", "-o", default="nrpn_map.json")

    p_url = sub.add_parser("set-url", help="Configure the registry base URL")
    p_url.add_argument("url", help="e.g. https://vst-gen-registry-xxx-uc.a.run.app")

    args = parser.parse_args()
    {
        "login":         cmd_login,
        "whoami":        cmd_whoami,
        "list":          cmd_list,
        "get":           cmd_get,
        "push":          cmd_push,
        "upload-panel":  cmd_upload_panel,
        "pull":          cmd_pull,
        "set-url":       cmd_set_url,
    }[args.command](args)


if __name__ == "__main__":
    main()
