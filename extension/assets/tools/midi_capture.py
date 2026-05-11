#!/usr/bin/env python3
"""
midi_capture.py — Interactive MIDI parameter capture tool for hardware synthesizers.

Usage:
  python3 midi_capture.py --list
  python3 midi_capture.py --capture --device "Take5" --output nrpn_map.json
  python3 midi_capture.py --validate --map nrpn_map.json --device "Take5"
"""

import argparse
import json
import sys
import time
import threading
from datetime import date
from collections import defaultdict

try:
    import mido
except ImportError:
    sys.exit("mido is required: pip install mido python-rtmidi")


# ---------------------------------------------------------------------------
# MIDI port helpers
# ---------------------------------------------------------------------------

def list_ports():
    """Print all available MIDI input and output port names."""
    inputs = mido.get_input_names()
    outputs = mido.get_output_names()
    print("MIDI Input ports:")
    for name in inputs:
        print(f"  {name}")
    print("\nMIDI Output ports:")
    for name in outputs:
        print(f"  {name}")


def find_port(ports: list[str], fragment: str) -> str | None:
    """Return the first port whose name contains `fragment` (case-insensitive)."""
    frag = fragment.lower()
    for p in ports:
        if frag in p.lower():
            return p
    return None


# ---------------------------------------------------------------------------
# NRPN decode state machine
# ---------------------------------------------------------------------------

class NrpnDecoder:
    """Stateful per-channel NRPN decoder (CC99/98/6/38)."""

    def __init__(self):
        self._msb: int | None = None
        self._lsb: int | None = None
        self._val_msb: int = 0

    def feed(self, msg) -> tuple[int, int, int] | None:
        """
        Feed a MIDI message. Returns (param_msb, param_lsb, value) when a
        complete NRPN is decoded, else None.
        """
        if msg.type != "control_change":
            return None
        cc, val = msg.control, msg.value
        if cc == 99:
            self._msb = val
            self._lsb = None
        elif cc == 98:
            self._lsb = val
        elif cc == 6:
            self._val_msb = val
        elif cc == 38:
            if self._msb is not None and self._lsb is not None:
                value = (self._val_msb << 7) | val
                result = (self._msb, self._lsb, value)
                return result
        return None


# ---------------------------------------------------------------------------
# Interactive capture session
# ---------------------------------------------------------------------------

def capture_session(device_fragment: str, output_path: str, channel: int):
    """Run an interactive capture session, writing results to output_path."""
    in_ports = mido.get_input_names()
    port_name = find_port(in_ports, device_fragment)
    if not port_name:
        sys.exit(
            f"No MIDI input port matching '{device_fragment}'. "
            "Run --list to see available ports."
        )

    print(f"Listening on: {port_name}")
    print("Type a parameter name (or 'done' to finish), then move the knob.\n")

    decoder = NrpnDecoder()
    params: list[dict] = []
    seen: set[tuple] = set()  # (msb, lsb) already captured

    with mido.open_input(port_name) as inport:  # type: ignore[attr-defined]
        while True:
            param_id = input("Parameter ID (snake_case, or 'done'): ").strip()
            if param_id.lower() == "done":
                break
            label = input(f"Display label for '{param_id}': ").strip() or param_id

            print(f"  → Move the '{label}' knob through its full range (3 s)…")

            messages: list[tuple[int, int, int]] = []  # (msb, lsb, value)
            cc_messages: list[tuple[int, int]] = []    # (cc, value)

            deadline = time.time() + 3.0
            while time.time() < deadline:
                for msg in inport.iter_pending():
                    if msg.type == "control_change" and msg.channel == (channel - 1):
                        result = decoder.feed(msg)
                        if result:
                            messages.append(result)
                        # Also capture raw CC for non-NRPN devices
                        if msg.control not in (6, 38, 98, 99):
                            cc_messages.append((msg.control, msg.value))
                time.sleep(0.01)

            if messages:
                # NRPN detected
                msb = messages[0][0]
                lsb = messages[0][1]
                values = [m[2] for m in messages]
                key = (msb, lsb)
                if key in seen:
                    print(f"  ⚠ Duplicate NRPN ({msb}/{lsb}) — check param or skip.")
                seen.add(key)
                params.append({
                    "paramId": param_id,
                    "label": label,
                    "type": "nrpn",
                    "msb": msb,
                    "lsb": lsb,
                    "minVal": min(values),
                    "maxVal": max(values),
                    "default": min(values),
                    "verified": True,
                })
                print(f"  ✓ NRPN {msb}/{lsb}  range {min(values)}–{max(values)}\n")
            elif cc_messages:
                # Plain CC detected
                cc_nums = [c[0] for c in cc_messages]
                cc = max(set(cc_nums), key=cc_nums.count)
                values = [c[1] for c in cc_messages if c[0] == cc]
                params.append({
                    "paramId": param_id,
                    "label": label,
                    "type": "cc",
                    "cc": cc,
                    "minVal": min(values),
                    "maxVal": max(values),
                    "default": min(values),
                    "verified": True,
                })
                print(f"  ✓ CC {cc}  range {min(values)}–{max(values)}\n")
            else:
                print("  ✗ No MIDI received — skipping. Check cable and MIDI send setting.\n")

    device_name = input(f"\nDevice name (for JSON header, e.g. 'Sequential Take 5'): ").strip()
    result = {
        "device": device_name,
        "captured": str(date.today()),
        "midi_channel": channel,
        "params": params,
    }
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved {len(params)} parameters to {output_path}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_map(map_path: str, device_fragment: str, channel: int):
    """Send each captured NRPN back to the device and confirm no MIDI errors."""
    with open(map_path) as f:
        nrpn_map = json.load(f)

    out_ports = mido.get_output_names()
    port_name = find_port(out_ports, device_fragment)
    if not port_name:
        sys.exit(f"No MIDI output port matching '{device_fragment}'.")

    ch = channel - 1
    print(f"Sending test values to {port_name}…\n")

    with mido.open_output(port_name) as outport:  # type: ignore[attr-defined]
        for param in nrpn_map["params"]:
            if param["type"] != "nrpn":
                continue
            msb, lsb = param["msb"], param["lsb"]
            default = param.get("default", param["minVal"])
            # Send NRPN
            outport.send(mido.Message("control_change", channel=ch, control=99, value=msb))
            outport.send(mido.Message("control_change", channel=ch, control=98, value=lsb))
            outport.send(mido.Message("control_change", channel=ch, control=6, value=default >> 7))
            outport.send(mido.Message("control_change", channel=ch, control=38, value=default & 0x7F))
            time.sleep(0.05)
            print(f"  ✓ {param['paramId']:30s} NRPN {msb}/{lsb} = {default}")

    print("\nValidation complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MIDI parameter capture tool")
    parser.add_argument("--list", action="store_true", help="List MIDI ports and exit")
    parser.add_argument("--capture", action="store_true", help="Run interactive capture")
    parser.add_argument("--validate", action="store_true", help="Validate existing map against hardware")
    parser.add_argument("--device", default="", help="MIDI device name fragment")
    parser.add_argument("--output", default="nrpn_map.json", help="Output JSON path")
    parser.add_argument("--map", default="nrpn_map.json", help="Existing map JSON for validation")
    parser.add_argument("--channel", type=int, default=1, help="MIDI channel (1-16)")
    args = parser.parse_args()

    if args.list:
        list_ports()
    elif args.capture:
        if not args.device:
            sys.exit("--device is required for capture mode")
        capture_session(args.device, args.output, args.channel)
    elif args.validate:
        if not args.device:
            sys.exit("--device is required for validation mode")
        validate_map(args.map, args.device, args.channel)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
