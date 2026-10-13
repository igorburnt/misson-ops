#!/usr/bin/env python3
"""Download a video or image, keeping provenance.

    fetch_media.py <url> --out <dir> [--max-height 1080] [--image]

Videos go through yt-dlp (YouTube, Instagram, TikTok, direct links).
Images and direct media URLs fall back to a plain HTTP download.
Writes <file> plus a sidecar <file>.json recording source URL, uploader,
title, upload date and the probe metadata. Exits non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import ProbeError, probe  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36"


class FetchError(RuntimeError):
    pass


def _sidecar(media_path: str, source_url: str, info: dict) -> dict:
    try:
        meta = probe(media_path)
    except ProbeError as exc:
        raise FetchError(f"downloaded file is not readable media: {exc}") from exc

    sidecar = {
        "source_url": source_url,
        "platform": info.get("extractor_key") or info.get("extractor"),
        "uploader": info.get("uploader") or info.get("channel"),
        "uploader_url": info.get("uploader_url") or info.get("channel_url"),
        "title": info.get("title"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "duration_s": info.get("duration"),
        "webpage_url": info.get("webpage_url") or source_url,
        "file": media_path,
        "probe": meta,
    }
    with open(media_path + ".json", "w") as fh:
        json.dump(sidecar, fh, indent=2)
    return sidecar


def _via_ytdlp(url: str, out_dir: str, max_height: int, cookies_from: str | None) -> dict:
    if not shutil.which("yt-dlp"):
        raise FetchError("yt-dlp not found on PATH")

    template = os.path.join(out_dir, "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-progress",
        "--no-warnings",
        "-f", f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "--merge-output-format", "mp4",
        "--print-json",
        "--no-simulate",
        "-o", template,
    ]
    if cookies_from:
        cmd += ["--cookies-from-browser", cookies_from]
    cmd.append(url)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Login walls (Instagram in particular) are expected; the caller logs and continues.
        raise FetchError(f"yt-dlp failed: {proc.stderr.strip()[:500]}")

    info = json.loads(proc.stdout.strip().splitlines()[-1])
    path = info.get("_filename") or info.get("filename")
    if path and not os.path.isfile(path):
        # --merge-output-format rewrites the extension after _filename is set.
        stem = os.path.splitext(path)[0]
        path = next((c for c in (stem + ".mp4", stem + ".mkv", stem + ".webm") if os.path.isfile(c)), None)
    if not path or not os.path.isfile(path):
        raise FetchError("yt-dlp reported success but no output file was found")
    return {"path": path, "info": info}


def _via_http(url: str, out_dir: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
            data = resp.read()
    except Exception as exc:  # urllib raises a wide range of transport errors
        raise FetchError(f"download failed: {exc}") from exc

    name = os.path.basename(urllib.parse.urlsplit(url).path) or "download"
    if not os.path.splitext(name)[1]:
        name += mimetypes.guess_extension(content_type) or ".bin"
    path = os.path.join(out_dir, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return {"path": path, "info": {"title": name, "extractor_key": "http", "webpage_url": url}}


def fetch(url: str, out_dir: str, max_height: int = 1080,
          image: bool = False, cookies_from: str | None = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    result = _via_http(url, out_dir) if image else _via_ytdlp(url, out_dir, max_height, cookies_from)
    return _sidecar(result["path"], url, result["info"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Download media with provenance sidecar.")
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--max-height", type=int, default=1080)
    ap.add_argument("--image", action="store_true", help="plain HTTP download (images, direct files)")
    ap.add_argument("--cookies-from", help="browser to pull cookies from, e.g. chrome (login-walled sources)")
    args = ap.parse_args()

    try:
        print(json.dumps(fetch(args.url, args.out, args.max_height, args.image, args.cookies_from), indent=2))
    except FetchError as exc:
        print(json.dumps({"error": str(exc), "url": args.url}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
