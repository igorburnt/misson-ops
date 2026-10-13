#!/usr/bin/env python3
"""Make an image spec-compliant (1:1 mission image).

    normalize_image.py <in> [--out <file>] [--profile mission] [--focus x,y]

Centre-crops to the target aspect, upscales with lanczos when below the
minimum resolution, exports the format from specs.json. Prints JSON.
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


class NormalizeError(RuntimeError):
    pass


def _crop_filter(src_w: int, src_h: int, target_ratio: float, focus: tuple[float, float] | None) -> str:
    """Crop to target_ratio, keeping the focus point (0-1 relative) in frame."""
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        crop_w, crop_h = round(src_h * target_ratio), src_h
    else:
        crop_w, crop_h = src_w, round(src_w / target_ratio)
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2

    fx, fy = focus if focus else (0.5, 0.5)
    x = min(max(round(src_w * fx - crop_w / 2), 0), src_w - crop_w)
    y = min(max(round(src_h * fy - crop_h / 2), 0), src_h - crop_h)
    return f"crop={crop_w}:{crop_h}:{x}:{y}"


def normalize(src: str, out: str | None, profile_name: str,
              focus: tuple[float, float] | None = None, specs_path: str | None = None) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise NormalizeError("ffmpeg not found on PATH")

    spec = specs_mod.image_profile(profile_name, specs_path)
    meta = probe(src)

    target_w, target_h = spec["width"], spec["height"]
    fmt = spec.get("format", "png")
    if out is None:
        stem = os.path.splitext(src)[0]
        out = f"{stem}_{profile_name}.{fmt}"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    upscaled = meta["width"] < target_w or meta["height"] < target_h
    chain = [
        _crop_filter(meta["width"], meta["height"], target_w / target_h, focus),
        f"scale={target_w}:{target_h}:flags=lanczos",
    ]

    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", src, "-vf", ",".join(chain), "-frames:v", "1"]
    if fmt in ("jpg", "jpeg"):
        # ffmpeg's mjpeg -q:v runs 2 (best) to 31; map the 0-100 quality knob onto it.
        q = max(2, round(31 - (spec.get("jpeg_quality", 92) / 100) * 29))
        cmd += ["-q:v", str(q)]
    cmd.append(out)
    run(cmd)

    result = probe(out)
    warnings = []
    if upscaled:
        warnings.append(
            f"source was {meta['width']}x{meta['height']}, below {target_w}x{target_h}; upscaled (may look soft)"
        )
    max_mb = spec.get("max_size_mb")
    if max_mb and result["size_mb"] > max_mb:
        warnings.append(f"output {result['size_mb']}MB exceeds max_size_mb {max_mb}")

    return {
        "ok": not warnings,
        "input": meta,
        "output": result,
        "profile": profile_name,
        "upscaled": upscaled,
        "warnings": warnings,
    }


def _parse_focus(raw: str | None) -> tuple[float, float] | None:
    if not raw:
        return None
    try:
        x, y = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise NormalizeError("--focus expects x,y as 0-1 floats, e.g. 0.5,0.35") from exc
    return x, y


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize an image to the mission spec.")
    ap.add_argument("input")
    ap.add_argument("--out")
    ap.add_argument("--profile", default="mission")
    ap.add_argument("--focus", help="focus point as x,y in 0-1 (default centre)")
    ap.add_argument("--specs", help="override path to specs.json")
    args = ap.parse_args()

    try:
        print(json.dumps(normalize(args.input, args.out, args.profile,
                                   _parse_focus(args.focus), args.specs), indent=2))
    except (NormalizeError, ProbeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
