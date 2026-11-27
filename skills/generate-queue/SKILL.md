---
name: generate-queue
description: Work the generation queue - for every `ready` item in queue/generation.json, generate the text-free scene with the native image tool, composite the brand's real logo and copy with scripts/brand_overlay.py, and record the result. Generation only - no research, no browsing. Use when asked to work, run or empty the generation queue.
---

# generate-queue

**You generate; you do not research.** Everything an item needs was found and recorded by
research (`/brand-queue`) before it was marked `ready`: the kit, the logo URL, the exact copy
lines with their source, the scene prompt. Your job is the scene, the layout and the check.

Read first: `skills/static-creative/SKILL.md` (§3 scene, §4 layout, §5 composite) and
`skills/safe-area/SKILL.md`. This skill only changes *where things come from and go to*.

## Hard limits

- **No internet** except one call: `scripts/fetch_kit_logo.py`, which downloads the logo from
  the URL already in the kit. No web search, no browsing, no other downloads, no stock images.
- **Never change the copy.** Use `item.copy[].text` exactly, character for character. Do not
  translate, shorten, re-case, fix punctuation or add a line. If the copy does not fit, see §5.
- **Never draw text or logos** (rule 3). The scene is text-free; the real logo and copy are
  composited by script.
- **Never edit `queue/*.json` by hand.** Every status change goes through
  `scripts/work_queue.py`. Never set `approved` or `rejected`: that is the reviewer's call.
- If something is missing or wrong in what research handed you, do not fix it yourself: move
  the item on (§7) with a note that says exactly what is missing, and take the next one.

Commands below use `py -3` (Windows). Use `python3` on macOS and Linux.

## 1. Claim

```
py -3 scripts/work_queue.py claim --by codex
```

Exit 3 means no `ready` items: go to §8. Otherwise it prints the item, now `generating`.
The fields you use:

| Field | What |
|---|---|
| `id` | Pass it to every `set` call. |
| `out` | Your attempt folder, already created. **Everything you write goes here.** |
| `scene_prompt` | The prompt research wrote. |
| `copy` | The exact lines to set, in order. |
| `logo.png`, `logo.tint_allowed`, `logo.colour` | Logo file, and whether it may be tinted. |
| `font` | Brand font file, or null (use the fallback in static-creative §1). |
| `attempt`, `last_note`, `history` | If `attempt` > 1, read `last_note`: why the last attempt came back. |

Earlier attempts stay in their own `attempt-N` folders. Do not delete or overwrite them.

## 2. Logo

```
py -3 scripts/fetch_kit_logo.py <slug>
```

`present` or `fetched`: go on. Error: move the item to `blocked` (§7) with the error text.

## 3. Scene

1. Read `scene_prompt`. If this is a retry and `last_note` is about the scene (composition,
   subject in a band, artefacts, mood), you may add **one** paragraph starting
   `Correction:` before the `Composition (mandatory)` block that addresses the note. Do not
   touch the composition bands or the `Forbidden:` block, and never ask for text or a logo.
2. Save the prompt you actually use to `<out>/scene_prompt.txt`.
3. Generate with your native image tool (Codex `image_gen`) in vertical 9:16 and save it as
   `<out>/scene.png`. If you have no image tool, stop here: move the item back to `ready` with
   the note "no image tool in this agent" and end the session.
4. **Look at it.** Regenerate (at most twice, three images in total) if it has any lettering or
   gibberish text, a logo or brand mark, a watermark, UI or a screen with content, or a subject
   that sits in the logo band (14-26% of the height) or the headline band (68-85%).
5. Still failing after three: move the item to `failed` (§7) and describe what kept going wrong.

## 4. Layout

Write `<out>/layout.json` (format in `scripts/brand_overlay.py`, slots in static-creative §4):

- One `image` element for the logo, `src` = `logo.png`. `tint` only if `logo.tint_allowed` is
  true, and only to make a single-colour logo legible (e.g. `#FFFFFF` on a dark scene).
- One `text` element per copy line, `text` exactly as in `item.copy`, all in `group: "headline"`.
- Look at `scene.png` and move a slot if it lands on a face, the subject or a busy area. Pick
  colours for contrast; `shadow: true` on photographs.

## 5. Composite and check

```
py -3 scripts/brand_overlay.py <out>/scene.png --layout <out>/layout.json \
  --out <out>/final.png --overlay <out>/final_check.png
```

- Exit 0: geometry is right. **Look at `final.png`**: logo legible, text readable, nothing
  covering a face or the subject. Fix the layout and re-run if not.
- Exit 1: a slot leaves the safe area or a line does not fit above `min_font_px`. Move or widen
  the slot. If a line simply does not fit at the minimum size, that is a copy problem, not
  yours: move the item to `needs_research` (§7) with the line and the size it needed.
- At most three layout tries, then `failed`.

## 6. Record

Write `<out>/static.json`:

```json
{
  "id": "<item id>",
  "brand": "<brand>",
  "attempt": 1,
  "copy": [{"text": "...", "source": "...", "source_url": "..."}],
  "scene_prompt_file": "<out>/scene_prompt.txt",
  "generator": "image_gen (built-in)",
  "scene_attempts": 1,
  "layout_attempts": 1,
  "overlay_result": { "...": "the JSON brand_overlay.py printed" },
  "font_used": "<path>",
  "notes": ["what you changed and why, e.g. moved headline up to clear the dog"],
  "needs_human": ["Scene generated by AI: approve before brand use.", "..."]
}
```

`needs_human` always includes the AI-scene line, plus a fallback font, a tint you chose, and
anything you were unsure about. Then:

```
py -3 scripts/work_queue.py set <id> done --by codex --note "<one line: what was made>"
```

`done` refuses if `final.png`, `final_boxes.json` or `static.json` is missing from `out`.
Go back to §1 for the next item.

## 7. When an item cannot be done

| Situation | Status | Note says |
|---|---|---|
| Logo will not download, file missing, kit unreadable | `blocked` | the exact error |
| Copy does not fit, copy looks wrong, logo looks wrong | `needs_research` | what and why |
| Scene or layout failed three times | `failed` | what kept going wrong |
| You must stop mid-item (no image tool, session ending) | `ready` | why, so the next run retries |

```
py -3 scripts/work_queue.py set <id> <status> --by codex --note "<reason>"
```

A note is required for every one of these. Then take the next item. Never leave an item in
`generating` when you stop.

## 8. Finish

When `claim` exits 3:

```
py -3 scripts/review_gallery.py
```

Reply with a table: id, brand, status, attempt, one-line note. Then give the path to
`queue/review.html` for the person to review. Do not commit unless asked.
