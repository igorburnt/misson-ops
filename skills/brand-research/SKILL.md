---
name: brand-research
description: Workflow 1 of the mission-creatives pipeline, and it always runs first. Finds real brand video and imagery from official sources, normalizes it to spec, scores it against the rubric by looking at extracted frames, and proposes the top 3 in the manifest. Generation is only ever a fallback from here.
---

# brand-research

**Input:** run input (PROJECT.md §5.1) + `brands/<slug>/kit.json` from `brand-kit`.
**Output:** scored candidates in `brands/<slug>/runs/<ts>/manifest.json`.

Read `skills/creative-standards/SKILL.md` first — `rubric.md` and `library_profile.md` are the
scoring inputs. Worked example with real numbers: `references/worked-example-crunchyroll.md`.

Rule 1 is why this skill exists: real assets before generated ones, always. A score of 68 from
a real brand video usually beats a generated 75 — it is cheaper, it is authentic, and it does
not need the brand to approve something we invented.

## 0. Check what is already approved

Look in `brands/<slug>/assets/approved/` first. A previously approved asset that is still
on-spec wins outright — no search, no credits, no second review. This is the whole point of
the per-brand cache, and the most common way a run should finish early.

## 1. Classify the brand before choosing sources

**This step is not optional, and it is not in PROJECT.md §9.3.** The fixed source order there
assumes a brand that makes its own product content. It is wrong for licensors.

| Class | What the official channel actually contains | Search order |
|---|---|---|
| **Product brand** — apps, fintech, DTC, games, retail | Product and brand content | §9.3 order: Shorts → Reels → website → store → TikTok |
| **Licensed content** — anime, film, music, sports streaming | Clips of third-party content with burned-in licensor credits and subtitles | **Store preview videos and the brand's own app-promo cuts first**, then official brand teasers, then Shorts |

You can tell from `kit.json` and one look at the channel: if the titles are episode and series
names rather than the brand's name, it is a licensor.

Why this matters, measured: on Crunchyroll, 5 of 6 candidates from the official channel scored
55–65 because **every official Short carries a burned-in licensor copyright line** and most
carry burned-in English subtitles. That is the category working as designed, not a bad pick.

## 2. Shortlist up to 10 — but know what metadata can and cannot tell you

Rank by: native vertical first, recent, healthy views, not influencer-hosted, brand-named
titles over episode titles.

**Metadata shortlists. It cannot rank.** In the worked example all six candidates looked
equivalent on metadata and scored 55 to 79 once the frames were examined — and the highest
view count in the set produced the lowest score. Never write a score before step 4.

## 3. Download and normalize

```bash
python3 scripts/fetch_media.py <url> --out <run>/candidates
python3 scripts/normalize_video.py <file> --profile feed --out <run>/normalized/<id>.mp4
python3 scripts/extract_frames.py <run>/normalized/<id>.mp4 --out <run>/frames --n 5
```

Instagram may fail on a login wall. **Log it and continue** — it is expected, not a run failure.

Read the normalizer's JSON, not just its exit code. `fit`, `crop_loss` and `warnings` are
scoring evidence: a `pad` with `crop_loss: 0.68` has already told you the format score before
you look at anything.

## 4. Score by looking at the frames

Open the frames. Score each of the six criteria separately, write one sentence of reasoning
per asset, record the breakdown in the manifest. Four rules the worked example established:

- **Score the hook on frame 0, honestly.** The feed autoplays; the viewer sees the first half
  second. One candidate opened deliberately out of focus on an empty interior and got 3/15 for
  hook despite being fine later. That is correct.
- **Do not score anything else from frame 0.** The branded teaser looked clean at 0.00 s and
  carried burned-in subtitles from 3 s on. Look at several frames before scoring clean frame.
- **Brand fidelity cannot rescue format fit.** That teaser scored highest in the set on brand
  (26/30) and still lost: 16:9 padded to 9:16 discards 68% of the frame, and its burned-in
  subtitles landed *inside the blurred pad band*, which reads as a rendering bug. If a 16:9
  source has burned-in text anywhere, padding will look broken — crop it or reject it.
- **Check the subject against the feed UI.** A candidate with its subject in the bottom third
  lost hook points because the feed chrome sits exactly there.

Apply the hard fails literally (rubric.md). A third-party *licensor* credit is not a competitor
and not an automatic zero — it is a clean-frame penalty plus a `needs_human` entry.

## 5. Keep the top 3, and always produce the mission image

Top 3 by score go in as `status: proposed`; the rest stay in the manifest as `rejected` **with
their reasoning**, so the next run on this brand does not re-litigate them.

The 1:1 mission image comes from `kit.json` screenshots where possible — prefer a native
vertical screenshot, which crops to 1:1 without losing the subject — and only falls back to a
still from the winning video. Say which it was in the reasoning; a still from licensed footage
scores worse on brand fidelity than a real product screenshot.

```bash
python3 scripts/normalize_image.py <source> --out <run>/i1_mission.webp --focus 0.5,0.33
```

## 6. Hand off

Best score **≥ 70** → research path succeeded, write the manifest, stop. **< 70** → the
orchestrator falls through to `video-generate`. Do not generate from inside this skill.

Expect the threshold to bite: only 1 of 6 cleared 70 on a major brand with a 9.28M-subscriber
channel. That is the threshold doing its job.

## What good output looks like

- Every candidate scored per criterion with written reasoning — never a bare number.
- Provenance on every asset: source URL, uploader, upload date, view count.
- `fit` and `crop_loss` recorded, so a human can see what was discarded without opening the file.
- Rejected candidates kept with reasons.
- `needs_human` populated with specific, actionable items. On a licensor brand an empty
  `needs_human` means the attribution question was not asked.
