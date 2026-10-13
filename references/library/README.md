# Reference library

- `raw/` — the "good examples", mirrored from Drive. **Git-ignored. Never commit media.**
- `negative/` — what we do **not** want: corporate, low-effort influencer UGC, blurry, wrong format. Not yet populated.

Source: `https://drive.google.com/drive/folders/1j0s9X3HxP5ya7B9-2HZg2CXjD_p3Yifr` ("Feed - Demos", shared by link).

```bash
python3 scripts/fetch_drive_library.py \
  "https://drive.google.com/drive/folders/1j0s9X3HxP5ya7B9-2HZg2CXjD_p3Yifr" \
  --out references/library/raw
```

Re-running skips files already present at the right size. `raw/_index.json` records the
Drive id, path, mime and size of everything mirrored.

This is not model fine-tuning. The library is used to (a) derive a written style profile and
calibrate the rubric, and (b) provide visual references and keyframes for generation prompts.

## What is actually in it (mirrored 2026-10-13: 209 files, 1.05 GB, 32 brand folders)

The folders are **mixed** — shipped finals sitting next to the raw material they were cut
from. That distinction matters: the style profile must be derived from the finals, and the
raw sources are only useful as "what the input usually looks like".

| Group | Count | What it is |
|---|---|---|
| `<Brand>/feed.mp4`, `<Brand>/feed-high.mp4` | 27 videos, 24 brands | **The shipped feed creatives. This is the house standard.** |
| `*.publer.com.mp4` and similar | ~55 videos | Raw social scrapes — the input side, not the output |
| `Crypto.com/cryptocom_DSPtest_*` | 40 videos | Ad-network DSP banner videos at 1024×768, 480×320, 320×480… **Not feed creatives.** They skew every aggregate; exclude them. |
| `<Brand>/*_1x1_1024.png` etc. | 27 images | 1:1 mission images |
| `<Brand>/1-5.webp` (810×1440) | ~50 images | Play Store screenshot sets |

### What the 27 shipped creatives look like

- **30 fps, unanimously** — all 27.
- **9:16 at 1080×1920** — 22 of 27. The strays are 1080×2340 (phone screen recording), 1080×1918, 1080×1868, one 720×1278 at 0.3 MB (visibly low quality), and one 1920×1080 landscape 41 s file that looks like a stray source.
- **Duration 6.2–30.0 s, median 16.2 s.** 12 of 27 are under 15 s.
- **HEVC in 26 of 27**, MP4 container.
- **Size 0.3–27.6 MB, median 18.1 MB** — none over 30 MB, but several hugging it.
- **Bitrate median 8676 kbps, max 15094.**
- All 27 carry an audio track.

Two of these contradicted PROJECT.md §4 and the specs were corrected — see `specs.md`.

### Known skew

Crypto.com holds 42 of the 126 videos, 40 of them DSP banner tests. Any aggregate over the
whole library is really an aggregate over Crypto.com. Filter to `feed*.mp4` for the house
standard, or exclude that folder.
