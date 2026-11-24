---
name: safe-area
description: Check whether a 9:16 creative keeps its logo, text, product and CTA inside the mobile safe area, and triage each mission into a fix bucket. Also the layout brief for anything composited or generated. You find the elements; scripts/check_safe_area.py does the geometry.
---

# safe-area

**Input:** a creative (image or video), 9:16. **Output:** `boxes.json`, the check result, an overlay PNG, a triage bucket.

Read `skills/creative-standards/SKILL.md` first. The source rules are
`references/constraints-creatives-generation.md` (Safe Area Skill v2.1). The numbers live in
`specs.json` under `safe_area.feed`, never in this file or a prompt.

## The split

| Judgment (you) | Mechanics (`check_safe_area.py`) |
|---|---|
| Which elements exist and which are critical | Mapping boxes onto the 1080×1920 canvas |
| The tight visible bounds of each one | Overflow per side, padding, cover-crop visibility |
| Whether a crop is intentional (v2.1 §5) | Exit code and the overlay image |

Never eyeball "it looks inside". Write the boxes down and let the script measure them.

## How v2.1 applies in this pipeline

v2.1 was written for a model that draws the whole ad, logo and headline included. Rule 3
forbids that here. In this pipeline its rules apply in three places:

- **Checking** an existing creative (triage) or a finished one (auto-QA): the full rule set, as written.
- **Generating**: the model produces background and environment only, text-free and logo-free.
  The safe-area rules tell it what to *leave room for*: keep the safe region calm where the
  logo and headline will go, and keep any generated subject inside it.
- **Compositing**: the real logo and copy are placed by FFmpeg inside the safe area with
  `min_padding_px` clear space. v2.1 §6–8 (text width, logo clear space, CTA margin) govern
  the placement coordinates.

## 1. Look at it with the guide

```
python3 scripts/check_safe_area.py <creative> --overlay <run>/safe_area/<name>_guide.png
```

Look at the guide, not the raw file. Outside the safe area is darkened, the safe area is
outlined green and the cover-crop edges are yellow. For a video, check the first frame and the
frames from `extract_frames.py`. An element only has to leave the safe area once to fail.

If the script refuses because the source is not 9:16, that is a triage result, not an error.
See §4.

## 2. Write the boxes

`<run>/safe_area/<name>_boxes.json`, in the **source file's own pixels**:

```json
{"elements": [
  {"label": "logo", "box": [x0, y0, x1, y1]},
  {"label": "headline", "box": [x0, y0, x1, y1]},
  {"label": "background glow", "box": [x0, y0, x1, y1], "critical": false}
]}
```

- **Critical by default** (v2.1 §4): logo and brand name, every line of text, CTA and button,
  price, offer and reward, the main product, primary people. Mark something
  `"critical": false` only when it is truly decorative (§9). If you hesitate, it is critical.
- **Tight visible bounds**, not the element's centre. Text runs from the leftmost to the
  rightmost glyph (§6); a logo includes its wordmark and symbol (§7); a CTA includes the button
  background and arrow (§8); a person includes hair and hands (§10).
- One box per element. A two-line headline is one box spanning both lines.

## 3. Run the check

```
python3 scripts/check_safe_area.py <creative> --boxes <boxes.json> \
  --overlay <run>/safe_area/<name>_check.png
```

Exit 0 is a pass, 2 means a critical element is outside, and 1 is an error. `warnings` lists
elements that are inside but closer than `min_padding_px` to the edge. Those pass, but say so.
Look at the `_check.png`: red means a failure, orange means tight, cyan means fine. If a red
box looks wrong, your box was wrong; redo §2 rather than overriding the result.

## 4. Triage bucket

| Bucket | When |
|---|---|
| `no_creative` | Nothing on the mission |
| `static_ok` | 9:16 static, check passes |
| `static_breaks_safe_area` | 9:16 static, check fails |
| `static_wrong_ratio` | Static is not 9:16. Needs outpainting before it can be checked |
| `video_ok` | 9:16 video, check passes on every frame you looked at |
| `video_wrong_ratio_or_quality` | Not 9:16, below the `hard_fails` floor, or key content outside on some frames |

## 5. needs_human, not a guess

- An intentional crop of the product (§5): you cannot tell whether it is deliberate.
- Burned-in legal text or a disclaimer that only just breaks the edge. Moving it may change its meaning.
- A box boundary you cannot see clearly (low resolution, motion blur, text on busy art).
- Every `static_breaks_safe_area` until the fix step exists. Nothing is auto-fixed yet.

## Open questions

- **Cover vs fit-to-width.** v2.1 assumes cover into 1080×2346, which crops about 98 px per
  side. The app's new top/bottom gradient fits to width instead, which crops nothing. The
  safe area still protects against UI overlays either way, but `placement_fit` in
  `specs.json` should say which one is true. The status is PROVISIONAL until confirmed.
- **Static format.** `image.mission` is 1:1 (Command Center, Sidney 2026-10-13), but the
  pilot plan targets 1080×1920 statics. The safe area only applies to 9:16. Settle it in
  `specs.json` before any static is generated against it.
