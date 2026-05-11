#!/usr/bin/env python3
"""
seed_registry.py — Seed the VST Gen Device Registry from iron-static/database/midi_params/.

Converts the local midi_params/*.json files (which may have various schemas)
to the registry API format and submits them.

Usage:
  python3 tools/seed_registry.py \
    --source /path/to/iron-static/database/midi_params/ \
    --api-key vst_<your-key>

  # Dry run (print normalized JSON without submitting)
  python3 tools/seed_registry.py --source /path/to/midi_params/ --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema normalizers
# ---------------------------------------------------------------------------

def normalize_take5(raw: dict) -> dict | None:
    """Convert take5.json (CC + NRPN dicts) → registry DeviceMapCreate."""
    params = []

    # NRPN params
    nrpn_sec = raw.get("nrpn_params", {})
    for nrpn_str, p in nrpn_sec.get("params", {}).items():
        parts = nrpn_str.split("/") if "/" in nrpn_str else [None, nrpn_str]
        msb = int(parts[0]) if parts[0] else 0
        lsb = int(parts[-1])
        rng = p.get("range", "0-127").split("-")
        params.append({
            "paramId": _make_param_id(p["name"]),
            "label": p["name"],
            "type": "nrpn",
            "msb": msb,
            "lsb": lsb,
            "minVal": int(rng[0]),
            "maxVal": int(rng[-1]),
            "verified": True,
        })

    return {
        "slug": "sequential-take5",
        "device": raw.get("name", "Sequential Take 5"),
        "manufacturer": "Sequential",
        "captured": raw.get("captured", ""),
        "midi_channel": 1,
        "notes": raw.get("notes", []),
        "params": params,
    } if params else None


def normalize_generic_nrpn(raw: dict, slug: str) -> dict | None:
    """Generic converter for {params: {N: {name, nrpn_a, value_range}}} schema (Rev2, etc.)."""
    params_raw = raw.get("params", {})
    params = []

    for _key, p in params_raw.items():
        if not isinstance(p, dict):
            continue
        nrpn_a = p.get("nrpn_a")
        if nrpn_a is None:
            continue
        rng = str(p.get("value_range", "0-127")).split("-")
        params.append({
            "paramId": _make_param_id(p.get("name", f"param_{_key}")),
            "label": p.get("name", f"param_{_key}"),
            "type": "nrpn",
            "msb": 0,
            "lsb": int(nrpn_a),
            "minVal": int(rng[0]),
            "maxVal": int(rng[-1]),
            "verified": True,
        })

    instrument = raw.get("instrument", slug)
    name = raw.get("name", instrument.replace("-", " ").title())
    return {
        "slug": slug,
        "device": name,
        "manufacturer": _guess_manufacturer(slug),
        "captured": "",
        "midi_channel": 1,
        "notes": raw.get("notes", []),
        "params": params,
    } if params else None


def normalize_cc_list(raw: dict, slug: str) -> dict | None:
    """Converter for flat list of CC params [{cc, name, range}, ...]."""
    params = []
    for p in raw.get("params", []):
        if "cc" not in p:
            continue
        rng = str(p.get("range", "0-127")).split("-")
        params.append({
            "paramId": _make_param_id(p.get("name", f"cc{p['cc']}")),
            "label": p.get("name", f"CC {p['cc']}"),
            "type": "cc",
            "cc": int(p["cc"]),
            "minVal": int(rng[0]),
            "maxVal": int(rng[-1]),
            "verified": True,
        })

    name = raw.get("name", slug.replace("-", " ").title())
    return {
        "slug": slug,
        "device": name,
        "manufacturer": _guess_manufacturer(slug),
        "captured": "",
        "midi_channel": 1,
        "notes": raw.get("notes", []),
        "params": params,
    } if params else None


def _make_param_id(name: str) -> str:
    """'Filter Cutoff' → 'filter_cutoff'"""
    return name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")[:60]


def _guess_manufacturer(slug: str) -> str:
    manufacturers = {
        "sequential": "Sequential",
        "elektron": "Elektron",
        "arturia": "Arturia",
        "moog": "Moog",
        "roland": "Roland",
        "korg": "Korg",
        "dave-smith": "Dave Smith Instruments",
    }
    for key, mfr in manufacturers.items():
        if key in slug:
            return mfr
    return ""


# ---------------------------------------------------------------------------
# Auto-detect schema and normalize
# ---------------------------------------------------------------------------

def normalize(raw: dict, slug: str) -> dict | None:
    # Take 5 — has both cc_params + nrpn_params sections
    if "nrpn_params" in raw and slug == "take5":
        return normalize_take5(raw)

    # Rev2-style — params dict keyed by index, with nrpn_a
    if isinstance(raw.get("params"), dict):
        sample = next(iter(raw["params"].values()), {})
        if "nrpn_a" in sample:
            return normalize_generic_nrpn(raw, slug)

    # Flat CC list
    if isinstance(raw.get("params"), list):
        return normalize_cc_list(raw, slug)

    return None


# ---------------------------------------------------------------------------
# HTTP submit
# ---------------------------------------------------------------------------

def submit(payload: dict, api_key: str, registry_url: str, update: bool = False) -> None:
    slug = payload["slug"]
    method = "PUT" if update else "POST"
    url = registry_url.rstrip("/") + (f"/devices/{slug}" if update else "/devices")
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  ✓ {method} {slug}  ({result.get('device')})")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        print(f"  ✗ {slug}: HTTP {e.code} — {detail}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import os

    parser = argparse.ArgumentParser(description="Seed device registry from midi_params dir")
    parser.add_argument("--source", required=True, help="Path to midi_params/ directory")
    parser.add_argument("--api-key", help="Registry API key (or set VST_GEN_API_KEY env)")
    parser.add_argument("--registry-url",
                        default=os.environ.get("VST_GEN_REGISTRY_URL",
                                               "http://localhost:8080"),
                        help="Registry base URL")
    parser.add_argument("--update", action="store_true",
                        help="PUT (update) instead of POST (create)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print normalized JSON, do not submit")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("VST_GEN_API_KEY")
    if not api_key and not args.dry_run:
        sys.exit("--api-key or VST_GEN_API_KEY required (unless --dry-run)")

    source = Path(args.source)
    if not source.is_dir():
        sys.exit(f"Not a directory: {source}")

    for json_file in sorted(source.glob("*.json")):
        slug = json_file.stem
        print(f"\nProcessing {json_file.name} (slug: {slug})")
        raw = json.loads(json_file.read_text())

        payload = normalize(raw, slug)
        if payload is None:
            print(f"  ⚠ Could not normalize — skipping")
            continue

        print(f"  Params: {len(payload['params'])}")

        if args.dry_run:
            print(json.dumps(payload, indent=2)[:500] + "…")
        else:
            submit(payload, api_key, args.registry_url, update=args.update)

    print("\nDone.")


if __name__ == "__main__":
    main()
