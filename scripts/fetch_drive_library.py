#!/usr/bin/env python3
"""Mirror a public Google Drive folder into the reference library.

    fetch_drive_library.py <folder-url-or-id> --out references/library/raw [--index-only]

Walks the folder tree, preserving the per-brand subfolder structure, and
downloads every video and image. Skips files already present at the right
size, so re-running it is cheap. Writes an `_index.json` recording the
Drive id, path, mime and size of everything it saw.

Works only on folders shared by link. A folder needing sign-in yields an
empty listing and the script says so rather than writing a partial mirror.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36"
FOLDER_MIME = "application/vnd.google-apps.folder"
WANTED_PREFIXES = ("video/", "image/")


class DriveError(RuntimeError):
    pass


def folder_id(raw: str) -> str:
    m = re.search(r"/folders/([0-9A-Za-z_-]+)", raw)
    return m.group(1) if m else raw


def _get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _listing(fid: str, retries: int = 3) -> list:
    """Drive embeds the folder listing in a _DRIVE_ivd blob on the HTML page."""
    for attempt in range(retries):
        try:
            html = _get(f"https://drive.google.com/drive/folders/{fid}").decode("utf-8", "replace")
            m = re.search(r"_DRIVE_ivd'\]\s*=\s*'(.*?)';", html, re.S)
            if not m:
                return []
            return json.loads(m.group(1).encode().decode("unicode_escape"))[0] or []
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def walk(fid: str, path: str = "") -> list[dict]:
    entries = []
    for item in _listing(fid):
        drive_id, name, mime = item[0], item[2], item[3]
        if mime == FOLDER_MIME:
            entries += walk(drive_id, f"{path}/{name}" if path else name)
        elif mime.startswith(WANTED_PREFIXES):
            entries.append({
                "id": drive_id,
                "name": name,
                "mime": mime,
                "size": int(item[13] or 0),
                "folder": path,
            })
    return entries


def download(entry: dict, out_root: str, retries: int = 3) -> dict:
    dest_dir = os.path.join(out_root, entry["folder"])
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, entry["name"])

    # Re-running must be cheap: a file already at the expected size is done.
    if os.path.isfile(dest) and (not entry["size"] or os.path.getsize(dest) == entry["size"]):
        return {**entry, "file": dest, "status": "skipped"}

    # confirm=t bypasses the virus-scan interstitial Drive shows for large files.
    url = f"https://drive.usercontent.google.com/download?id={entry['id']}&export=download&confirm=t"
    for attempt in range(retries):
        try:
            data = _get(url, timeout=300)
            break
        except Exception as exc:
            if attempt == retries - 1:
                return {**entry, "file": dest, "status": "failed", "error": str(exc)[:200]}
            time.sleep(3 * (attempt + 1))

    if data[:15].lstrip().lower().startswith(b"<!doctype html"):
        return {**entry, "file": dest, "status": "failed",
                "error": "Drive returned an HTML page, not the file (permissions or quota)"}

    with open(dest, "wb") as fh:
        fh.write(data)
    return {**entry, "file": dest, "status": "downloaded", "bytes": len(data)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Mirror a public Drive folder into the reference library.")
    ap.add_argument("folder", help="Drive folder URL or id")
    ap.add_argument("--out", required=True)
    ap.add_argument("--index-only", action="store_true", help="list the tree without downloading")
    args = ap.parse_args()

    try:
        entries = walk(folder_id(args.folder))
    except Exception as exc:
        print(json.dumps({"error": f"could not read the folder: {exc}"}), file=sys.stderr)
        return 1

    if not entries:
        print(json.dumps({"error": "no media found - the folder is empty or not shared by link"}),
              file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)
    index = {
        "folder": args.folder,
        "counts": {
            "videos": sum(1 for e in entries if e["mime"].startswith("video/")),
            "images": sum(1 for e in entries if e["mime"].startswith("image/")),
        },
        "total_bytes": sum(e["size"] for e in entries),
        "brands": sorted({e["folder"].split("/")[0] for e in entries if e["folder"]}),
        "files": entries,
    }

    if not args.index_only:
        results = []
        for i, entry in enumerate(entries, 1):
            r = download(entry, args.out)
            results.append(r)
            print(f"[{i}/{len(entries)}] {r['status']:10} {r['folder']}/{r['name']}", file=sys.stderr)
        index["files"] = results
        index["failed"] = [r for r in results if r["status"] == "failed"]

    with open(os.path.join(args.out, "_index.json"), "w") as fh:
        json.dump(index, fh, indent=2)

    summary = {k: index[k] for k in ("counts", "total_bytes", "brands")}
    summary["index"] = os.path.join(args.out, "_index.json")
    summary["failed"] = len(index.get("failed", []))
    print(json.dumps(summary, indent=2))
    return 1 if index.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
