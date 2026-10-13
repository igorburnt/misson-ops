---
name: creative-standards
description: Shared reference for every mission-creatives skill — output specs, the scoring rubric, and the style profile derived from the reference library. Read this before judging, generating or normalizing any asset.
---

# Creative standards

Reference-only. This skill produces nothing; every other skill reads it.

## Files

| File | What it is | Owner |
|---|---|---|
| `references/specs.json` | **Machine-readable output specs.** The scripts read this file directly. | Sidney (Command Center limits) |
| `references/specs.md` | The same specs in prose, with the reasoning. | Sidney / Igor |
| `references/rubric.md` | The 0–100 scoring rubric and hard fails. | Igor |
| `references/library_profile.md` | What "premium" looks like, derived from the reference library. | **Igor** — written in Phase 1, Igor reviews and owns it. |

## How to use this

- **Before normalizing anything:** nothing to do. The scripts read `specs.json` themselves. Never pass resolutions or codecs on the command line to override it.
- **Before scoring an asset:** read `rubric.md` and `library_profile.md`, look at the extracted frames, then score each criterion separately and write the reasoning. Never score from metadata alone.
- **Before writing a generation prompt:** read `library_profile.md` for pacing, framing, light and mood. Then apply rule 3 — no text, no letters, no logos, no watermarks in the generated footage.

## Changing a spec

Edit `references/specs.json` and keep `specs.md` in step. Do not hardcode a spec in a script, a skill or a prompt. Values carrying `"_status": "PROVISIONAL"` are PROJECT.md §13 open questions and are not yet confirmed by the Command Center.
