# Worked example — Crunchyroll, "Start a free trial" (US)

A real `brand-research` run, done by hand before the skill was written, so the skill could be
written from evidence rather than from the plan. Run output:
`example-manifest-crunchyroll.json`. Media is git-ignored; the manifest is the contract.

## What was done

1. Identified the official channel — `youtube.com/@Crunchyroll`, linked from the site footer, verified badge. Evidence recorded.
2. Shortlisted 5 Shorts by metadata (official, vertical, recent, 8.4k–27k views) + 1 branded teaser from the main channel.
3. `fetch_media.py` → `normalize_video.py --profile feed` → `extract_frames.py --n 5` on all 6.
4. **Looked at the frames.** Scored each criterion separately, wrote the reasoning.
5. Kept the top 3, produced the 1:1 mission image, wrote the manifest.

All 6 normalized clean: 1080×1920, ≤30 s, ≤30 MB, H.264, 30 fps, no warnings.

## Results

| Score | Status | Fit | Loss | Asset |
|---:|---|---|---:|---|
| **79** | proposed | crop | 0.00 | Ito Is In Love With Gen |
| 65 | proposed | crop | 0.00 | Stand Up, Subaru! |
| 64 | proposed | pad | 0.68 | SSS-Class Revival Hunter — Official Teaser |
| 64 | rejected | crop | 0.00 | Jiro and Rago |
| 59 | rejected | crop | 0.00 | Taira Appreciation Post |
| 55 | rejected | crop | 0.00 | She Thought He Was Feeling Her |

One asset cleared 70. Research path succeeded, no generation needed, 0 credits.

## The five things this run taught

### 1. Metadata ranks candidates almost backwards

All six looked equivalent in metadata: official channel, vertical, recent, healthy views.
After looking at frames they spanned 55 to 79. The **highest view count in the set (27k)
produced the lowest score (55)** — it opens deliberately out of focus on an empty interior
with a third-party publisher logo in the corner.

Metadata is for *shortlisting*. It cannot rank. Never score without extracting frames.

### 2. The first frame decides the hook score, and it is often not representative

`cFGULHZBrPk` looks like a blurred mistake at 0.00 s and is fine later. The feed autoplays —
the viewer sees the first half second and nothing else. Score the hook on frame 0, honestly,
even when later frames are better.

Conversely, do not score the *rest* from frame 0 either: the SSS-Class teaser looked clean at
0.00 s and turned out to carry burned-in subtitles from 3 s onward. Look at several frames.

### 3. Brand fidelity cannot rescue format fit

The teaser was the only genuinely Crunchyroll-branded candidate — brand fidelity 26/30, the
highest in the set. It still lost, because it is 16:9: padding discards 68% of the frame and
leaves the content in a band about a third of the screen height. **And its burned-in subtitles
land inside the blurred pad area rather than on the image, which reads as a rendering bug.**

If a 16:9 source has burned-in text anywhere, padding it will look broken. Prefer a native
9:16 source, or crop and accept the loss, or reject it.

### 4. Licensed-content brands fail "clean frame" structurally

Every official Crunchyroll Short carries a burned-in licensor copyright line
(`©Akira Ozaki/SHUEISHA, …`), and most carry burned-in English subtitles. This is not a run of
bad picks — it is how the category works, and it will repeat for every anime, film, music and
sports-streaming brand.

Two consequences:
- The copyright line is a required attribution. **Covering it with `brand_overlay.py` is not an
  option** — it goes to `needs_human` and waits on the brand approval policy.
- For this brand class, reorder the search: Play Store preview videos and the brand's own
  app-promo cuts **before** official Shorts, since those are brand content rather than clip
  content. The PROJECT.md §9.3 order is right for product brands, not for licensors.

### 5. A 70 threshold is doing real work

Only 1 of 6 cleared it. The 55–69 band held four assets that are genuinely usable-with-review
rather than good — exactly what that band is for. Nothing here needed generation, but a brand
with weaker assets would have fallen through, which is the intended behaviour.

## What a good run produces

- Every candidate scored per criterion with written reasoning — not one number.
- Provenance for every asset: source URL, uploader, upload date, view count.
- The framing decision recorded (`fit`, `crop_loss`) so a human can see what was discarded.
- `needs_human` populated with specific, actionable items — not left empty to look clean.
- Rejected candidates kept in the manifest with their reasoning, so the next run on this brand
  does not re-litigate them.
