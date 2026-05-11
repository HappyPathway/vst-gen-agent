# VST Gen Agent

Generate VST3/AU/Standalone MIDI controller plugins from hardware synthesizer front panels.
Uses JUCE 8 (primary) or Elementary Audio (web-first). Works with any NRPN/CC device.

## Quick Start

```
@vst-gen /new-device
```

Then follow the guided workflow to capture MIDI parameters, detect knob positions, and scaffold a buildable plugin.

## What Gets Generated

Each device produces a complete plugin project:

```
devices/<DeviceName>/
  panel.png               ← front-panel backdrop image
  nrpn_map.json           ← captured MIDI parameter map
  src/
    PluginProcessor.cpp/h ← JUCE plugin processor with NRPN send/receive
    PluginEditor.cpp/h    ← Panel UI with knobs overlaid on panel image
    DeviceParameters.h    ← APVTS parameter layout + NRPN table
    midi/                 ← USB MIDI manager, NRPN encoder/decoder
  CMakeLists.txt
  Makefile
  README.md
```

## Reference Implementations

- [Sequential Take 5](https://github.com/HappyPathway/Take5-VST) — full working example
  (42 NRPN params, brushed-aluminum custom LookAndFeel, panel.png backdrop)

## Supported Frameworks

| Framework | Output | Use When |
|-----------|--------|----------|
| **JUCE 8** | VST3 + AU + Standalone | Professional DAW plugin (default) |
| **Elementary Audio** | WebAudio / Node | Rapid prototyping, web-first |
| **iPlug2** | VST3 + WASM | Browser + DAW deployment |

## Tools

| Tool | Purpose |
|------|---------|
| `tools/midi_capture.py` | Interactive NRPN/CC capture from live hardware |
| `tools/vision_coords.py` | Detect knob positions in front-panel photos |
| `tools/scaffold.py` | Generate plugin project from map + coords |

## Requirements

- macOS 13+ · Xcode CLT · CMake 3.22+ · Ninja
- Python 3.11+ with `pillow numpy opencv-python-headless mido python-rtmidi`
- Node.js 20+ (Elementary Audio only)

---
Part of the [HappyPathway](https://github.com/HappyPathway) open-source toolchain.
