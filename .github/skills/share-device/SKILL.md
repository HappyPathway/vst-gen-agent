---
name: share-device
description: "Share a captured device NRPN map to the community registry, or pull an existing device from the registry. Use when: uploading a completed nrpn_map.json to the shared registry; downloading a device map that someone else has already captured; checking if a device already exists before capturing from scratch."
argument-hint: "Device slug or nrpn_map.json path to upload"
---

# Share Device — Community Registry

Publish your captured device NRPN/CC map to the shared registry so other `@vst-gen` users can skip the hardware capture step, or pull a pre-captured device to save time.

## When to Use

**Push** — You completed MIDI capture and want to contribute the map
**Pull** — You want to use someone else's capture for a device you own

## Prerequisites

- `python3 tools/registry_client.py whoami` returns your profile (you're logged in)
- If not logged in: run the `/login` prompt first

## Procedure — Push (share your capture)

### 1. Verify your nrpn_map.json is complete

Open `nrpn_map.json` and confirm:
- `device` field is the full brand + model name
- All front-panel knobs are present
- `verified: true` on at least the majority of params

### 2. Check if the device already exists

```bash
python3 tools/registry_client.py list | grep <slug>
```

If it exists:
- Fetch it and compare: `python3 tools/registry_client.py get <slug>`
- If yours has more params or corrections, use `--update`

### 3. Push to registry

```bash
python3 tools/registry_client.py push nrpn_map.json
```

Or with explicit slug:
```bash
python3 tools/registry_client.py push nrpn_map.json --slug sequential-take5
```

### 4. Upload panel image (optional but recommended)

```bash
python3 tools/registry_client.py upload-panel <slug> panel.png
```

---

## Procedure — Pull (use existing capture)

### 1. Browse available devices

```bash
python3 tools/registry_client.py list
```

### 2. Pull the device map

```bash
python3 tools/registry_client.py pull <slug> --output nrpn_map.json
```

Then continue directly to the `scaffold-vst` skill — skip the `midi-capture` step.

---

## Registry URL

The live registry is at: `https://vst-gen-registry-<hash>-uc.a.run.app`

To configure:
```bash
python3 tools/registry_client.py set-url https://vst-gen-registry-<hash>-uc.a.run.app
```

Or set the environment variable: `export VST_GEN_REGISTRY_URL=https://...`
