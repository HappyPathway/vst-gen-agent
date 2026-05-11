---
name: midi-capture
description: "Capture NRPN/CC parameter values directly from hardware. Use when: learning MIDI parameters from a physical synthesizer; running the interactive knob-turn capture session; building nrpn_map.json for a new device; confirming MIDI implementation numbers against actual hardware."
argument-hint: "MIDI device name fragment (e.g. 'Take5', 'Rev2')"
---

# MIDI Parameter Capture

Interactively captures NRPN or CC parameter numbers directly from hardware by monitoring MIDI output while the user turns each knob.

## When to Use

- You need to confirm the actual NRPN/CC numbers a device sends (manufacturer docs are sometimes wrong)
- You are building `nrpn_map.json` for a new device from scratch
- You want to discover undocumented parameters

## Prerequisites

- Device connected via USB MIDI
- `mido` and `python-rtmidi` installed: `pip install mido python-rtmidi`
- MIDI Param Send enabled on device (consult manual — usually in Global settings)

## Procedure

### 1. List available MIDI ports

```bash
python3 tools/midi_capture.py --list
```

Verify your device appears in both input and output lists.

### 2. Run the interactive capture session

```bash
python3 tools/midi_capture.py --capture --device "Take5" --output nrpn_map.json
```

The tool will:
1. Prompt you for a parameter name (e.g. "cutoff")
2. Ask you to move the corresponding hardware knob through its full range
3. Detect and record the CC/NRPN numbers and value range
4. Ask for the next parameter

Repeat for every knob on the front panel.

### 3. Review and validate

After capture, open `nrpn_map.json` and verify:
- No duplicate NRPN numbers (unless two params share a number, like FM/OSC2 Level on the Take 5)
- Value ranges match the manual's specification
- All front-panel knobs are represented

### 4. Run validation

```bash
python3 tools/midi_capture.py --validate --map nrpn_map.json --device "Take5"
```

This sends each captured NRPN to the hardware and confirms the device responds.

## Output — `nrpn_map.json` Schema

```json
{
  "device": "Sequential Take 5",
  "captured": "2026-05-10",
  "midi_channel": 1,
  "params": [
    {
      "paramId": "cutoff",
      "label": "Filter Cutoff",
      "type": "nrpn",
      "msb": 0,
      "lsb": 29,
      "minVal": 0,
      "maxVal": 1023,
      "default": 1023
    }
  ]
}
```

## Reference

Script: [tools/midi_capture.py](../../tools/midi_capture.py)
Output schema: [references/nrpn-schema.json](./references/nrpn-schema.json)
