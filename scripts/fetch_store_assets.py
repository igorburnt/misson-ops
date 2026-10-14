#!/usr/bin/env python3
"""Pull icon and screenshots from a Google Play listing.

    fetch_store_assets.py <play-store-url-or-package-id> --out <dir> [--max 12]

Play Store listings are fetchable when brand websites are not, and they
carry higher-resolution art than the App Store. Play serves every image
at an arbitrary size suffix, so assets come down at full resolution
rather than at the carousel's thumbnail size.

The page also embeds "similar apps", so there is no clean way to isolate
this app's images by markup alone. Instead every candidate is downloaded
and probed, and the result is sorted by resolution with dimensions and
aspect reported - the agent picks, and never has to guess.

Prints JSON. Exits non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import ProbeError, probe  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36"
IMG = r"https://play-lh\.googleusercontent\.com/[A-Za-z0-9_-]+"


class StoreError(RuntimeError):
    pass


def listing_url(raw: str) -> str:
    if raw.startswith("http"):
        return raw if "hl=" in raw else raw + ("&" if "?" in raw else "?") + "hl=en_US"
    return f"https://play.google.com/store/apps/details?id={raw}&hl=en_US"


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def scrape(url: str) -> dict[str, list[str]]:
    try:
        html = _get(url).decode("utf-8", "replace")
    except Exception as exc:
        raise StoreError(f"could not fetch the listing: {exc}") from exc

    variants: dict[str, set[str]] = {}
    for base, size in re.findall(rf"({IMG})=([ws][0-9h-]+)", html):
        variants.setdefault(base, set()).add(size.rstrip("-"))

    # The carousel serves screenshots at a w<width>-h<height> size; icons
    # only ever appear as s<size>. That separates the two cleanly even
    # though it does not separate this app from its neighbours.
    shots = [u for u, s in variants.items() if any(x.startswith("w") for x in s)]
    icons = [u for u, s in variants.items() if all(x.startswith("s") for x in s)]

    # The page is full of s20/s40 thumbnails for neighbouring apps. Rank icon
    # candidates by the largest size the page itself asks for, treating s0
    # (serve the original) as the largest, so the real app icon wins.
    def icon_rank(u: str) -> int:
        best = 0
        for x in variants[u]:
            try:
                n = int(x[1:])
            except ValueError:
                continue
            best = max(best, 10 ** 6 if n == 0 else n)
        return best

    return {"screenshots": sorted(shots),
            "icons": sorted(icons, key=icon_rank, reverse=True)}


def download(base: str, out_dir: str, name: str, size: str) -> dict | None:
    dest = os.path.join(out_dir, f"{name}.png")
    try:
        data = _get(f"{base}={size}")
    except Exception as exc:
        return {"file": dest, "error": str(exc)[:160]}
    with open(dest, "wb") as fh:
        fh.write(data)
    try:
        meta = probe(dest)
    except ProbeError as exc:
        os.remove(dest)
        return {"file": dest, "error": str(exc)[:160]}
    return {
        "file": dest, "source": base,
        "width": meta["width"], "height": meta["height"],
        "aspect": meta["aspect"], "is_vertical": meta["is_vertical"],
        "size_mb": meta["size_mb"],
    }


def fetch(target: str, out_dir: str, max_shots: int = 12) -> dict:
    url = listing_url(target)
    found = scrape(url)
    if not found["screenshots"] and not found["icons"]:
        raise StoreError("no images found on the listing - layout may have changed")

    os.makedirs(out_dir, exist_ok=True)
    icon = download(found["icons"][0], out_dir, "icon", "s1024") if found["icons"] else None

    shots = []
    for i, base in enumerate(found["screenshots"][:max_shots]):
        r = download(base, out_dir, f"screenshot_{i:02d}", "w2560")
        if r and "error" not in r:
            shots.append(r)
    # Biggest first - the agent wants the highest-resolution usable art.
    shots.sort(key=lambda s: -(s["width"] * s["height"]))

    warnings = []
    if icon and "error" not in icon and min(icon["width"], icon["height"]) < 1024:
        warnings.append(
            f"app icon is only {icon['width']}x{icon['height']}, below the 1024x1024 "
            "mission-image minimum - do not use it as the mission image without a human check"
        )
    if not any(s["is_vertical"] for s in shots):
        warnings.append("no vertical screenshot on the listing; 1:1 and 9:16 crops will come "
                        "from landscape art and may lose the subject")

    return {
        "listing": url,
        "icon": icon,
        "screenshots": shots,
        "vertical_screenshots": sum(1 for s in shots if s["is_vertical"]),
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch icon and screenshots from a Play listing.")
    ap.add_argument("target", help="Play Store URL or package id")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=12, help="max screenshots to download")
    args = ap.parse_args()
    try:
        print(json.dumps(fetch(args.target, args.out, args.max), indent=2))
    except StoreError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
