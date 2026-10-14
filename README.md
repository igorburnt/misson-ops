# mission-creatives

Offer → mission-ready creatives, with minimal human work. See `PROJECT.md` for the spec,
`AGENTS.md` / `CLAUDE.md` for the agent entry point.

## Setup

```bash
brew install ffmpeg yt-dlp     # yt-dlp must be current — YouTube blocks older builds
python3 --version              # 3.11+
cp .env.example .env           # no keys needed for Phase 0
```

## Phase 0 — the deterministic layer

```bash
# metadata
python3 scripts/probe.py <file>

# download, keeping provenance in a sidecar .json
python3 scripts/fetch_media.py <url> --out downloads/
python3 scripts/fetch_media.py <image-url> --out downloads/ --image

# normalize to spec
python3 scripts/normalize_video.py <in.mp4> --profile feed        # 9:16, 15-30s
python3 scripts/normalize_video.py <in.mp4> --profile generated   # 9:16, 5-10s, 720p
python3 scripts/normalize_video.py <in.mp4> --profile feed --fit crop --focus 0.4,0.35
python3 scripts/normalize_image.py <in.png>                       # 1:1 mission image -> .webp
```

Every script prints JSON and exits non-zero on failure. Output specs come from
`skills/creative-standards/references/specs.json` — change specs there, never in a script.

Current targets (Command Center limits, confirmed 2026-10-13):

| | Export |
|---|---|
| Mission video | 9:16 1080×1920, 30 fps, MP4 H.264, 15–30 s, ≤ 30 MB |
| Generated video | rendered 720×1280, exported 1080×1920, 5–10 s |
| Mission image | 1:1 1080×1080, WebP q92, ≤ 1.0 MB |

Both size caps are enforced: the video re-encodes against the remaining budget, the image
steps down a quality ladder. Check `warnings` and `encode_passes` in the JSON.

## Phase 1 — the analysis layer

```bash
# mirror the reference library (skips what is already there)
python3 scripts/fetch_drive_library.py <drive-folder-url> --out references/library/raw

# per-group stats + first-frame thumbnails
python3 scripts/profile_library.py references/library/raw \
  --out references/library/profile.json --thumbs references/library/thumbs

# frames and pacing for one video
python3 scripts/extract_frames.py <in.mp4> --out frames/ --n 6
```

`profile_library.py` reports aggregates **per group**, because the library mixes shipped
finals (`feed*.mp4` — the house standard), raw social scrapes, and ad-network banner videos.
An average across all of them describes nothing. Each group also reports its top brand's
share, so a lopsided aggregate is visible rather than hidden.

## Tests

```bash
python3 tests/make_samples.py     # generates git-ignored fixtures with ffmpeg
python3 tests/test_scripts.py     # or: python3 -m pytest tests/ -q
```
