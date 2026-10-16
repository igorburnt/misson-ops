#!/usr/bin/env python3
"""Collect every candidate asset for a brand, raw and unfiltered.

Collection is deliberately separate from judgment. This script downloads
everything it is pointed at, probes it, and records it. It never rejects a
file for being the wrong aspect ratio, resolution, duration or size --
that is a later step (normalize_video.py / normalize_image.py).

The only things it will not download are hard failures that make a file
useless as a source at all: a dead URL, or a file ffprobe cannot read.
"""
import argparse, json, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent


def run_fetch(url, outdir, image=False):
    cmd = [sys.executable, str(HERE / "fetch_media.py"), url, "--out", str(outdir)]
    if image:
        cmd.append("--image")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {"ok": False, "url": url, "error": (p.stderr or p.stdout).strip()[:400]}
    try:
        d = json.loads(p.stdout)
        d["ok"] = True
        return d
    except json.JSONDecodeError:
        return {"ok": False, "url": url, "error": "fetch_media.py returned non-JSON"}


def classify(probe):
    """Describe the file. Never judge it."""
    if not probe:
        return {}
    w, h = probe.get("width"), probe.get("height")
    note = []
    if w and h:
        if h > w:
            note.append("vertical")
        elif w > h:
            note.append("landscape - will need crop or pad for 9:16")
        else:
            note.append("square")
        if min(w, h) < 1080:
            note.append(f"short side {min(w,h)}px, under the 1080 feed floor")
    d = probe.get("duration_s")
    if d and d > 30:
        note.append(f"{d:.0f}s, over the 30s cap - will need trimming")
    return {"shape_notes": note}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="run directory; raw files land in <out>/raw")
    ap.add_argument("--video", action="append", default=[], help="video URL (repeatable)")
    ap.add_argument("--image", action="append", default=[], help="image URL (repeatable)")
    ap.add_argument("--urls-file", help="file with one URL per line; '# image' suffix marks an image")
    ap.add_argument("--brand", default=None)
    args = ap.parse_args()

    videos, images = list(args.video), list(args.image)
    if args.urls_file:
        for line in pathlib.Path(args.urls_file).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith("# image"):
                images.append(line.rsplit("#", 1)[0].strip())
            else:
                videos.append(line)

    outdir = pathlib.Path(args.out)
    raw = outdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    collected, failed = [], []
    for url in videos:
        r = run_fetch(url, raw, image=False)
        (collected if r.get("ok") else failed).append(r)
    for url in images:
        r = run_fetch(url, raw, image=True)
        (collected if r.get("ok") else failed).append(r)

    assets = []
    for r in collected:
        probe = r.get("probe", {}) or {}
        assets.append({
            # fetch_media.py reports the downloaded file as "file"; "path" is its
            # internal pre-sidecar key and is not present in the sidecar output.
            "path": r.get("file") or r.get("path"),
            "source_url": r.get("source_url") or r.get("url"),
            "platform": r.get("platform"),
            "title": r.get("title"),
            "uploader": r.get("uploader"),
            "upload_date": r.get("upload_date"),
            "view_count": r.get("view_count"),
            "width": probe.get("width"),
            "height": probe.get("height"),
            "aspect": probe.get("aspect"),
            "duration_s": probe.get("duration_s"),
            "codec": probe.get("codec"),
            "size_mb": probe.get("size_mb"),
            "has_audio": probe.get("has_audio"),
            **classify(probe),
            "status": "collected",
        })

    index = {
        "brand": args.brand,
        "collected": len(assets),
        "failed": len(failed),
        "note": "Raw and unfiltered. Nothing here has been judged, cropped or re-encoded.",
        "assets": assets,
        "failures": [{"url": f.get("url"), "error": f.get("error")} for f in failed],
    }
    (outdir / "assets_index.json").write_text(json.dumps(index, indent=2))
    print(json.dumps(index, indent=2))
    return 0 if assets or not (videos or images) else 1


if __name__ == "__main__":
    sys.exit(main())
