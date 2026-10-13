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
    ext = os.path.splitext(out)[1].lstrip(".").lower()
    if ext and ext not in (fmt, {"jpg": "jpeg", "jpeg": "jpg"}.get(fmt, fmt)):
        raise NormalizeError(
            f"--out ends in .{ext} but specs.json sets image.{profile_name}.format to {fmt}; "
            f"use .{fmt} or change the spec"
        )
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    min_w = spec.get("min_width", target_w)
    min_h = spec.get("min_height", target_h)
    upscaled = meta["width"] < min_w or meta["height"] < min_h
    chain = [
        _crop_filter(meta["width"], meta["height"], target_w / target_h, focus),
        f"scale={target_w}:{target_h}:flags=lanczos",
    ]

    def encode(quality: int) -> dict:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", src, "-vf", ",".join(chain), "-frames:v", "1"]
        if fmt in ("jpg", "jpeg"):
            # ffmpeg's mjpeg -q:v runs 2 (best) to 31; map the 0-100 knob onto it.
            cmd += ["-q:v", str(max(2, round(31 - (quality / 100) * 29)))]
        elif fmt == "webp":
            cmd += ["-c:v", "libwebp", "-quality", str(quality), "-preset", "picture"]
        cmd.append(out)
        run(cmd)
        return probe(out)

    ladder = spec.get("quality_ladder") or [spec.get("quality", 92)]
    result = encode(ladder[0])
    used_quality = ladder[0]
    warnings = []
    max_mb = spec.get("max_size_mb")

    # PNG is lossless, so there is no quality knob to step down - the only
    # honest move is to tell the operator to switch format in specs.json.
    if max_mb and spec.get("enforce_max_size") and result["size_mb"] > max_mb and fmt != "png":
        for quality in ladder[1:]:
            result = encode(quality)
            used_quality = quality
            if result["size_mb"] <= max_mb:
                break
        if result["size_mb"] <= max_mb and used_quality != ladder[0]:
            warnings.append(
                f"dropped quality to {used_quality} to fit the {max_mb}MB cap "
                f"(final {result['size_mb']}MB)"
            )

    if upscaled:
        warnings.append(
            f"source was {meta['width']}x{meta['height']}, below the {min_w}x{min_h} minimum; "
            "upscaled (may look soft) - prefer Google Play previews over App Store thumbnails"
        )
    if max_mb and result["size_mb"] > max_mb:
        hint = ("PNG is lossless; set image.mission.format to webp or jpg in specs.json"
                if fmt == "png" else "source is unusually detailed; try a different frame")
        warnings.append(f"output {result['size_mb']}MB exceeds the {max_mb}MB cap - {hint}")
    if result["width"] < min_w or result["height"] < min_h:
        warnings.append(f"output {result['width']}x{result['height']} is below the required {min_w}x{min_h}")

    return {
        "ok": not warnings,
        "input": meta,
        "output": result,
        "profile": profile_name,
        "format": fmt,
        "quality": used_quality if fmt != "png" else None,
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
