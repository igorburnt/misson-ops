#!/usr/bin/env python3
"""Re-fetch a brand's logo PNG from the URL its kit recorded.

    fetch_kit_logo.py <slug> [<slug> ...] [--force]

Logos are media and never committed, so a fresh clone has kit.json but no
logo file. brand-kit records where the PNG came from in `logo.png_url`; this
downloads it to `logo.png` and checks it is a real image. It never searches
for a logo - finding one is brand-kit's judgment, not this script's.

Wikimedia rate-limits upload.wikimedia.org hard (HTTP 429) but serves the
thumb.wikimedia.org renderings brand-kit records. Prints JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import ProbeError, probe  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "mission-ops/1.0"


class LogoError(RuntimeError):
    pass


def fetch(slug: str, force: bool = False) -> dict:
    kit_path = os.path.join(ROOT, "brands", slug, "kit.json")
    if not os.path.isfile(kit_path):
        raise LogoError(f"{slug}: no kit.json at {kit_path}; run brand-kit first")
    with open(kit_path, encoding="utf-8") as fh:
        logo = json.load(fh).get("logo") or {}
    url, rel = logo.get("png_url"), logo.get("png")
    if not url or not rel:
        raise LogoError(f"{slug}: kit has no logo.png_url / logo.png to fetch from")

    dest = os.path.join(ROOT, rel)
    if os.path.isfile(dest) and not force:
        meta = probe(dest)
        return {"slug": slug, "file": rel, "status": "present", "size": [meta["width"], meta["height"]]}

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            ctype = resp.headers.get("Content-Type", "")
            data = resp.read()
    except Exception as exc:  # urllib raises a wide range of transport errors
        raise LogoError(f"{slug}: download failed: {exc}") from exc
    # A rate-limit page saved as logo.png would pass as a logo until someone looked.
    if not ctype.startswith("image/"):
        raise LogoError(f"{slug}: {url} returned {ctype or 'no content type'}, not an image")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    try:
        meta = probe(dest)
    except ProbeError as exc:
        os.remove(dest)
        raise LogoError(f"{slug}: downloaded file is not a readable image: {exc}") from exc

    expected = logo.get("png_size")
    warnings = []
    if expected and [meta["width"], meta["height"]] != list(expected):
        warnings.append(f"size {meta['width']}x{meta['height']} differs from kit png_size {expected}")
    return {"slug": slug, "file": rel, "status": "fetched", "size": [meta["width"], meta["height"]],
            "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-fetch brand logo PNGs from their kit.json.")
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--force", action="store_true", help="download even if the file exists")
    args = ap.parse_args()

    results, failed = [], False
    for slug in args.slugs:
        try:
            results.append(fetch(slug, args.force))
        except (LogoError, ProbeError, OSError, json.JSONDecodeError) as exc:
            results.append({"slug": slug, "error": str(exc)})
            failed = True
    print(json.dumps(results, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
