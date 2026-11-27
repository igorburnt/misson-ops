---
name: static-creative
description: Rebuild a mission static as a 9:16 creative - an image model redraws the scene with no text and no logo, then the brand's real logo and copy are composited inside the safe area by scripts/brand_overlay.py and checked. Use when a static breaks the safe area, is the wrong ratio, or is missing.
---

# static-creative

**Input:** a brand slug (with `brands/<slug>/kit.json`), the copy for the creative, and
optionally the current creative as a reference.
**Output:** `brands/<slug>/runs/<ts>/static/`: `scene.png`, `scene_prompt.txt`, `layout.json`,
`final.png`, `final_boxes.json`, `final_check.png`, `static.json`.

Read `skills/creative-standards/SKILL.md` and `skills/safe-area/SKILL.md` first.

## The split

| Who | What |
|---|---|
| Image model | The scene. Never logos, text, letters, numbers or UI (rule 3). |
| You | The scene prompt, the copy, which logo variant, where each element goes, and whether the result looks right. |
| `brand_overlay.py` | Draws the real logo and copy, measures them, runs the safe-area check. |

The model redraws the whole scene from scratch. That is intended: nothing is pasted back
over it, so there are no seams. What it must not draw is anything the brand depends on.

## 1. Kit

`brands/<slug>/kit.json` must have a PNG logo (`logo.png`). FFmpeg cannot render SVG.
Logos are never committed, so on a fresh clone the file is missing: run
`scripts/fetch_kit_logo.py <slug>`, which downloads it again from the kit's `logo.png_url`. If the
kit only has an SVG from Wikimedia Commons, take Commons' PNG rendering (`iiurlwidth=1600` in
the imageinfo query, see `brand-kit`). If `logo_missing` is true, stop: a creative without
the real logo is not a fallback, it goes to `needs_human`.

Font: use `kit.font` if present. Otherwise use a bold system sans (Windows
`C:/Windows/Fonts/arialbd.ttf`, macOS `/System/Library/Fonts/Supplemental/Arial Bold.ttf`)
and add "brand font not available, used <font>" to `needs_human`.

## 2. Copy

Sources, in order, always quoted **exactly** and recorded in `static.json` with where they
came from:

1. The mission's copy.
2. The current creative's copy, transcribed.
3. The brand's own official copy: App Store subtitle, Google Play short description, or the
   tagline on the brand's site or official YouTube channel. Record the URL.

Do not rewrite, translate or invent copy. A line written by you or by a model is not a
fallback; if none of the three exists, stop and put it in `needs_human`. Offers, prices and legal lines go to `needs_human` for a
person to confirm word for word. Keep it short: v2.1 §12 says cut copy before shrinking it.

Write the candidates to `copy.json` in the static folder. `scripts/work_queue.py` reads it,
so keep the shape:

```json
{
  "brand": "Chime",
  "lines": [
    {"text": "Credit, Cash back, Savings", "source": "App Store subtitle",
     "source_url": "https://apps.apple.com/us/app/chime-mobile-banking/id836215269"}
  ],
  "not_used": [{"text": "...", "where": "...", "why": "legal line"}],
  "needs_human": ["..."]
}
```

Every line needs `text` and `source_url`. Which lines are set on the creative is chosen when
the item is queued (`work_queue.py add ... --lines 0,1`), not here.

## 3. Scene

Write the prompt to `scene_prompt.txt` first, then generate. Template:

```
A 9:16 vertical photograph for a mobile ad for <brand>: <scene, taken from the reference
creative or the brand's world - setting, subject, light, mood>.

Composition (mandatory):
- Main subject between 30% and 65% of the image height, inside the central 70% of the width.
- Keep the band from 14% to 26% of the height calm and low in detail (sky, wall, soft
  shadow, plain surface): a logo will be placed there later.
- Keep the band from 68% to 85% of the height calm and darker or lighter than the rest:
  a headline will be placed there later.
- Backgrounds, light and texture may run to every edge.

Forbidden: any text, letters, numbers, logos, brand marks, signage, UI, watermarks,
screens showing content. No real or famous people. No other brands' products.
```

The bands match the default slots in §4. If you move the slots, move the bands with them.

**Generating.** If you have a native image tool (Codex `image_gen`), use it and save to
`scene.png` in the run folder. If you do not (Claude Code has none), stop after writing
`scene_prompt.txt` and add to `needs_human`: "generate scene.png from scene_prompt.txt and
save it to <run>/static/". Never substitute a stock or downloaded image for the scene.

**Look at the scene before going on.** Hard fail and regenerate (at most twice) if it has any
lettering, gibberish text, a logo or brand mark, another platform's watermark, or a subject
that ignores the bands. After two failed attempts, stop and put it in `needs_human`.

## 4. Layout

Write `layout.json` in 1080×1920 canvas pixels. See `scripts/brand_overlay.py` for the format.
Default slots, all inside the safe area less `min_padding_px`:

| Element | Slot `[x0, y0, x1, y1]` |
|---|---|
| Logo | `[340, 300, 740, 420]` |
| Headline, line 1 | `[190, 1330, 890, 1420]` |
| Headline, line 2 | `[190, 1430, 890, 1520]` |
| Headline, line 3 | `[190, 1530, 890, 1620]` |

- Look at `scene.png` and move a slot if it lands on a face, the subject or a busy area.
- One text element per line, all lines of a headline in the same `group`.
- Pick colours for contrast with the scene behind the slot. Use `shadow: true` for text on
  photographs. Use `tint` only on a single-colour logo (e.g. a black wordmark shown white on a
  dark scene); never tint a multi-colour logo.
- A CTA is a text element with `button`.

## 5. Composite and check

```
python3 scripts/brand_overlay.py <run>/static/scene.png --layout <run>/static/layout.json \
  --out <run>/static/final.png --overlay <run>/static/final_check.png
```

(`py -3` instead of `python3` on Windows.)

Exit 0 means every element is inside the safe area; the boxes are measured from the rendered
pixels, so the check is exact. Exit 1 usually means a slot leaves the safe area or a line does
not fit above `min_font_px`. Fix the layout or shorten the line; do not override.

Then **look at `final.png`**: contrast, the logo legible, nothing covering a face or the
subject. The script checks geometry; it cannot check taste.

## 6. Record

`static.json`: brand, copy used, scene prompt, generator used, the overlay result and
`needs_human`. Do not normalize yet: the static output format (1:1 in `specs.json` vs 9:16
in the pilot plan) is not settled.

## Working from the queue

In the research/generation split, research stops after `copy.json` and `scene_prompt.txt` and
queues the item (`/brand-queue`); generation (`skills/generate-queue/SKILL.md`) does §3-§6
and writes everything into the attempt folder the queue hands out
(`<run>/static/attempt-N/`), so retries never overwrite earlier work.

## needs_human, always

- The copy, if it contains an offer, price or legal line.
- "Scene generated by AI": a person approves it before it represents the brand.
- A missing brand font, a missing logo, a logo below 400 px wide.
- Anything you regenerated twice and still did not like.
