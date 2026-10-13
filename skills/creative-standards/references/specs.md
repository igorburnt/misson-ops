# Output specs

`specs.json` in this folder is the machine-readable version and the one the scripts read.
This file is the human explanation. Keep the two in step.

> **Status: CONFIRMED** — Command Center limits from Sidney, 2026-10-13:
>
> - **Mission video:** 9:16, ≥ 1080×1920, rec. ≤ 30.0 MB, MP4 H.264 or WebM, ≤ 30 s
> - **Mission image:** 1:1, ≥ 1024×1024, rec. ≤ 1.0 MB, PNG / JPG / WebP

## Feed video — sourced (`video.feed`)

| Setting | Value | Why |
|---|---|---|
| Aspect / resolution | 9:16, 1080×1920 | The platform minimum, exactly |
| Duration | **8–30 s** | 30 s is the platform ceiling. The 8 s floor is calibrated: 12 of the 27 shipped house creatives are under 15 s (shortest 6.2 s, median 16.2 s), so PROJECT.md's original 15 s floor would have flagged half our own best work |
| FPS | **30** | See the decision note below |
| Video | H.264 high@4.0, yuv420p, CRF 21, preset slow, ceiling 12000 kbps | MP4/H.264 over WebM: H.264 decodes in hardware on every phone, and WebM buys nothing at this size. The bitrate ceiling is deliberately high — the house creatives run at a median 8676 kbps and up to 15094 — because the enforced 30 MB cap, not the ceiling, is what actually constrains the file |
| Audio | AAC 128 kbps, 48 kHz, stereo | The feed autoplays muted, but a missing audio track trips some uploaders — `normalize_video.py` adds a silent one when the source has none |
| Container | mp4, `+faststart` | Starts playing before the full file lands |
| Max size | **30 MB, enforced** | See the size-cap note below |

### Why 30 fps, not 24

Sources are social video, which is shot and delivered at 30 or 60. 60 → 30 is a clean 2:1
drop; 60 → 24 and 30 → 24 both need frame blending or dropping and show as judder, which
reads as cheap on a short autoplaying loop. 24 only buys a filmic look we are not after, and
saves roughly 10% bitrate we do not need inside a 30 MB budget. If a source is natively 24,
the conversion to 30 is still less visible than the judder from forcing everything to 24.

### The 30 MB cap is enforced, not warned about

CRF encoding does not know about file size — a detailed 30 s clip at CRF 21 can overshoot.
Overshooting means Sidney's upload is rejected after the fact, so `normalize_video.py`
re-encodes automatically: it computes a bitrate from the remaining budget
(`max_size_mb × 8 × 1024 ÷ duration − audio`, at 95% then 88% headroom) and reports
`encode_passes` plus a warning saying what it did. If it still cannot fit, the warning says to
shorten the cut rather than silently shipping an oversized file.

### Calibration against the library

These values were checked against the 27 shipped `feed*.mp4` creatives in the reference
library (mirrored 2026-10-13). What that evidence changed:

| Setting | Was | Now | Why |
|---|---|---|---|
| `min_duration_s` | 15 | **8** | 12 of 27 shipped creatives are under 15 s |
| `max_bitrate_kbps` | 7000 | **12000** | House median is 8676 kbps; a 7000 ceiling would have exported below our own standard |
| `fps` | 30 (judgment) | 30 (**confirmed**) | All 27 are 30 fps — not a preference, the house standard |

**Open with Sidney: the library is HEVC, the stated spec is H.264.** 26 of the 27 shipped
creatives are HEVC in an MP4 container, but the Command Center limits say "MP4 H.264 · WebM".
Either the uploader accepts HEVC in practice and the stated spec understates it, or these are
pre-upload masters. It matters: HEVC would buy roughly 30–40% more quality inside the same
30 MB. We export H.264 for now because it is strictly within the stated spec and decodes in
hardware everywhere — but if HEVC is genuinely accepted, that is a free quality win.

A real check: `Uber/feed-high.mp4` (HEVC, 1080×1920, 30 s, 26.56 MB) round-trips to H.264
1080×1920, 30 s, 20.51 MB in one pass with no warnings.

## Feed video — generated (`video.generated`)

**Resolution conflict, resolved.** PROJECT.md §9.4 says generate at 720p — correct, because
it means fewer artifacts and fewer credits. But the Command Center requires ≥ 1080×1920, so
720p cannot be the *export* resolution.

So: generate at 720×1280 (`generate_width` / `generate_height`, which `video-generate` will
read in Phase 2), then export upscaled to 1080×1920. The profile sets `allow_upscale: true`,
which makes `normalize_video.py` record the upscale as a **note** rather than a warning —
it is intended, not a quality defect. Everything else matches the feed profile; 5–10 s.

## Mission image (`image.mission`)

1:1, 1080×1080 (above the 1024×1024 minimum), **WebP at quality 92**, ≤ 1.0 MB enforced.

The library backs this up twice over: the house 1:1 images are named `*_1x1_1024.png` — the
1024 convention is real — and **7 of the 27 of them exceed the 1.0 MB cap**, the largest at
1.58 MB. Those are mostly PNGs. Our own library demonstrates the failure mode WebP avoids.

### Why WebP, not PNG

1.0 MB is tight. PNG is lossless, so a photographic or screenshot-heavy 1080×1080 routinely
lands at 2–3 MB — measured at 1.59 MB on a worst-case test source — and there is no quality
knob to turn. WebP holds the same frame at visually lossless quality well under the cap, and
it is in the accepted list. `normalize_image.py` steps down a quality ladder
(92 → 86 → 80 → 72) until the file fits and reports the quality it used.

Set `format` to `png` only for flat UI art where losslessness matters and the file is small,
or `jpg` if something downstream rejects WebP. If PNG is selected and the file overshoots,
the script says so explicitly — it will not silently ship an oversized image.

Sources below 1024×1024 are upscaled with lanczos and flagged. Prefer Google Play previews
over App Store thumbnails, and either over the Command Center's own low-res screenshots.

## Framing rules (`normalize_video.py`)

- **crop** — centre crop to 9:16. `--focus x,y` (0–1) moves the crop window when the subject is off-centre.
- **pad** — blurred, slightly darkened copy of the frame behind the whole frame. Use when a crop would cut the subject.
- **auto** (default) — crop when it discards ≤ 40% of the frame, pad otherwise. A 16:9 source loses ~68%, so it pads; a native 9:16 source crops with no loss.

A source shorter than the minimum is **never looped** — looping reads as cheap. The script
warns and leaves the short cut; find a longer source or accept it consciously.

## Hard floor

Source height below 480p is a rubric hard fail (score 0), not a normalization problem.
Do not upscale your way past it.
