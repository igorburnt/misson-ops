#!/usr/bin/env python3
"""Fit a creative inside the safe area for outpainting, then restore its pixels.

    outpaint_canvas.py prepare <creative> --out <canvas.png> [--fill grey|blur] [--profile feed]
    outpaint_canvas.py merge <canvas.json> <generated> --out <final.png>

`prepare` scales the whole creative down until it fits the safe area from
specs.json, centres it there on the full canvas and fills the margins with
flat grey. The margins are what the image model is asked to extend.

`merge` takes whatever the model returned (any size), covers the canvas with
it, then pastes the original creative back at the exact rectangle `prepare`
recorded. Image models re-render the whole picture and drift on logos and
text; the merge guarantees every pixel inside that rectangle is the source's,
so the model only ever contributes the margins (rule 3).

Provider-agnostic: the generated file can come from an API or from a person
pasting the canvas into a chat. Prints JSON.
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

# Neutral and unmistakable in a prompt ("replace the flat grey").
FILL = "0x808080"


class OutpaintError(RuntimeError):
    pass


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OutpaintError("ffmpeg not found on PATH")
    return ffmpeg


def placement(src_w: int, src_h: int, spec: dict) -> list[int]:
    """Largest rect with the source's aspect that fits the safe area less min_padding_px,
    centred in it. Without the padding a full-width headline lands exactly on the edge."""
    cw, ch = spec["canvas_width"], spec["canvas_height"]
    pad = spec["min_padding_px"]
    sx0, sy0 = spec["margin_left"] + pad, spec["margin_top"] + pad
    sw = cw - spec["margin_left"] - spec["margin_right"] - 2 * pad
    sh = ch - spec["margin_top"] - spec["margin_bottom"] - 2 * pad
    scale = min(sw / src_w, sh / src_h)
    w, h = int(src_w * scale) // 2 * 2, int(src_h * scale) // 2 * 2
    x, y = sx0 + (sw - w) // 2, sy0 + (sh - h) // 2
    return [x, y, w, h]


def prepare(src: str, out: str, profile_name: str = "feed", specs_path: str | None = None,
            fill: str = "grey") -> dict:
    """fill=grey leaves the margins for an image model to extend. fill=blur needs no model:
    the margins become a blurred, darkened cover-scaled copy of the creative, the same
    treatment normalize_video.py uses for its pad mode, and the result is final as is."""
    spec = specs_mod.safe_area_profile(profile_name, specs_path)
    meta = probe(src)
    cw, ch = spec["canvas_width"], spec["canvas_height"]
    x, y, w, h = placement(meta["width"], meta["height"], spec)

    if fill == "grey":
        bg = f"color=c={FILL}:s={cw}x{ch}[bg];[0:v]scale={w}:{h}:flags=lanczos[fg];"
    elif fill == "blur":
        bg = (f"[0:v]split=2[b][f];"
              f"[b]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},"
              f"boxblur=luma_radius=min(h\\,w)/20:luma_power=1,eq=brightness=-0.06[bg];"
              f"[f]scale={w}:{h}:flags=lanczos[fg];")
    else:
        raise OutpaintError(f"unknown fill {fill!r}; expected grey or blur")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run([_ffmpeg(), "-y", "-v", "error", "-i", src, "-frames:v", "1", "-filter_complex",
         f"{bg}[bg][fg]overlay={x}:{y}:format=auto", out])

    record = {
        "source": src,
        "canvas": out,
        "canvas_size": [cw, ch],
        "placement": [x, y, w, h],
        "scale": round(w / meta["width"], 4),
        "fill": fill,
        "profile": profile_name,
    }
    with open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return record


def merge(record_path: str, generated: str, out: str) -> dict:
    with open(record_path, encoding="utf-8") as fh:
        rec = json.load(fh)
    cw, ch = rec["canvas_size"]
    x, y, w, h = rec["placement"]
    gen = probe(generated)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run([_ffmpeg(), "-y", "-v", "error", "-i", generated, "-i", rec["source"], "-frames:v", "1",
         "-filter_complex",
         # Cover: scale up until both sides fill the canvas, centre-crop the overhang.
         f"[0:v]scale={cw}:{ch}:force_original_aspect_ratio=increase:flags=lanczos,"
         f"crop={cw}:{ch}[bg];[1:v]scale={w}:{h}:flags=lanczos[fg];"
         f"[bg][fg]overlay={x}:{y}:format=auto", out])

    warnings = []
    if abs(gen["width"] / gen["height"] - cw / ch) > 0.02 * cw / ch:
        warnings.append(f"generated image is {gen['width']}x{gen['height']}, not {cw}x{ch}; "
                        "it was cover-scaled, so its outer edges were cropped")
    return {"source": rec["source"], "generated": generated, "output": out,
            "size": [cw, ch], "restored_rect": rec["placement"], "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare an outpainting canvas, or merge the result back.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("input")
    p.add_argument("--out", required=True)
    p.add_argument("--profile", default="feed")
    p.add_argument("--fill", choices=["grey", "blur"], default="grey",
                   help="grey: margins for an image model to extend; blur: no model, final as is")
    p.add_argument("--specs", help="override path to specs.json")
    m = sub.add_parser("merge")
    m.add_argument("record", help="the .json written next to the prepared canvas")
    m.add_argument("generated")
    m.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        if args.cmd == "prepare":
            result = prepare(args.input, args.out, args.profile, args.specs, args.fill)
        else:
            result = merge(args.record, args.generated, args.out)
    except (OutpaintError, ProbeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
