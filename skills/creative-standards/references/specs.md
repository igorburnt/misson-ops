# Output specs

`specs.json` in this folder is the machine-readable version and the one the scripts read.
This file is the human explanation. Keep the two in step.

> **Status: PROVISIONAL.** Every number below is a working default from PROJECT.md §4's
> suggestions. The exact codec / container / bitrate / max file size the Command Center
> accepts is still open (PROJECT.md §13, owner: Sidney — shared in the 2026-10-13 call chat).
> When confirmed, edit `specs.json`, drop the `_status` flags, and re-run `tests/test_scripts.py`.

## Feed video — sourced (`video.feed`)

| Setting | Value | Why |
|---|---|---|
| Aspect / resolution | 9:16, 1080×1920 | The feed is full-screen vertical, TikTok-style |
| Duration | 15–30 s | Long enough to tell the mission, short enough to re-loop |
| FPS | 30 | Matches most social sources; avoids judder from 24↔30 conversion |
| Video | H.264 high@4.0, yuv420p, CRF 20, preset slow, max 8000 kbps | Universally decodable; CRF 20 is visually clean at 1080×1920 |
| Audio | AAC 128 kbps, 48 kHz, stereo | The feed autoplays muted, but a missing audio track trips some uploaders — `normalize_video.py` adds a silent one when the source has none |
| Container | mp4, `+faststart` | Starts playing before the full file lands |
| Max size | 50 MB | Provisional |

## Feed video — generated (`video.generated`)

Same codec family at 720×1280, 5–10 s, CRF 21, max 5000 kbps, 30 MB.
Shorter and smaller on purpose: fewer generation artifacts and fewer credits (PROJECT.md §4).

## Mission image (`image.mission`)

1:1, 1080×1080, PNG. Sources below 1080×1080 are upscaled with lanczos and flagged —
upscaled app-store thumbnails look soft, so prefer Google Play previews over App Store,
and prefer either over the Command Center's own low-res screenshots.

## Framing rules (`normalize_video.py`)

- **crop** — centre crop to 9:16. `--focus x,y` (0–1) moves the crop window when the subject is off-centre.
- **pad** — blurred, slightly darkened copy of the frame behind the whole frame. Use when a crop would cut the subject.
- **auto** (default) — crop when it discards ≤ 40% of the frame, pad otherwise. A 16:9 source loses ~68%, so it pads; a native 9:16 source crops with no loss.

A source shorter than the minimum is **never looped** — looping reads as cheap. The script warns and leaves the short cut; find a longer source or accept it consciously.

## Hard floor

Source height below 480p is a rubric hard fail (score 0), not a normalization problem. Do not upscale your way past it.
