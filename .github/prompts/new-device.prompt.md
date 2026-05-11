---
name: new-device
description: "Start the full workflow to generate a VST plugin for a new hardware MIDI device. Guides through: device info gathering, NRPN/CC parameter capture, front-panel screenshot analysis, and JUCE/Elementary plugin scaffolding."
argument-hint: "Device name (e.g. 'Sequential Prophet 6')"
---

# New Device — VST Plugin Generation Workflow

You are the `@vst-gen` agent starting the full device-to-plugin pipeline.

## Step 1 — Gather device assets

Ask the user for the following with `vscode_askQuestions`:

1. **Device name** — full brand + model (e.g. "Sequential Prophet 6")
2. **Front-panel image** — path to a high-res photo or screenshot of the hardware front panel
3. **Manual or MIDI Implementation** — PDF path, URL, or "I'll paste the table"
4. **MIDI channel** — default 1; ask if the user knows it's different
5. **Target framework** — JUCE 8 (default) or Elementary Audio (web-first)

Do not proceed until at least device name and panel image are provided.

## Step 2 — Check the community registry

Before any hardware capture, check if this device is already in the registry:

```bash
python3 tools/registry_client.py get <slug>
```

If found → pull it, skip to Step 4 (coordinate mapping).
If not found → continue to Step 3.

## Step 3 — Extract parameters

If a manual is provided, invoke the `extract-params` skill to build a preliminary parameter table.
If no manual is available, skip to Step 3 and capture directly from hardware.

## Step 4 — Capture NRPN values from hardware

If the registry check (Step 2) returned a device map, skip this step.
Otherwise, invoke the `midi-capture` skill:

Invoke the `midi-capture` skill:
- Run `tools/midi_capture.py --capture --device "<device_name>" --output nrpn_map.json`
- Walk the user through touching each knob
- Save to `nrpn_map.json`

## Step 5 — Map screenshot coordinates

Invoke the `vision-to-coords` skill:
- Run `tools/vision_coords.py --image <panel_image> --scale 0.5 --output vision_output.json`
- Open `vision_annotated.png` so the user can verify detections
- Ask user to confirm or correct any missed/false knob positions

## Step 6 — Scaffold the plugin

Invoke the `scaffold-vst` skill:
- Run `tools/scaffold.py --framework <framework> --map nrpn_map.json --coords vision_output.json --panel <panel_image> --output devices/<DeviceName>/`

## Step 7 — Build and validate

```bash
cd devices/<DeviceName> && make run
```

Report any build errors and fix them. Confirm knob positions look correct in the running plugin.

## Step 8 — Share back to the registry

If the device wasn't already in the registry, use the `share-device` skill:

```bash
python3 tools/registry_client.py push nrpn_map.json
python3 tools/registry_client.py upload-panel <slug> panel.png
```

Ask the user for consent before pushing.

## Completion checklist

- [ ] `nrpn_map.json` — all front-panel knobs captured and verified
- [ ] `vision_output.json` — knob coordinates extracted and reviewed
- [ ] `devices/<DeviceName>/` — plugin builds without errors
- [ ] Plugin launches with panel backdrop
- [ ] Moving a knob sends the correct NRPN to hardware
