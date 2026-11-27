#!/usr/bin/env python3
"""Build a local review page for generated statics.

    review_gallery.py [--status done] [--out queue/review.html]

One card per queue item: the scene, the final creative and the safe-area check
side by side, the copy with its source, and everything flagged for a person.
The page writes nothing back. Its buttons produce the `work_queue.py set`
commands for your decisions, to paste into a terminal (or into an agent).
Open it from disk; images are linked relative to the page, not embedded.
Prints JSON.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import work_queue  # noqa: E402

ROOT = work_queue.ROOT


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _img(root: str, page_dir: str, path: str, label: str) -> str:
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        return f'<figure class="missing"><div>no {html.escape(label)}</div><figcaption>{html.escape(label)}</figcaption></figure>'
    src = os.path.relpath(full, page_dir).replace("\\", "/")
    return (f'<figure><a href="{html.escape(src)}" target="_blank"><img src="{html.escape(src)}" '
            f'alt="{html.escape(label)}" loading="lazy"></a><figcaption>{html.escape(label)}</figcaption></figure>')


def card(root: str, page_dir: str, item: dict) -> str:
    out = item.get("out") or item["run"]
    static = _read_json(os.path.join(root, out, "static.json"))
    copy_doc = _read_json(os.path.join(root, item.get("copy_file", "")))
    kit = _read_json(os.path.join(root, "brands", item["slug"], "kit.json"))
    overlay = static.get("overlay_result") or {}

    flags = list(dict.fromkeys(
        (static.get("needs_human") or []) + (copy_doc.get("needs_human") or [])))
    copy_rows = "".join(
        f'<li>&ldquo;{html.escape(c.get("text") or "")}&rdquo; '
        f'<a href="{html.escape(c.get("source_url") or "#")}" target="_blank">{html.escape(c.get("source") or "source")}</a></li>'
        for c in item.get("copy", []))
    check = ("pass" if overlay.get("pass") else "FAIL") if overlay else "not run"
    flag_rows = "".join(f"<li>{html.escape(f)}</li>" for f in flags) or "<li>none</li>"
    kit_flags = "".join(f"<li>{html.escape(f)}</li>" for f in (kit.get("needs_human") or []))
    iid = html.escape(item["id"])
    return f"""
<section class="card" data-id="{iid}">
  <header>
    <h2>{html.escape(item.get("brand", item["slug"]))}</h2>
    <span class="meta">{iid} · attempt {item.get("attempt", 0)} · {html.escape(item["status"])} · safe area: <b class="{check.lower().replace(' ', '-')}">{check}</b></span>
  </header>
  <div class="imgs">
    {_img(root, page_dir, out + "/scene.png", "scene")}
    {_img(root, page_dir, out + "/final.png", "final")}
    {_img(root, page_dir, out + "/final_check.png", "safe-area check")}
  </div>
  <div class="info">
    <h3>Copy</h3><ul>{copy_rows or "<li>none</li>"}</ul>
    <h3>Needs a person</h3><ul>{flag_rows}</ul>
    <details><summary>Kit flags ({len(kit.get("needs_human") or [])})</summary><ul>{kit_flags or "<li>none</li>"}</ul></details>
  </div>
  <div class="decide">
    <label><input type="radio" name="d-{iid}" value="approved"> approve</label>
    <label><input type="radio" name="d-{iid}" value="rejected"> reject</label>
    <select aria-label="send back to">
      <option value="ready">back to Codex (scene or layout)</option>
      <option value="needs_research">back to Claude (copy, logo or kit)</option>
    </select>
    <input type="text" placeholder="why (required to reject)">
  </div>
</section>"""


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Static Review</title>
<style>
:root {{ --bg:#f6f5f2; --fg:#1c1c1c; --muted:#6b6b6b; --card:#fff; --line:#e3e1dc; --ok:#1f7a3a; --bad:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#151515; --fg:#ececec; --muted:#9a9a9a; --card:#1f1f1f; --line:#333; --ok:#5fcf7f; --bad:#ff7b72; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:24px 16px 120px; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }} .sub {{ color:var(--muted); margin:0 0 24px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; margin:0 auto 20px; max-width:1100px; }}
.card header {{ display:flex; flex-wrap:wrap; gap:8px 16px; align-items:baseline; }}
.card h2 {{ margin:0; font-size:18px; }} .meta {{ color:var(--muted); font-size:13px; }}
.pass {{ color:var(--ok); }} .fail {{ color:var(--bad); }}
.imgs {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px; margin:14px 0; }}
figure {{ margin:0; }} img {{ width:100%; aspect-ratio:9/16; object-fit:contain; background:#000; border-radius:6px; display:block; }}
figcaption {{ color:var(--muted); font-size:12px; margin-top:4px; }}
.missing div {{ aspect-ratio:9/16; border:1px dashed var(--line); border-radius:6px; display:grid; place-items:center; color:var(--muted); }}
.info h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:12px 0 4px; }}
.info ul {{ margin:0; padding-left:18px; }} a {{ color:inherit; }}
.decide {{ display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; margin-top:14px; padding-top:12px; border-top:1px solid var(--line); }}
.decide input[type=text] {{ flex:1 1 240px; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); }}
.decide select {{ padding:6px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); }}
#bar {{ position:fixed; left:0; right:0; bottom:0; background:var(--card); border-top:1px solid var(--line); padding:12px 16px; }}
#bar button {{ padding:8px 14px; border-radius:6px; border:1px solid var(--line); background:var(--fg); color:var(--bg); cursor:pointer; }}
#cmds {{ width:100%; margin-top:8px; font:12px ui-monospace, monospace; min-height:0; display:none; background:var(--bg); color:var(--fg); border:1px solid var(--line); }}
@media (max-width:640px) {{ .imgs {{ grid-template-columns:1fr; }} }}
</style></head><body>
<h1>Static review</h1>
<p class="sub">{count} item(s) with status {status}. Generated {generated}. Decide each, then copy the commands.</p>
{cards}
<div id="bar"><button id="go">Build commands</button> <span id="msg"></span>
<textarea id="cmds" rows="6" readonly></textarea></div>
<script>
document.getElementById('go').onclick = () => {{
  const py = {py};
  const lines = [], missing = [];
  for (const c of document.querySelectorAll('.card')) {{
    const id = c.dataset.id, pick = c.querySelector('input[type=radio]:checked');
    if (!pick) continue;
    const note = c.querySelector('input[type=text]').value.trim().replace(/"/g, "'");
    if (pick.value === 'rejected' && !note) {{ missing.push(id); continue; }}
    const n = note ? ` --note "${{note}}"` : '';
    lines.push(`${{py}} scripts/work_queue.py set ${{id}} ${{pick.value}} --by human${{n}}`);
    if (pick.value === 'rejected') {{
      const back = c.querySelector('select').value;
      lines.push(`${{py}} scripts/work_queue.py set ${{id}} ${{back}} --by human --note "${{note}}"`);
    }}
  }}
  const t = document.getElementById('cmds');
  t.style.display = 'block'; t.value = lines.join('\\n');
  t.select();
  try {{ navigator.clipboard.writeText(t.value); }} catch (e) {{}}
  document.getElementById('msg').textContent = missing.length
    ? `Rejections need a reason: ${{missing.join(', ')}}` : `${{lines.length}} command(s), copied.`;
}};
</script></body></html>
"""


def build(root: str, status: str, out: str) -> dict:
    chosen = work_queue.items(root, status)
    page_dir = os.path.dirname(os.path.abspath(out))
    os.makedirs(page_dir, exist_ok=True)
    py = "py -3" if os.name == "nt" else "python3"
    page = PAGE.format(count=len(chosen), status=html.escape(status), generated=work_queue.now(),
                       cards="".join(card(root, page_dir, it) for it in chosen) or "<p>Nothing to review.</p>",
                       py=json.dumps(py))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    return {"page": os.path.abspath(out), "items": [it["id"] for it in chosen]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the static review page from the generation queue.")
    ap.add_argument("--status", default="done")
    ap.add_argument("--out", default=None, help="default: queue/review.html")
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    a = ap.parse_args()
    try:
        r = build(a.root, a.status, a.out or os.path.join(a.root, "queue", "review.html"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
