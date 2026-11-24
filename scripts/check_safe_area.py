#!/usr/bin/env python3
"""Check element bounding boxes against the 9:16 safe area.

    check_safe_area.py <image-or-video> [--boxes <boxes.json>] [--overlay <out.png>]
                       [--profile feed]

Deciding *where* the logo, headline, product and CTA are is judgment and
belongs to the safe-area skill. This script only does the geometry: it maps
the boxes it is given onto the canvas from specs.json, measures overflow and
padding, and draws an overlay for a human or a vision model to look at.

boxes.json, in the input file's own pixel coordinates:

    {"elements": [{"label": "logo", "box": [x0, y0, x1, y1], "critical": true}]}

`critical` defaults to true. Without --boxes the script reports the geometry
only, which is useful together with --overlay as a guide image.

Exit codes: 0 pass (or no boxes given), 2 a critical element breaks the safe
area, 1 error. Prints JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import specs as specs_mod  # noqa: E402
from probe import ProbeError, probe, run  # noqa: E402

# How far a source may drift from the canvas aspect and still be checked.
# 1080x1920 vs 1080x1918 is the same layout; 1080x1350 is not.
ASPECT_TOLERANCE = 0.01


class CheckError(RuntimeError):
    pass


def geometry(spec: dict) -> dict:
    """Safe area and the part of the canvas still visible after placement, in canvas px."""
    cw, ch = spec["canvas_width"], spec["canvas_height"]
    safe = [spec["margin_left"], spec["margin_top"],
            cw - spec["margin_right"], ch - spec["margin_bottom"]]

    fit = spec["placement_fit"]
    if fit == "cover":
        # Cover scales up until both sides fill the placement; whatever overhangs is cropped.
        scale = max(spec["placement_width"] / cw, spec["placement_height"] / ch)
        crop_x = (cw - spec["placement_width"] / scale) / 2
        crop_y = (ch - spec["placement_height"] / scale) / 2
    elif fit == "contain":
        crop_x = crop_y = 0.0
    else:
        raise CheckError(f"unknown placement_fit {fit!r}; expected cover or contain")
    visible = [round(crop_x, 1), round(crop_y, 1), round(cw - crop_x, 1), round(ch - crop_y, 1)]
    return {"canvas": [cw, ch], "safe_area": safe, "placement_visible": visible}


def _check_element(el: dict, scale: float, geo: dict, min_padding: int) -> dict:
    try:
        x0, y0, x1, y1 = (float(v) * scale for v in el["box"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckError(f"element {el.get('label')!r}: box must be [x0, y0, x1, y1]") from exc
    if x1 <= x0 or y1 <= y0:
        raise CheckError(f"element {el.get('label')!r}: box has no area")

    sx0, sy0, sx1, sy1 = geo["safe_area"]
    overflow = {
        "left": max(0.0, sx0 - x0), "top": max(0.0, sy0 - y0),
        "right": max(0.0, x1 - sx1), "bottom": max(0.0, y1 - sy1),
    }
    inside = not any(overflow.values())
    padding = min(x0 - sx0, y0 - sy0, sx1 - x1, sy1 - y1)
    vx0, vy0, vx1, vy1 = geo["placement_visible"]

    return {
        "label": el.get("label", "?"),
        "critical": bool(el.get("critical", True)),
        "box_canvas": [round(v, 1) for v in (x0, y0, x1, y1)],
        "inside_safe_area": inside,
        "overflow_px": {k: round(v, 1) for k, v in overflow.items() if v},
        "padding_px": round(padding, 1) if inside else None,
        "tight": inside and padding < min_padding,
        "visible_after_placement": x0 >= vx0 and y0 >= vy0 and x1 <= vx1 and y1 <= vy1,
    }


def _draw_overlay(src: str, out: str, geo: dict, elements: list[dict]) -> None:
    cw, ch = geo["canvas"]
    sx0, sy0, sx1, sy1 = geo["safe_area"]
    shade = "color=black@0.45:t=fill"
    filters = [
        f"scale={cw}:{ch}",
        # Darken everything outside the safe area so the protected region reads at a glance.
        f"drawbox=x=0:y=0:w={cw}:h={sy0}:{shade}",
        f"drawbox=x=0:y={sy1}:w={cw}:h={ch - sy1}:{shade}",
        f"drawbox=x=0:y={sy0}:w={sx0}:h={sy1 - sy0}:{shade}",
        f"drawbox=x={sx1}:y={sy0}:w={cw - sx1}:h={sy1 - sy0}:{shade}",
        f"drawbox=x={sx0}:y={sy0}:w={sx1 - sx0}:h={sy1 - sy0}:color=lime:t=4",
    ]
    vx0, vy0, vx1, vy1 = geo["placement_visible"]
    if (vx0, vy0) != (0, 0):
        filters.append(f"drawbox=x={vx0}:y={vy0}:w={vx1 - vx0}:h={vy1 - vy0}:color=yellow:t=3")
    for el in elements:
        x0, y0, x1, y1 = el["box_canvas"]
        bad = el["critical"] and not el["inside_safe_area"]
        color = "red" if bad else ("orange" if el["tight"] else "cyan")
        filters.append(f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color={color}:t=3")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise CheckError("ffmpeg not found on PATH")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run([ffmpeg, "-y", "-v", "error", "-i", src, "-frames:v", "1",
         "-vf", ",".join(filters), out])


def check(src: str, boxes_path: str | None = None, overlay: str | None = None,
          profile_name: str = "feed", specs_path: str | None = None) -> dict:
    spec = specs_mod.safe_area_profile(profile_name, specs_path)
    meta = probe(src)
    w, h = meta["width"], meta["height"]
    cw, ch = spec["canvas_width"], spec["canvas_height"]
    if abs(w / h - cw / ch) > ASPECT_TOLERANCE * (cw / ch):
        raise CheckError(
            f"{w}x{h} is not the {cw}x{ch} canvas aspect; the safe area only applies to "
            f"a {cw}x{ch} composition - normalize or outpaint first")

    geo = geometry(spec)
    scale = cw / w
    elements = []
    if boxes_path:
        with open(boxes_path, encoding="utf-8") as fh:
            data = json.load(fh)
        elements = [_check_element(el, scale, geo, spec["min_padding_px"])
                    for el in data.get("elements", [])]

    failures = [e["label"] for e in elements if e["critical"] and not e["inside_safe_area"]]
    warnings = [f"{e['label']}: only {e['padding_px']}px from the safe-area edge "
                f"(want >= {spec['min_padding_px']})" for e in elements if e["tight"]]

    if overlay:
        _draw_overlay(src, overlay, geo, elements)

    return {
        "input": src,
        "profile": profile_name,
        "source_size": [w, h],
        **geo,
        "pass": (not failures) if boxes_path else None,
        "failures": failures,
        "warnings": warnings,
        "elements": elements,
        "overlay": overlay,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check element boxes against the 9:16 safe area.")
    ap.add_argument("input")
    ap.add_argument("--boxes", help="JSON file of element boxes in the input's pixel coordinates")
    ap.add_argument("--overlay", help="write a PNG with the safe area and boxes drawn on it")
    ap.add_argument("--profile", default="feed")
    ap.add_argument("--specs", help="override path to specs.json")
    args = ap.parse_args()

    try:
        result = check(args.input, args.boxes, args.overlay, args.profile, args.specs)
    except (CheckError, ProbeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 2 if result["pass"] is False else 0


if __name__ == "__main__":
    sys.exit(main())
