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
import time
import urllib.parse
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

# GitHub OAuth App client ID — set this after creating an OAuth App at
# https://github.com/settings/developers  (Application type: GitHub App or OAuth App)
# Required scopes: read:user  user:email
DEFAULT_GITHUB_CLIENT_ID = ""  # override with VST_GEN_GITHUB_CLIENT_ID env var or set-github-client-id


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


def get_github_client_id() -> str:
    return (
        os.environ.get("VST_GEN_GITHUB_CLIENT_ID")
        or load_config().get("github_client_id", DEFAULT_GITHUB_CLIENT_ID)
    )


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


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_login(args):
    """
    Authenticate via GitHub device flow, then register with the VST Gen registry.

    Flow:
      1. POST to github.com/login/device/code  (get user_code + device_code)
      2. User opens a URL and enters the user_code in their browser
      3. Poll github.com/login/oauth/access_token until authorized
      4. POST /auth/register-github with the GitHub token
      5. Save the returned vst_... API key to ~/.vst-gen-token
    """
    client_id = get_github_client_id()
    if not client_id:
        sys.exit(
            "No GitHub OAuth client ID configured.\n"
            "Set VST_GEN_GITHUB_CLIENT_ID env var or run:\n"
            "  python3 tools/registry_client.py set-github-client-id <CLIENT_ID>"
        )

    # Step 1: request device code
    code_data = urllib.parse.urlencode(
        {"client_id": client_id, "scope": "read:user user:email"}
    ).encode()
    req = urllib.request.Request(
        "https://github.com/login/device/code",
        data=code_data,
        headers={"Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        flow = json.loads(resp.read())

    user_code       = flow["user_code"]
    device_code     = flow["device_code"]
    verification_uri = flow.get("verification_uri", "https://github.com/login/device")
    interval        = flow.get("interval", 5)

    print(f"\n  1. Open: {verification_uri}")
    print(f"  2. Enter code: {user_code}\n")

    # Step 2: poll for the access token
    poll_payload = {
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    print("Waiting for GitHub authorization", end="", flush=True)
    github_token = None
    while True:
        time.sleep(interval)
        print(".", end="", flush=True)
        poll_data = urllib.parse.urlencode(poll_payload).encode()
        req2 = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=poll_data,
            headers={"Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2) as resp:
            result = json.loads(resp.read())

        error = result.get("error")
        if not error:
            github_token = result["access_token"]
            print()  # end the dots line
            break
        elif error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval = result.get("interval", interval + 5)
        elif error == "expired_token":
            sys.exit("\nDevice code expired. Please run login again.")
        elif error == "access_denied":
            sys.exit("\nAccess denied. Authorization cancelled.")
        else:
            sys.exit(f"\nUnexpected error from GitHub: {error}")

    # Step 3: register with the VST Gen registry
    url = get_registry_url().rstrip("/") + "/auth/register-github"
    req3 = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req3) as resp:
            reg = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        sys.exit(f"Registration failed (HTTP {e.code}): {detail}")

    api_key = reg.get("api_key", "")
    if not api_key:
        sys.exit("Registration failed — no key returned.")
    save_api_key(api_key)
    print(reg.get("message", "Done."))


def cmd_whoami(args):
    key = get_api_key()
    if not key:
        sys.exit("Not logged in. Run: python3 tools/registry_client.py login")
    resp = _request("GET", "/auth/me", api_key=key)
    print(f"GitHub:   @{resp.get('github_login', '(unknown)')}")
    print(f"Email:    {resp['email']}")
    print(f"Devices:  {', '.join(resp['device_slugs']) or '(none)'}")


def cmd_list(args):
    resp = _request("GET", "/devices")
    devices = resp.get("devices", [])
    if not devices:
        print("No devices in registry yet.")
        return
    print(f"{'Slug':<35}  {'Device':<35}  {'Params':>6}  Repo")
    print("-" * 100)
    for d in devices:
        repo = d.get("github_repo") or ""
        print(f"{d['slug']:<35}  {d['device']:<35}  {len(d.get('params', [])):>6}  {repo}")


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
    if args.repo:
        data["github_repo"] = args.repo
    method = "PUT" if args.update else "POST"
    resp = _request(method, f"/devices/{slug}" if args.update else "/devices",
                    body=data, api_key=key)
    print(f"\u2713 {'Updated' if args.update else 'Submitted'}: {resp['slug']} ({resp['device']})")
    if resp.get("github_repo"):
        print(f"  Plugin repo: https://github.com/{resp['github_repo']}")
        print(f"  Clone: git clone https://github.com/{resp['github_repo']}")



def cmd_pull(args):
    """Pull a device map; if a plugin repo is attached, offer to clone it."""
    resp = _request("GET", f"/devices/{args.slug}")
    output = Path(args.output)
    output.write_text(json.dumps(resp, indent=2))
    print(f"Saved NRPN map to {output}")
    repo = resp.get("github_repo")
    if repo:
        clone_url = f"https://github.com/{repo}"
        print(f"\nThis device has a pre-built plugin repo:")
        print(f"  {clone_url}")
        if not args.no_clone:
            answer = input(f"Clone plugin code into ./{repo.split('/')[-1]}? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                import subprocess
                subprocess.run(["git", "clone", clone_url], check=True)
            else:
                print(f"Skipped. To clone manually: git clone {clone_url}")
        else:
            print(f"To clone: git clone {clone_url}")


def cmd_set_github_client_id(args):
    cfg = load_config()
    cfg["github_client_id"] = args.client_id
    save_config(cfg)
    print(f"GitHub OAuth client ID set to: {args.client_id}")


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

    sub.add_parser("login",  help="Authenticate via GitHub device flow and register")
    sub.add_parser("whoami", help="Show current user profile")
    sub.add_parser("list",   help="List all devices in the registry")

    p_get = sub.add_parser("get", help="Fetch a device map by slug")
    p_get.add_argument("slug")
    p_get.add_argument("--output", "-o", help="Save to file instead of stdout")

    p_push = sub.add_parser("push", help="Submit or update a device map")
    p_push.add_argument("map", help="Path to nrpn_map.json")
    p_push.add_argument("--slug", help="Override slug (default: from JSON)")
    p_push.add_argument("--repo", metavar="OWNER/REPO",
                        help="Public GitHub repo containing the generated plugin code")
    p_push.add_argument("--update", action="store_true", help="PUT (update) instead of POST (create)")

    p_pull = sub.add_parser("pull", help="Pull a device map (and optionally clone the plugin repo)")
    p_pull.add_argument("slug")
    p_pull.add_argument("--output", "-o", default="nrpn_map.json")
    p_pull.add_argument("--no-clone", action="store_true",
                        help="Skip the git clone prompt even if a plugin repo is attached")

    p_url = sub.add_parser("set-url", help="Configure the registry base URL")
    p_url.add_argument("url", help="e.g. https://vst-gen-registry-xxx-uc.a.run.app")

    p_gid = sub.add_parser("set-github-client-id",
                           help="Store your GitHub OAuth App client ID")
    p_gid.add_argument("client_id", help="GitHub OAuth App client_id (20-char hex)")

    args = parser.parse_args()
    {
        "login":                  cmd_login,
        "whoami":                 cmd_whoami,
        "list":                   cmd_list,
        "get":                    cmd_get,
        "push":                   cmd_push,
        "pull":                   cmd_pull,
        "set-url":                cmd_set_url,
        "set-github-client-id":   cmd_set_github_client_id,
    }[args.command](args)


if __name__ == "__main__":
    main()
