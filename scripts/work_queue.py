#!/usr/bin/env python3
"""The two work queues between research (Claude) and generation (Codex).

    queue/brands.json      brands a person wants researched
    queue/generation.json  creatives ready (or not) to be generated

Agents never edit these files by hand: every change goes through this script,
under a lock, so two agents cannot claim the same item and a half-written file
cannot happen. Prints JSON; exit 0 ok, 1 error, 3 nothing to claim.

Brands (filled by a person, worked by /brand-queue):
    work_queue.py brand-add "<name>" [--copy "<mission copy>"] [--url <store/site>] [--note ...]
    work_queue.py brands [--status pending]
    work_queue.py brand-set "<name>" <pending|researching|researched|failed> [--slug s] [--note ...]

Generation (filled by /brand-queue, worked by skills/generate-queue):
    work_queue.py add <slug> <run>/static [--lines 0,1] [--note ...]
    work_queue.py list [--status ready]
    work_queue.py show <id>
    work_queue.py claim [--by codex]        next ready item -> generating, with its attempt folder
    work_queue.py set <id> <status> [--note ...] [--by ...] [--lines 0,1]

An item becomes `ready` only if everything generation needs is already on disk
or recorded: kit, logo URL, the exact copy lines, the scene prompt. Otherwise it
is `blocked` with the reasons, and generation never touches it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BRAND_STATUSES = ("pending", "researching", "researched", "failed")

# status -> statuses it may move to. `claim` is the only way into `generating`.
TRANSITIONS = {
    "ready": {"blocked", "needs_research"},
    "generating": {"done", "failed", "blocked", "needs_research", "ready"},
    "done": {"approved", "rejected"},
    "rejected": {"ready", "needs_research"},
    "failed": {"ready", "blocked", "needs_research"},
    "blocked": {"ready", "needs_research"},
    "needs_research": {"ready", "blocked"},
    "approved": set(),
}
# Moving into these re-runs the readiness checks; a fix must actually be on disk.
REVALIDATE = {"ready"}
# A note is how the next agent learns why; these moves are useless without one.
NOTE_REQUIRED = {"failed", "blocked", "rejected", "needs_research"}

LOCK_STALE_S = 120


class QueueError(RuntimeError):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- storage

class Store:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.dir = os.path.join(self.root, "queue")
        self.lock_path = os.path.join(self.dir, ".lock")

    def path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def __enter__(self):
        os.makedirs(self.dir, exist_ok=True)
        deadline = time.time() + 30
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > LOCK_STALE_S:
                        os.remove(self.lock_path)  # a crashed writer left it behind
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > deadline:
                    raise QueueError(f"queue is locked ({self.lock_path}); another agent is writing")
                time.sleep(0.1)

    def __exit__(self, *exc):
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass

    def load(self, name: str, key: str) -> dict:
        p = self.path(name)
        if not os.path.isfile(p):
            return {key: []}
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault(key, [])
        return data

    def save(self, name: str, data: dict) -> None:
        p = self.path(name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, p)


def rel(root: str, path: str) -> str:
    """Repo-relative, forward slashes: the queue must read the same on every OS."""
    p = path if os.path.isabs(path) else os.path.join(root, path)
    return os.path.relpath(os.path.abspath(p), root).replace("\\", "/")


# ---------------------------------------------------------------- brands

def _find_brand(data: dict, name: str) -> dict:
    for b in data["brands"]:
        if b["name"].casefold() == name.casefold():
            return b
    raise QueueError(f"no brand named {name!r} in queue/brands.json")


def brand_add(root: str, name: str, copy: str | None, url: str | None, note: str | None) -> dict:
    with Store(root) as s:
        data = s.load("brands.json", "brands")
        if any(b["name"].casefold() == name.casefold() for b in data["brands"]):
            raise QueueError(f"{name!r} is already in queue/brands.json")
        entry = {"name": name, "status": "pending", "added_at": now()}
        if copy:
            entry["mission_copy"] = copy
        if url:
            entry["url"] = url
        if note:
            entry["note"] = note
        data["brands"].append(entry)
        s.save("brands.json", data)
    return entry


def brand_list(root: str, status: str | None) -> list[dict]:
    data = Store(root).load("brands.json", "brands")
    return [b for b in data["brands"] if status is None or b["status"] == status]


def brand_set(root: str, name: str, status: str, slug: str | None, note: str | None) -> dict:
    if status not in BRAND_STATUSES:
        raise QueueError(f"brand status must be one of {BRAND_STATUSES}")
    with Store(root) as s:
        data = s.load("brands.json", "brands")
        b = _find_brand(data, name)
        b["status"], b["updated_at"] = status, now()
        if slug:
            b["slug"] = slug
        if note:
            b["note"] = note
        s.save("brands.json", data)
    return b


# ---------------------------------------------------------------- readiness

def inspect(root: str, slug: str, run: str, lines: list[int] | None) -> tuple[dict, list[str]]:
    """Everything generation needs, read from disk. Returns (fields, blocking reasons)."""
    reasons: list[str] = []
    fields: dict = {"slug": slug, "run": rel(root, run)}
    static = os.path.join(root, fields["run"])

    kit_path = os.path.join(root, "brands", slug, "kit.json")
    kit: dict = {}
    if not os.path.isfile(kit_path):
        reasons.append(f"no kit at brands/{slug}/kit.json")
    else:
        with open(kit_path, encoding="utf-8") as fh:
            kit = json.load(fh)
    fields["brand"] = kit.get("brand", slug)
    logo = kit.get("logo") or {}
    if kit:
        if kit.get("logo_missing"):
            reasons.append("kit says logo_missing: a creative without the real logo is not a fallback")
        if not logo.get("png") or not logo.get("png_url"):
            reasons.append("kit has no logo.png + logo.png_url; generation cannot fetch the logo")
        if kit.get("partial"):
            reasons.append(f"partial kit: {kit.get('partial_note', 'research not finished')}")
    single = logo.get("png_single_colour", logo.get("single_colour"))
    fields["logo"] = {"png": logo.get("png"), "png_url": logo.get("png_url"),
                      "tint_allowed": bool(single), "colour": logo.get("colour")}
    fields["font"] = kit.get("font")

    prompt = os.path.join(static, "scene_prompt.txt")
    fields["scene_prompt"] = rel(root, prompt)
    if not os.path.isfile(prompt):
        reasons.append(f"no scene prompt at {fields['scene_prompt']}")
    else:
        with open(prompt, encoding="utf-8") as fh:
            text = fh.read()
        if "Forbidden:" not in text:
            reasons.append("scene prompt has no 'Forbidden:' block (static-creative section 3 template)")

    copy_path = os.path.join(static, "copy.json")
    fields["copy_file"] = rel(root, copy_path)
    fields["copy"] = []
    if not os.path.isfile(copy_path):
        reasons.append(f"no copy at {fields['copy_file']}")
    else:
        with open(copy_path, encoding="utf-8") as fh:
            avail = json.load(fh).get("lines") or []
        if not avail:
            reasons.append("copy.json has no lines")
        else:
            chosen = lines if lines is not None else ([0] if len(avail) == 1 else None)
            if chosen is None:
                reasons.append(f"copy.json has {len(avail)} lines: choose which with --lines")
            elif not chosen:
                reasons.append("no copy line chosen")
            else:
                for i in chosen:
                    if not 0 <= i < len(avail):
                        reasons.append(f"--lines {i} is not in copy.json (0..{len(avail) - 1})")
                        continue
                    line = avail[i]
                    if not line.get("text") or not line.get("source_url"):
                        reasons.append(f"copy line {i} has no text or no source_url")
                    fields["copy"].append({"text": line.get("text"), "source": line.get("source"),
                                           "source_url": line.get("source_url")})
    return fields, reasons


# ---------------------------------------------------------------- generation

def _find(data: dict, item_id: str) -> dict:
    for it in data["items"]:
        if it["id"] == item_id:
            return it
    raise QueueError(f"no item {item_id!r} in queue/generation.json")


def _move(item: dict, to: str, by: str | None, note: str | None) -> None:
    item["history"].append({"at": now(), "from": item["status"], "to": to,
                            "by": by or "unknown", **({"note": note} if note else {})})
    item["status"], item["updated_at"] = to, now()
    if note:
        item["last_note"] = note


def add(root: str, slug: str, run: str, lines: list[int] | None, note: str | None,
        by: str | None = None) -> dict:
    fields, reasons = inspect(root, slug, run, lines)
    item_id = f"{slug}-{os.path.basename(os.path.dirname(os.path.join(root, fields['run'])))}"
    with Store(root) as s:
        data = s.load("generation.json", "items")
        if any(it["id"] == item_id for it in data["items"]):
            raise QueueError(f"{item_id} is already queued; use `set` to change it")
        status = "blocked" if reasons else "ready"
        item = {"id": item_id, "status": status, "attempt": 0, "created_at": now(),
                "updated_at": now(), **fields, "blocked_by": reasons,
                "history": [{"at": now(), "from": None, "to": status, "by": by or "unknown",
                             **({"note": note} if note else {})}]}
        if note:
            item["last_note"] = note
        data["items"].append(item)
        s.save("generation.json", data)
    return item


def items(root: str, status: str | None) -> list[dict]:
    data = Store(root).load("generation.json", "items")
    return [it for it in data["items"] if status is None or it["status"] == status]


def claim(root: str, by: str | None) -> dict | None:
    with Store(root) as s:
        data = s.load("generation.json", "items")
        item = next((it for it in data["items"] if it["status"] == "ready"), None)
        if item is None:
            return None
        item["attempt"] += 1
        item["out"] = f"{item['run']}/attempt-{item['attempt']}"
        _move(item, "generating", by, None)
        s.save("generation.json", data)
    os.makedirs(os.path.join(root, item["out"]), exist_ok=True)
    return item


def set_status(root: str, item_id: str, to: str, note: str | None, by: str | None,
               lines: list[int] | None = None) -> dict:
    if to == "generating":
        raise QueueError("use `claim` to start generating; it hands out the attempt folder")
    if to not in TRANSITIONS:
        raise QueueError(f"unknown status {to!r}; one of {sorted(TRANSITIONS)}")
    if to in NOTE_REQUIRED and not note:
        raise QueueError(f"moving to {to} needs --note: the next agent has to know why")
    with Store(root) as s:
        data = s.load("generation.json", "items")
        item = _find(data, item_id)
        if to not in TRANSITIONS[item["status"]]:
            raise QueueError(f"{item_id}: cannot go from {item['status']} to {to} "
                             f"(allowed: {sorted(TRANSITIONS[item['status']]) or 'none'})")
        if to == "done":
            out = os.path.join(root, item.get("out", ""))
            missing = [f for f in ("final.png", "final_boxes.json", "static.json")
                       if not os.path.isfile(os.path.join(out, f))]
            if missing:
                raise QueueError(f"{item_id}: cannot be done, {item.get('out')} lacks {missing}")
        if to in REVALIDATE:
            idx = lines
            if idx is None and item.get("copy"):
                # Keep the lines chosen before, matched by text: copy.json may have been
                # rewritten. A line that vanished must be chosen again, not dropped.
                with open(os.path.join(root, item["copy_file"]), encoding="utf-8") as fh:
                    avail = [ln.get("text") for ln in json.load(fh).get("lines") or []]
                gone = [c["text"] for c in item["copy"] if c["text"] not in avail]
                if gone:
                    raise QueueError(f"{item_id}: copy lines no longer in copy.json: {gone}; "
                                     "choose again with --lines")
                idx = [avail.index(c["text"]) for c in item["copy"]]
            fields, reasons = inspect(root, item["slug"], item["run"], idx)
            if reasons:
                raise QueueError(f"{item_id}: still not ready: {reasons}")
            item.update(fields)
            item["blocked_by"] = []
        _move(item, to, by, note)
        s.save("generation.json", data)
    return item


# ---------------------------------------------------------------- CLI

def _lines(value: str | None) -> list[int] | None:
    if value is None:
        return None
    try:
        return [int(v) for v in value.split(",") if v.strip() != ""]
    except ValueError as exc:
        raise QueueError(f"--lines takes indexes like 0 or 1,2, got {value!r}") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Research and generation queues.")
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("brand-add"); p.add_argument("name")
    p.add_argument("--copy"); p.add_argument("--url"); p.add_argument("--note")
    p = sub.add_parser("brands"); p.add_argument("--status", choices=BRAND_STATUSES)
    p = sub.add_parser("brand-set"); p.add_argument("name"); p.add_argument("status")
    p.add_argument("--slug"); p.add_argument("--note")

    p = sub.add_parser("add"); p.add_argument("slug"); p.add_argument("run")
    p.add_argument("--lines"); p.add_argument("--note"); p.add_argument("--by")
    p = sub.add_parser("list"); p.add_argument("--status", choices=sorted(TRANSITIONS) + ["generating"])
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("claim"); p.add_argument("--by")
    p = sub.add_parser("set"); p.add_argument("id"); p.add_argument("status")
    p.add_argument("--note"); p.add_argument("--by")
    p.add_argument("--lines", help="with status ready: choose the copy lines again")

    a = ap.parse_args(argv)
    root = a.root
    try:
        if a.cmd == "brand-add":
            out = brand_add(root, a.name, a.copy, a.url, a.note)
        elif a.cmd == "brands":
            out = brand_list(root, a.status)
        elif a.cmd == "brand-set":
            out = brand_set(root, a.name, a.status, a.slug, a.note)
        elif a.cmd == "add":
            out = add(root, a.slug, a.run, _lines(a.lines), a.note, a.by)
        elif a.cmd == "list":
            out = [{k: it.get(k) for k in ("id", "brand", "status", "attempt", "last_note", "blocked_by")}
                   for it in items(root, a.status)]
        elif a.cmd == "show":
            out = _find(Store(root).load("generation.json", "items"), a.id)
        elif a.cmd == "claim":
            out = claim(root, a.by)
            if out is None:
                print(json.dumps({"claimed": None, "message": "no ready items"}))
                return 3
        else:
            out = set_status(root, a.id, a.status, a.note, a.by, _lines(a.lines))
    except (QueueError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
