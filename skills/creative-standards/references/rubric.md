# Scoring rubric (0–100)

Score every candidate asset against all six criteria by **looking at the extracted frames**,
never from metadata alone. Write one sentence of reasoning per asset and record the
per-criterion breakdown in the manifest (`score_breakdown`, PROJECT.md §11).

| Criterion | Weight | What good looks like |
|---|---|---|
| Brand fidelity | 30 | Official source; correct logo and product; on-brand colors |
| Visual quality | 20 | Sharp, well lit, no compression artifacts, source ≥ 720p |
| Format fit | 15 | Native 9:16, or crops to 9:16 without losing the subject |
| Hook | 15 | Something compelling in the first 2 s; motion, not a static title card |
| Tone | 10 | Matches `library_profile.md`; not stiff corporate, not low-effort UGC |
| Clean frame | 10 | No burned-in subtitle clutter, no foreign-language text, no CTA that conflicts with the mission |

## Hard fails — score 0, no partial credit

- Wrong brand
- Another platform's watermark (TikTok logo, Reels badge, CapCut outro)
- A competitor visible in frame
- Explicit or sensitive content
- Source below 480p
- AI-generated gibberish text or lettering

## Thresholds

| Score | Action |
|---|---|
| ≥ 70 | Accept |
| 55–69 | Usable, but flag for human review in `needs_human` |
| < 55 | Reject → fall through to `video-generate` |

## Calibration (Phase 1)

Score the reference library with this rubric. The library videos should land **≥ 80**.
If they do not, the rubric is wrong — adjust the rubric, not the library.
Record the calibration run and the adjustments made.
