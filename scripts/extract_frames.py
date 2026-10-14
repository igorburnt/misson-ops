#!/usr/bin/env python3
"""Pull frames out of a video so the agent can actually look at it.

    extract_frames.py <in> --out <dir> [--n 6] [--scene-threshold 0.3] [--no-cuts]

Writes the first frame plus `--n` evenly spaced frames, and detects scene
cuts. Scoring must be done by looking at frames (rubric criteria like hook,
tone and clean frame are invisible in metadata), and cuts-per-second is the
pacing signal the style profile is built on.

Prints JSON: frame paths with timestamps, cut times, cuts_per_second.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import ProbeError, probe, run  # noqa: E402


class FrameError(RuntimeError):
    pass


def detect_cuts(src: str, threshold: float = 0.3) -> list[float]:
    """Scene-cut timestamps, via ffmpeg's scene score."""
    ffmpeg = shutil.which("ffmpeg")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "info", "-i", src,
         "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    # The filter writes to stdout, but ffmpeg mixes its own log into stderr.
    times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", proc.stdout + proc.stderr)]
    return sorted(set(round(t, 3) for t in times))


def extract(src: str, out_dir: str, n: int = 6, threshold: float = 0.3,
            detect: bool = True) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FrameError("ffmpeg not found on PATH")

    meta = probe(src)
    if meta["kind"] != "video":
        raise FrameError(f"{src} is an image, not a video")
    duration = meta["duration_s"] or 0.0
    if duration <= 0:
        raise FrameError(f"{src} reports no duration")

    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]

    # First frame always, because the rubric's hook criterion is about the
    # first 2s - then evenly spaced across the rest.
    timestamps = [0.0]
    if n > 1:
        step = duration / n
        timestamps += [round(step * (i + 0.5), 3) for i in range(n - 1)]

    frames = []
    for i, ts in enumerate(timestamps):
        path = os.path.join(out_dir, f"{stem}_f{i:02d}_{ts:.2f}s.jpg")
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", src,
             "-frames:v", "1", "-q:v", "3", "-vf", "scale=640:-2", path])
        frames.append({"index": i, "time_s": ts, "file": path})

    cuts = detect_cuts(src, threshold) if detect else []
    return {
        "input": meta,
        "frames": frames,
        "cuts": cuts,
        "cut_count": len(cuts),
        "cuts_per_second": round(len(cuts) / duration, 3) if duration else None,
        "mean_shot_s": round(duration / (len(cuts) + 1), 2) if duration else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract review frames and detect scene cuts.")
    ap.add_argument("input")
    ap.add_argument("--out", required=True, help="output directory for frames")
    ap.add_argument("--n", type=int, default=6, help="total frames (first frame + evenly spaced)")
    ap.add_argument("--scene-threshold", type=float, default=0.3)
    ap.add_argument("--no-cuts", action="store_true", help="skip scene detection (faster)")
    args = ap.parse_args()

    try:
        print(json.dumps(extract(args.input, args.out, args.n,
                                 args.scene_threshold, not args.no_cuts), indent=2))
    except (FrameError, ProbeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
