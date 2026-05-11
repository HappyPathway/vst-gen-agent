#!/usr/bin/env python3
"""
scaffold.py — Generate a complete JUCE/Elementary plugin project from nrpn_map.json
and vision_output.json.

Usage:
  python3 scaffold.py --framework juce \
      --map nrpn_map.json \
      --coords vision_output.json \
      --panel panel.png \
      --output devices/MyDevice/
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


FRAMEWORKS = ("juce", "elementary", "iplug2")
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# Template substitution
# ---------------------------------------------------------------------------

def substitute(text: str, variables: dict[str, str]) -> str:
    """Replace {{KEY}} placeholders with values."""
    for key, val in variables.items():
        text = text.replace(f"{{{{{key}}}}}", val)
    return text


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------

def gen_juce_param_array(params: list[dict]) -> str:
    """Generate JUCE APVTS parameter layout entries."""
    lines = []
    for p in params:
        pid = p["paramId"]
        label = p.get("label", pid)
        lo = float(p.get("minVal", 0))
        hi = float(p.get("maxVal", 127))
        default = float(p.get("default", lo))
        lines.append(
            f'    std::make_unique<juce::AudioParameterFloat>(\n'
            f'        juce::ParameterID{{"{pid}", 1}},\n'
            f'        "{label}",\n'
            f'        juce::NormalisableRange<float>({lo:.0f}f, {hi:.0f}f, 1.f),\n'
            f'        {default:.0f}f)'
        )
    return ",\n".join(lines)


def gen_nrpn_table(params: list[dict]) -> str:
    """Generate the NrpnParam[] C++ array."""
    lines = []
    for p in params:
        pid = p["paramId"]
        if p["type"] == "nrpn":
            msb = p["msb"]
            lsb = p["lsb"]
            lo = p.get("minVal", 0)
            hi = p.get("maxVal", 1023)
        else:
            # CC → emulate as NRPN with msb=0
            msb = 0
            lsb = p.get("cc", 0)
            lo = p.get("minVal", 0)
            hi = p.get("maxVal", 127)
        lines.append(f'    {{"{pid}", {msb}, {lsb}, {lo}, {hi}}}')
    return ",\n".join(lines)


def gen_knobs_array(coords: list[dict], params: list[dict]) -> str:
    """Generate the kKnobs[] C++ constexpr array."""
    param_ids = [p["paramId"] for p in params]
    lines = []
    for i, c in enumerate(coords):
        pid = param_ids[i] if i < len(param_ids) else f"param_{i}"
        label = pid.upper()[:6]
        cx = c["x"]
        cy = c["y"]
        diam = c["r"] * 2
        lines.append(f'    {{"{pid}", "{label}", {cx}, {cy}, {diam}, false}}')
    return ",\n".join(lines)


def to_class_name(device_name: str) -> str:
    """'Sequential Take 5' → 'SequentialTake5'"""
    return re.sub(r"[^a-zA-Z0-9]", "", device_name.title())


# ---------------------------------------------------------------------------
# JUCE scaffold
# ---------------------------------------------------------------------------

def scaffold_juce(nrpn_map: dict, vision: dict, panel_src: Path, output_dir: Path):
    template_dir = TEMPLATES_DIR / "juce"
    if not template_dir.exists():
        sys.exit(f"JUCE templates not found at {template_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    src_dir = output_dir / "src"
    src_dir.mkdir(exist_ok=True)

    params = nrpn_map["params"]
    circles = vision.get("circles", [])
    device_name = nrpn_map["device"]
    class_name = to_class_name(device_name)
    midi_channel = nrpn_map.get("midi_channel", 1)

    # Panel image
    panel_dst = output_dir / "panel.png"
    shutil.copy2(panel_src, panel_dst)

    variables = {
        "DEVICE_NAME": device_name,
        "CLASS_NAME": class_name,
        "MIDI_CHANNEL": str(midi_channel),
        "PARAM_ARRAY": gen_juce_param_array(params),
        "NRPN_TABLE": gen_nrpn_table(params),
        "KNOBS_ARRAY": gen_knobs_array(circles, params),
        "PANEL_WIDTH": str(vision.get("width", 1281)),
        "PANEL_HEIGHT": str(vision.get("height", 365)),
    }

    # Copy & substitute all .tmpl files
    for tmpl in template_dir.rglob("*.tmpl"):
        rel = tmpl.relative_to(template_dir)
        # Strip .tmpl suffix, put source files under src/
        dest_name = rel.name.replace(".tmpl", "").replace("Device", class_name)
        if any(dest_name.endswith(ext) for ext in (".cpp", ".h")):
            dest = src_dir / dest_name
        else:
            dest = output_dir / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = substitute(tmpl.read_text(), variables)
        dest.write_text(text)
        print(f"  wrote {dest.relative_to(output_dir.parent)}")

    print(f"\nScaffold complete: {output_dir}")
    print(f"Build with:  cd {output_dir} && make all")


# ---------------------------------------------------------------------------
# Elementary Audio scaffold (stub — extend as needed)
# ---------------------------------------------------------------------------

def scaffold_elementary(nrpn_map: dict, vision: dict, panel_src: Path, output_dir: Path):
    template_dir = TEMPLATES_DIR / "elementary"
    if not template_dir.exists():
        sys.exit(f"Elementary templates not found at {template_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    device_name = nrpn_map["device"]
    class_name = to_class_name(device_name)
    variables = {
        "DEVICE_NAME": device_name,
        "CLASS_NAME": class_name,
        "MIDI_CHANNEL": str(nrpn_map.get("midi_channel", 1)),
    }

    for tmpl in template_dir.rglob("*.tmpl"):
        rel = tmpl.relative_to(template_dir)
        dest = output_dir / rel.name.replace(".tmpl", "")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(substitute(tmpl.read_text(), variables))
        print(f"  wrote {dest}")

    shutil.copy2(panel_src, output_dir / "panel.png")
    print(f"\nScaffold complete: {output_dir}")
    print(f"Run with:  cd {output_dir} && npm install && npm start")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scaffold a VST plugin from captured data")
    parser.add_argument("--framework", choices=FRAMEWORKS, default="juce",
                        help="Target framework (default: juce)")
    parser.add_argument("--map", required=True, help="Path to nrpn_map.json")
    parser.add_argument("--coords", required=True, help="Path to vision_output.json")
    parser.add_argument("--panel", required=True, help="Path to panel.png")
    parser.add_argument("--output", required=True, help="Output directory for the plugin")
    args = parser.parse_args()

    with open(args.map) as f:
        nrpn_map = json.load(f)
    with open(args.coords) as f:
        vision = json.load(f)
    panel_src = Path(args.panel)
    if not panel_src.exists():
        sys.exit(f"Panel image not found: {args.panel}")

    output_dir = Path(args.output)

    if args.framework == "juce":
        scaffold_juce(nrpn_map, vision, panel_src, output_dir)
    elif args.framework == "elementary":
        scaffold_elementary(nrpn_map, vision, panel_src, output_dir)
    else:
        sys.exit(f"Framework '{args.framework}' not yet implemented")


if __name__ == "__main__":
    main()
