---
name: extract-params
description: "Extract parameter names, MIDI CC/NRPN numbers, and ranges from a device manual. Use when: parsing a hardware synth user manual or MIDI implementation chart; building the initial parameter list before hardware capture; reading a PDF or URL for CC/NRPN documentation."
argument-hint: "Path to PDF or URL of device manual"
---

# Extract Parameters from Manual

Parses a hardware synth manual (PDF, URL, or pasted text) to build the initial parameter table before doing hardware capture.

## When to Use

- You have the device manual and want to build a preliminary parameter list
- You need to cross-reference confirmed hardware captures against documented ranges

## Procedure

### 1. Provide the MIDI Implementation section

Open the manual and navigate to the **MIDI Implementation Chart** (usually an appendix). Either:
- Paste the text directly into chat, or
- Provide a file path or URL

### 2. Extract the table

For each parameter, the agent identifies:
- **Parameter name** (knob/slider label on the front panel)
- **MIDI type**: CC (single byte 0–127) or NRPN (14-bit, 0–16383)
- **NRPN MSB / LSB** (for NRPN parameters)
- **CC number** (for CC parameters)
- **Value range** (e.g. 0–127 or 0–1023)
- **Default value**

### 3. Output as JSON

Write `nrpn_map_draft.json` using the schema from the `midi-capture` skill. Label all parameters as "unverified" until hardware capture confirms them.

### 4. Flag discrepancies

If the manual is ambiguous (duplicate numbers, undocumented ranges, missing default values), flag each one for follow-up during the hardware capture phase.

## Tips

- Sequential / Dave Smith instruments: NRPN is preferred over CC for full 14-bit resolution
- Elektron devices: Often use CC with specific patterns per track
- Arturia: Mix of CC and NRPN depending on generation
- Moog: Mostly CC (some models have NRPN for specific parameters)
