#!/usr/bin/env python3
"""ffprobe wrapper. Reads media metadata. Used by every other script.

    probe.py <file> [--json]

Prints a JSON object to stdout. Exits non-zero if the file is unreadable
or contains no video/image stream.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys


class ProbeError(RuntimeError):
    pass


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise ProbeError(f"{binary} not found on PATH")
    return path


def run(cmd: list[str]) -> str:
    """Run a command, return stdout, raise ProbeError with stderr on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProbeError(f"{cmd[0]} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def _ratio(width: int, height: int) -> str:
    if not width or not height:
        return "unknown"
    g = math.gcd(width, height)
    return f"{width // g}:{height // g}"


def _fps(stream: dict) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key) or ""
        if "/" in raw:
            num, _, den = raw.partition("/")
            try:
                num, den = float(num), float(den)
            except ValueError:
                continue
            if den:
                return round(num / den, 3)
    return None


def _container(path: str, format_name: str) -> str:
    """ffprobe reports a family ("mov,mp4,m4a,3gp,3g2,mj2"); pick the member
    matching the file extension so a spec check against "mp4" passes."""
    names = [n for n in format_name.split(",") if n]
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if ext in names:
        return ext
    return names[0] if names else ""


def probe(path: str) -> dict:
    """Return normalized metadata for a video or image file."""
    if not os.path.isfile(path):
        raise ProbeError(f"no such file: {path}")

    ffprobe = _require("ffprobe")
    raw = json.loads(run([
        ffprobe, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]))

    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ProbeError(f"no video/image stream in {path}")
    audio = next((s for s in raw.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = raw.get("format", {})

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    # Rotation metadata means the display dimensions are swapped.
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if abs(rotation) in (90, 270):
        width, height = height, width

    duration = fmt.get("duration") or video.get("duration")
    duration_s = round(float(duration), 3) if duration else None
    # Single-frame inputs (png/jpg/webp) are images, not 0-second videos.
    is_image = video.get("codec_name") in {"png", "mjpeg", "webp", "bmp", "gif", "tiff"} and (
        duration_s is None or int(video.get("nb_frames") or 1) <= 1
    )

    bit_rate = fmt.get("bit_rate") or video.get("bit_rate")

    return {
        "path": path,
        "kind": "image" if is_image else "video",
        "container": _container(path, fmt.get("format_name") or ""),
        "width": width,
        "height": height,
        "aspect": _ratio(width, height),
        "is_vertical": bool(height > width),
        "duration_s": None if is_image else duration_s,
        "codec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "profile": video.get("profile"),
        "fps": None if is_image else _fps(video),
        "bitrate_kbps": round(int(bit_rate) / 1000) if bit_rate else None,
        "size_bytes": os.path.getsize(path),
        "size_mb": round(os.path.getsize(path) / 1_048_576, 2),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "rotation": rotation,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Read media metadata via ffprobe.")
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true", help="accepted for symmetry; output is always JSON")
    args = ap.parse_args()
    try:
        print(json.dumps(probe(args.file), indent=2))
    except ProbeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
