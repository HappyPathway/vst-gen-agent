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

## Step 2 — Extract parameters

If a manual is provided, invoke the `extract-params` skill to build a preliminary parameter table.
If no manual is available, skip to Step 3 and capture directly from hardware.

## Step 3 — Capture NRPN values from hardware

Invoke the `midi-capture` skill:
- Run `tools/midi_capture.py --capture --device "<device_name>" --output nrpn_map.json`
- Walk the user through touching each knob
- Save to `nrpn_map.json`

## Step 4 — Map screenshot coordinates

Invoke the `vision-to-coords` skill:
- Run `tools/vision_coords.py --image <panel_image> --scale 0.5 --output vision_output.json`
- Open `vision_annotated.png` so the user can verify detections
- Ask user to confirm or correct any missed/false knob positions

## Step 5 — Scaffold the plugin

Invoke the `scaffold-vst` skill:
- Run `tools/scaffold.py --framework <framework> --map nrpn_map.json --coords vision_output.json --panel <panel_image> --output devices/<DeviceName>/`

## Step 6 — Build and validate

```bash
cd devices/<DeviceName> && make run
```

Report any build errors and fix them. Confirm knob positions look correct in the running plugin.

## Completion checklist

- [ ] `nrpn_map.json` — all front-panel knobs captured and verified
- [ ] `vision_output.json` — knob coordinates extracted and reviewed
- [ ] `devices/<DeviceName>/` — plugin builds without errors
- [ ] Plugin launches with panel backdrop
- [ ] Moving a knob sends the correct NRPN to hardware
