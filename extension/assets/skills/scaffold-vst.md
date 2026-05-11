---
name: scaffold-vst
description: "Scaffold a new VST plugin from templates. Use when: generating JUCE 8 plugin boilerplate for a new device; creating Elementary Audio plugin scaffolding; populating CMakeLists.txt, PluginProcessor, PluginEditor, and Makefile for a hardware MIDI controller; starting a new plugin project from nrpn_map.json and vision_output.json."
argument-hint: "Framework (juce|elementary|iplug2) and device folder path"
---

# Scaffold VST Plugin

Generates a complete, buildable plugin project from `nrpn_map.json` + `vision_output.json` using a framework template.

## When to Use

- You have completed the MIDI capture and coordinate mapping phases
- You are ready to generate source code files for a new device

## Prerequisites

- `nrpn_map.json` — MIDI parameter map from the `midi-capture` skill
- `vision_output.json` — Knob coordinate table from the `vision-to-coords` skill
- `panel.png` — Front panel image for the UI backdrop
- Framework installed on this machine (JUCE 8 / Node.js)

## Procedure

### 1. Choose framework

| Choice | When | Template folder |
|--------|------|-----------------|
| `juce` | Professional DAW plugin (VST3/AU/Standalone) | `templates/juce/` |
| `elementary` | Web-based, JS DSP, rapid prototyping | `templates/elementary/` |
| `iplug2` | WASM + browser deployment | `templates/iplug2/` |

If the user does not specify, default to **`juce`**.

### 2. Run the scaffolder

```bash
python3 tools/scaffold.py \
  --framework juce \
  --map nrpn_map.json \
  --coords vision_output.json \
  --panel panel.png \
  --output devices/<DeviceName>/
```

The script:
1. Reads `nrpn_map.json` to generate the parameter list (APVTS, NRPNs, etc.)
2. Reads `vision_output.json` to populate the `kKnobs[]` table in `PluginEditor.cpp`
3. Copies `panel.png` into the output folder as a binary asset
4. Substitutes all `{{DEVICE_NAME}}`, `{{MIDI_CHANNEL}}`, etc. placeholders in templates
5. Writes all source files to `devices/<DeviceName>/src/`

### 3. Build immediately

```bash
cd devices/<DeviceName> && make all
```

Fix any compilation errors (usually missing includes or mismatched param IDs).

### 4. Run the plugin

```bash
make run
```

Verify the panel backdrop loads and knobs appear at the correct positions.

## Template Variable Reference

| Placeholder | Source |
|-------------|--------|
| `{{DEVICE_NAME}}` | `nrpn_map.json` → `device` |
| `{{MIDI_CHANNEL}}` | `nrpn_map.json` → `midi_channel` |
| `{{PARAM_ARRAY}}` | Generated from `nrpn_map.json` → `params[]` |
| `{{KNOBS_ARRAY}}` | Generated from `vision_output.json` |
| `{{PANEL_WIDTH}}` | Panel image pixel width |
| `{{PANEL_HEIGHT}}` | Panel image pixel height |

## Reference

Script: [tools/scaffold.py](../../tools/scaffold.py)
JUCE templates: [templates/juce/](../../templates/juce/)
Elementary templates: [templates/elementary/](../../templates/elementary/)
