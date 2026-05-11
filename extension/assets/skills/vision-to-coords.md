---
name: vision-to-coords
description: "Map hardware device front-panel photo to pixel coordinates. Use when: analyzing a device screenshot or panel.png; finding knob positions on a synthesizer front panel; getting cx/cy/diameter values for JUCE knob placement; detecting circular controls in a hardware photo."
argument-hint: "Path to the panel image (PNG or JPG)"
---

# Vision → Coordinate Mapping

Detects all rotary knobs and controls in a device front-panel image and outputs a coordinate table suitable for placing JUCE `Slider` components over a panel backdrop.

## When to Use

- You have a photo or screenshot of a hardware synthesizer front panel
- You need to know where each knob center is (in pixels) so the plugin UI overlays correctly

## Procedure

### 1. Run the detection script

```bash
python3 tools/vision_coords.py --image <path/to/panel.png> --scale 0.5
```

This runs two complementary techniques:
- **Brightness peak analysis** — finds bright circular regions (silver/aluminum knob faces)
- **OpenCV Hough circle detection** — finds circular edges at configurable radius range

Output: `vision_output.json` with an array of `{x, y, r}` objects at the specified scale.

### 2. Annotate and review

The script also saves `vision_annotated.png` — the panel image with detected circles drawn as overlays. Open this in VS Code to visually verify which circles match actual knobs.

If some knobs are missed or false positives appear, adjust `--min-radius` / `--max-radius` / `--threshold` flags and re-run.

### 3. Assign parameter IDs

Match each detected circle to a parameter ID from `nrpn_map.json`:

```json
{
  "cutoff":        {"cx": 770, "cy": 208, "diam": 48, "isCutoff": true},
  "resonance":     {"cx": 541, "cy": 155, "diam": 34},
  "env1_attack":   {"cx": 876, "cy": 142, "diam": 34}
}
```

The agent should cross-reference the annotated image with the manual's section labels to make correct assignments. When in doubt, ask the user to identify ambiguous knobs.

### 4. Generate the kKnobs table

Produce a C++ snippet ready to paste into `PluginEditor.cpp`:

```cpp
constexpr KnobDef kKnobs[] = {
    { "cutoff",     "CUTOFF",  770, 208, 48, true  },
    { "resonance",  "RES",     541, 155, 34, false },
    // ...
};
```

## Reference

Script: [tools/vision_coords.py](../../tools/vision_coords.py)
Output schema: [references/coords-schema.json](./references/coords-schema.json)
