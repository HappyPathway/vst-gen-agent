#!/usr/bin/env python3
"""
vision_coords.py — Detect rotary knob positions in a hardware front-panel image.

Uses two techniques:
  1. Brightness peak analysis — finds bright silver/aluminum knob faces
  2. OpenCV Hough circle detection — finds circular edges

Usage:
  python3 vision_coords.py --image panel.png --scale 0.5
  python3 vision_coords.py --image panel.png --scale 0.5 --min-radius 12 --max-radius 30
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    sys.exit("Pillow and numpy required: pip install pillow numpy")

try:
    import cv2
except ImportError:
    sys.exit("OpenCV required: pip install opencv-python-headless")


# ---------------------------------------------------------------------------
# Brightness peak analysis
# ---------------------------------------------------------------------------

def brightness_peaks(img_gray: np.ndarray, scale: float,
                     block: int = 30, threshold: float = 200.0) -> list[dict]:
    """
    Divide the image into non-overlapping blocks and find bright local maxima
    that likely correspond to reflective knob faces.
    Returns list of {x, y, r} at original image scale (before applying `scale`).
    """
    h, w = img_gray.shape
    peaks = []
    for y0 in range(0, h - block, block // 2):
        for x0 in range(0, w - block, block // 2):
            region = img_gray[y0:y0 + block, x0:x0 + block]
            mean_val = float(region.mean())
            if mean_val >= threshold:
                cx = int((x0 + block // 2) * scale)
                cy = int((y0 + block // 2) * scale)
                r = int(block // 2 * scale)
                peaks.append({"x": cx, "y": cy, "r": r, "method": "brightness"})
    return peaks


# ---------------------------------------------------------------------------
# Hough circle detection
# ---------------------------------------------------------------------------

def hough_circles(img_gray: np.ndarray, scale: float,
                  min_radius: int, max_radius: int,
                  param2: int = 30) -> list[dict]:
    """
    Run OpenCV HoughCircles on a blurred grayscale image.
    Returns list of {x, y, r} at the requested output scale.
    """
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=min_radius * 2,
        param1=50,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    results = []
    if circles is not None:
        for x, y, r in circles[0]:
            results.append({
                "x": int(x * scale),
                "y": int(y * scale),
                "r": int(r * scale),
                "method": "hough",
            })
    return results


# ---------------------------------------------------------------------------
# Merge / deduplicate results
# ---------------------------------------------------------------------------

def merge(circles: list[dict], min_dist: int) -> list[dict]:
    """Remove duplicate detections closer than min_dist pixels."""
    merged: list[dict] = []
    for c in circles:
        for m in merged:
            dx = c["x"] - m["x"]
            dy = c["y"] - m["y"]
            if (dx * dx + dy * dy) ** 0.5 < min_dist:
                break
        else:
            merged.append(c)
    return merged


# ---------------------------------------------------------------------------
# Annotated output image
# ---------------------------------------------------------------------------

def draw_annotations(img_bgr: np.ndarray, circles: list[dict], scale: float) -> np.ndarray:
    """Draw detected circles onto a copy of img_bgr (at original resolution)."""
    out = img_bgr.copy()
    for i, c in enumerate(circles):
        # Convert scaled coords back to original image coords for drawing
        ox = int(c["x"] / scale)
        oy = int(c["y"] / scale)
        orr = int(c["r"] / scale)
        color = (0, 255, 0) if c["method"] == "hough" else (0, 165, 255)
        cv2.circle(out, (ox, oy), orr, color, 2)
        cv2.putText(out, str(i), (ox - 5, oy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detect knob positions in a panel image")
    parser.add_argument("--image", required=True, help="Path to panel image (PNG/JPG)")
    parser.add_argument("--scale", type=float, default=0.5,
                        help="Output coordinate scale factor (default 0.5 = half size)")
    parser.add_argument("--min-radius", type=int, default=10,
                        help="Minimum knob radius in pixels at original scale")
    parser.add_argument("--max-radius", type=int, default=40,
                        help="Maximum knob radius in pixels at original scale")
    parser.add_argument("--threshold", type=float, default=190.0,
                        help="Brightness threshold for peak detection (0–255)")
    parser.add_argument("--param2", type=int, default=30,
                        help="Hough accumulator threshold (lower = more circles)")
    parser.add_argument("--output", default="vision_output.json",
                        help="Output JSON path")
    parser.add_argument("--annotated", default="vision_annotated.png",
                        help="Annotated image output path")
    args = parser.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        sys.exit(f"Image not found: {args.image}")

    # Load with PIL first (handles more formats), then convert to OpenCV BGR
    pil_img = Image.open(img_path).convert("RGB")
    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    h, w = img_gray.shape
    print(f"Image: {w}×{h}px  →  output scale {args.scale}×  ({int(w*args.scale)}×{int(h*args.scale)})")

    # Run both detectors
    hough = hough_circles(img_gray, args.scale, args.min_radius, args.max_radius, args.param2)
    bright = brightness_peaks(img_gray, args.scale, block=int(args.min_radius * 2.5), threshold=args.threshold)

    all_circles = hough + bright
    merged = merge(sorted(all_circles, key=lambda c: (c["y"], c["x"])),
                   min_dist=int(args.min_radius * args.scale))

    print(f"Detected {len(hough)} Hough + {len(bright)} brightness → {len(merged)} merged circles")

    # Save JSON
    output = {
        "image": str(img_path),
        "scale": args.scale,
        "circles": merged,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Coordinates saved to {args.output}")

    # Save annotated image
    annotated = draw_annotations(img_bgr, merged, args.scale)
    cv2.imwrite(args.annotated, annotated)
    print(f"Annotated image saved to {args.annotated}")
    print("\nOpen vision_annotated.png to visually verify detections.")
    print("Then assign parameter IDs using: nrpn_map.json + annotated image.")


if __name__ == "__main__":
    main()
