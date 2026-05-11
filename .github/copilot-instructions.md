# VST Gen Agent — Repository Instructions

This repository contains the `@vst-gen` VS Code Copilot agent and supporting tools for
generating VST3/AU/Standalone MIDI controller plugins from hardware synthesizer front panels.

## How This Repo Works

| Folder | Purpose |
|--------|---------|
| `.github/agents/` | VS Code Copilot custom agent definitions |
| `.github/skills/` | Agent skill files (SKILL.md + supporting scripts) |
| `.github/prompts/` | Slash-command prompt files (e.g. `/new-device`) |
| `tools/` | Python CLI tools (midi_capture.py, vision_coords.py, scaffold.py, registry_client.py, seed_registry.py) |
| `templates/juce/` | JUCE 8 plugin boilerplate templates (`.tmpl` files) |
| `templates/elementary/` | Elementary Audio plugin boilerplate templates |
| `devices/` | Generated device-specific plugin projects (git-ignored by default) |

## Quick Start

1. Open this repo in VS Code alongside your target device workspace.
2. Type `@vst-gen /new-device` in GitHub Copilot Chat.
3. Follow the guided workflow: provide device name, panel image, and manual.
4. The agent runs the MIDI capture → coordinate detection → scaffold pipeline.
5. Build with `make run` from the generated device folder.

## Adding a New Device Manually

```bash
# 1. Capture NRPN params from hardware
python3 tools/midi_capture.py --capture --device "MyDevice" --output my_nrpn_map.json

# 2. Detect knob positions in panel photo
python3 tools/vision_coords.py --image my_panel.png --scale 0.5 --output my_coords.json

# 3. Scaffold the plugin
python3 tools/scaffold.py \
  --framework juce \
  --map my_nrpn_map.json \
  --coords my_coords.json \
  --panel my_panel.png \
  --output devices/MyDevice/

# 4. Build and run
cd devices/MyDevice && make run

# 5. Share your capture
python3 tools/registry_client.py push my_nrpn_map.json
```

## Device Registry

The shared community registry at `https://vst-gen-registry-<hash>-uc.a.run.app` stores pre-captured device maps:

```bash
python3 tools/registry_client.py list            # browse
python3 tools/registry_client.py pull <slug>     # download
python3 tools/registry_client.py login           # register / get API key
python3 tools/registry_client.py push nrpn.json  # contribute
```

Deploy the registry yourself:
```bash
cd terraform && terraform init -backend-config=gcs.tfbackend && terraform apply
```

## Environment Requirements

- macOS 13+ (for VST3/AU/Standalone)
- Xcode Command Line Tools
- CMake 3.22+, Ninja (`brew install cmake ninja`)
- Python 3.11+ with: `pip install pillow numpy opencv-python-headless mido python-rtmidi`
- Node.js 20+ (for Elementary Audio templates only)

## macOS 15+ Note

On macOS 15 (Sequoia) and later, the CLT stub for C++ stdlib headers is missing.
The Makefile automatically sets `CPLUS_INCLUDE_PATH` to the SDK path. If you see
`#include <string>` errors, verify the SDK path in the Makefile matches your installed SDK:

```bash
ls /Library/Developer/CommandLineTools/SDKs/
```
