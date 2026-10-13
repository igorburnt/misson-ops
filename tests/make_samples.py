#!/usr/bin/env python3
"""Generate the synthetic test fixtures with ffmpeg (they are git-ignored).

    python3 tests/make_samples.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")

FIXTURES = [
    # 16:9, 20s, with audio - the common "landscape YouTube video" case
    (["-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=20",
      "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"],
     "landscape_1080p.mp4"),
    # 4:3, 40s, no audio, at the 480p hard-fail floor - trim + silent audio + upscale
    (["-f", "lavfi", "-i", "smptebars=size=640x480:rate=25:duration=40",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
     "lowres_480p.mp4"),
    # already-vertical 9:16, 18s - the ideal case, should crop with no loss
    (["-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=18",
      "-f", "lavfi", "-i", "sine=frequency=330:duration=18",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"],
     "vertical_1080x1920.mp4"),
    # small image - exercises the upscale warning
    (["-f", "lavfi", "-i", "testsrc2=size=800x600", "-frames:v", "1"], "small.png"),
    # large image - no upscale needed
    (["-f", "lavfi", "-i", "testsrc2=size=2000x2000", "-frames:v", "1"], "large.png"),
]


def main() -> int:
    os.makedirs(SAMPLES, exist_ok=True)
    for args, name in FIXTURES:
        out = os.path.join(SAMPLES, name)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, out], check=True)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
