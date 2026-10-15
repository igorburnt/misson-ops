---
description: Score already-collected brand assets and produce feed-ready files
argument-hint: [brand slug, e.g. atm-com]
---

Score and normalize the assets already collected for: **$ARGUMENTS**

This runs *after* `/brand`. It expects `brands/$ARGUMENTS/runs/<ts>/assets_index.json`
to exist; if it does not, say so and suggest running `/brand` first.

Follow `skills/brand-research/SKILL.md` for scoring and `skills/creative-standards/`
for the rubric and specs. Extract frames with `scripts/extract_frames.py` and **look at
them** — never score from metadata. Normalize with `scripts/normalize_video.py` and
`scripts/normalize_image.py`, then write `manifest.json`.
