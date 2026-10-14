#!/usr/bin/env python3
"""Analyze the reference library so the agent can write the style profile.

    profile_library.py <dir> [--out <json>] [--thumbs <dir>] [--no-cuts] [--group feed]

Produces per-file stats and aggregates. No judgment, no LLM calls - it
reports numbers and writes first-frame thumbnails; a human-or-agent reads
them and writes `library_profile.md`.

The library is MIXED: shipped finals sit next to the raw sources they were
cut from, and one brand's ad-network banner tests can outnumber everything
else. So every aggregate is reported PER GROUP as well as overall - an
aggregate over the whole folder is misleading and was, in practice, mostly
an aggregate over one brand.

Groups:
  feed      <Brand>/feed.mp4 and feed-high.mp4 - the shipped house standard
  source    raw social scrapes and other brand video
  undersized  ad-network/DSP banner sizes (1024x768, 480x320, ...) and any
              other video too small to reach 1080x1920
  image_1x1 square mission images
  image_9x16 vertical images (store screenshots)
  image_other
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics as st
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_frames import detect_cuts  # noqa: E402
from probe import ProbeError, probe, run  # noqa: E402

FEED_NAME = re.compile(r"^feed(-high)?\.(mp4|mov|webm)$", re.I)
MEDIA_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".png", ".jpg", ".jpeg", ".webp"}


def classify(meta: dict, path: str) -> str:
    name = os.path.basename(path)
    if meta["kind"] == "image":
        if meta["aspect"] == "1:1":
            return "image_1x1"
        return "image_9x16" if meta["is_vertical"] else "image_other"
    if FEED_NAME.match(name):
        return "feed"
    # Ad-network/DSP banner creatives come in small fixed boxes (1024x768,
    # 480x320, 320x480, 768x1024). Anything whose longest side is under
    # 1280 can never reach a 1080x1920 export without heavy upscaling, so
    # it is not feed material whatever its orientation.
    if max(meta["width"], meta["height"]) < 1280:
        return "undersized"
    return "source"


def _summarize(values: list[float]) -> dict | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": round(vals[0], 2),
        "p25": round(vals[len(vals) // 4], 2),
        "median": round(st.median(vals), 2),
        "p75": round(vals[(3 * len(vals)) // 4], 2),
        "max": round(vals[-1], 2),
    }


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0}
    videos = [r for r in rows if r["kind"] == "video"]
    brands = Counter(r["brand"] for r in rows)
    top_brand, top_n = brands.most_common(1)[0]
    out = {
        "count": len(rows),
        "brands": len(brands),
        # Stated per group so a reader can see at a glance when an "average"
        # is really describing one brand.
        "top_brand": {"name": top_brand, "files": top_n, "share": round(top_n / len(rows), 2)},
        "aspect": Counter(r["aspect"] for r in rows).most_common(),
        "resolution": Counter(f"{r['width']}x{r['height']}" for r in rows).most_common(8),
        "codec": Counter(r["codec"] for r in rows).most_common(),
        "size_mb": _summarize([r["size_mb"] for r in rows]),
    }
    if videos:
        out.update({
            "container": Counter(r["container"] for r in videos).most_common(),
            "fps": Counter(r["fps"] for r in videos).most_common(),
            "has_audio": Counter(r["has_audio"] for r in videos).most_common(),
            "duration_s": _summarize([r["duration_s"] for r in videos]),
            "bitrate_kbps": _summarize([r["bitrate_kbps"] for r in videos]),
            "duration_histogram": Counter(round(r["duration_s"]) for r in videos
                                          if r["duration_s"]).most_common(),
        })
        cps = [r.get("cuts_per_second") for r in videos if r.get("cuts_per_second") is not None]
        if cps:
            out["cuts_per_second"] = _summarize(cps)
            out["mean_shot_s"] = _summarize([r["mean_shot_s"] for r in videos
                                             if r.get("mean_shot_s") is not None])
    return out


def thumbnail(src: str, dest: str) -> str | None:
    """First frame, scaled down - what the agent looks at to judge the hook."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", "0", "-i", src,
             "-frames:v", "1", "-q:v", "4", "-vf", "scale=360:-2", dest])
        return dest
    except Exception:
        return None


def profile(root: str, thumbs: str | None = None, cuts: bool = True,
            only_group: str | None = None) -> dict:
    rows, unreadable = [], []
    for dirpath, _, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.startswith((".", "_")):
                continue
            if os.path.splitext(name)[1].lower() not in MEDIA_EXT:
                continue
            path = os.path.join(dirpath, name)
            try:
                meta = probe(path)
            except ProbeError as exc:
                unreadable.append({"file": path, "error": str(exc)[:200]})
                continue
            rel = os.path.relpath(dirpath, root)
            meta["brand"] = rel.split(os.sep)[0] if rel != "." else ""
            meta["group"] = classify(meta, path)
            rows.append(meta)

    if only_group:
        rows = [r for r in rows if r["group"] == only_group]

    # Cut detection is the expensive part, so it runs only on video.
    for r in rows:
        if cuts and r["kind"] == "video" and r["duration_s"]:
            try:
                times = detect_cuts(r["path"])
                r["cut_count"] = len(times)
                r["cuts_per_second"] = round(len(times) / r["duration_s"], 3)
                r["mean_shot_s"] = round(r["duration_s"] / (len(times) + 1), 2)
            except Exception:
                pass
        if thumbs:
            dest = os.path.join(thumbs, r["group"],
                                f"{r['brand'] or 'root'}__{os.path.basename(r['path'])}.jpg")
            r["thumbnail"] = thumbnail(r["path"], dest)

    groups = sorted({r["group"] for r in rows})
    by_brand = Counter(r["brand"] for r in rows)
    dominant = by_brand.most_common(1)[0] if by_brand else ("", 0)

    result = {
        "root": root,
        "file_count": len(rows),
        "unreadable": unreadable,
        "groups": {g: aggregate([r for r in rows if r["group"] == g]) for g in groups},
        "overall": aggregate(rows),
        "files": rows,
    }
    # Say it out loud rather than letting a reader average across the mix.
    notes = ["Aggregates under 'overall' span every group and are usually misleading. "
             "Read groups.feed for the house standard."]
    if dominant[1] > 0.25 * len(rows):
        notes.append(f"Skew: '{dominant[0]}' holds {dominant[1]} of {len(rows)} files "
                     f"({dominant[1] / len(rows):.0%}); overall aggregates largely describe it.")
    result["notes"] = notes
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze the reference library.")
    ap.add_argument("dir")
    ap.add_argument("--out", help="write the full JSON here (stdout gets a summary)")
    ap.add_argument("--thumbs", help="directory for first-frame thumbnails")
    ap.add_argument("--no-cuts", action="store_true", help="skip scene detection (much faster)")
    ap.add_argument("--group", help="restrict to one group, e.g. feed")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print(json.dumps({"error": f"not a directory: {args.dir}"}), file=sys.stderr)
        return 1

    result = profile(args.dir, args.thumbs, not args.no_cuts, args.group)
    if not result["file_count"]:
        print(json.dumps({"error": f"no media found under {args.dir}"}), file=sys.stderr)
        return 1

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(result, fh, indent=2)

    summary = {k: result[k] for k in ("root", "file_count", "notes", "groups")}
    summary["unreadable"] = len(result["unreadable"])
    if args.out:
        summary["full_json"] = args.out
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
