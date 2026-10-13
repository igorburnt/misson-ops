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
python3 scripts/normalize_image.py <in.png>                       # 1:1 mission image
```

Every script prints JSON and exits non-zero on failure. Output specs come from
`skills/creative-standards/references/specs.json` — change specs there, never in a script.

## Tests

```bash
python3 tests/make_samples.py     # generates git-ignored fixtures with ffmpeg
python3 tests/test_scripts.py     # or: python3 -m pytest tests/ -q
```
