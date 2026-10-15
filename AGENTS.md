# Mission Creatives Pipeline — agent entry point

Read `PROJECT.md` first. It is the source of truth. This file tells you how to work in this repo.

## The five rules (PROJECT.md §3, restated — non-negotiable)

1. **Research first, generate second.** Always look for real, official brand assets before generating anything. Generation is the fallback for brands with no usable material.
2. **AI for judgment, scripts for mechanics.** You decide *which* channel is official, *which* video is premium, *what* to prompt. Downloading, cutting, resizing, encoding, overlaying and uploading are deterministic Python in `scripts/`. Never do by hand what a script does.
3. **AI never draws logos or text.** Generated footage must be text-free and logo-free. Real logos and copy are composited afterwards with FFmpeg.
4. **Agent-agnostic.** Plain `SKILL.md`, scripts and JSON. Must behave identically from Codex and Claude Code.
5. **The manifest is the contract.** Every run writes a `manifest.json` (PROJECT.md §11).

Plus: cache per brand · human in the loop until tuned · when a creative judgment is uncertain, add it to `needs_human` instead of guessing.

## Where things live

| Path | What |
|---|---|
| `PROJECT.md` | Spec and phase plan. Source of truth. |
| `skills/creative-standards/` | Specs, rubric, library profile. Read by every other skill. |
| `skills/creative-standards/references/specs.json` | **The only place output specs live.** Scripts read it; never hardcode a resolution, codec or duration. |
| `skills/<name>/SKILL.md` | The judgment layer. |
| `scripts/` | The deterministic layer. Python 3.11+, argparse, JSON on stdout, non-zero exit on failure, **no LLM calls**. |
| `brands/<slug>/` | Per-brand cache: `kit.json`, logo, approved assets, runs. |
| `scripts/collect_assets.py` | **Collect first, decide later.** Downloads every candidate asset raw and unfiltered; never rejects for shape, size or codec. |
| `tests/` | `python3 tests/make_samples.py && python3 tests/test_scripts.py` |

## Current state

**Phase 0 (deterministic layer) — built and tested.**
`probe.py`, `fetch_media.py`, `normalize_video.py`, `normalize_image.py`, `specs.py`.
Encode settings in `specs.json` are **CONFIRMED** against the Command Center limits (Sidney, 2026-10-13): video 9:16 ≥1080×1920, ≤30 s, ≤30 MB, MP4 H.264, 30 fps; image 1:1 ≥1024×1024, ≤1 MB, WebP. Both size caps are enforced by re-encode, not just warned about.

Phase 0 is **not signed off** until Sidney uploads a pipeline-normalized video to Command Center with no CapCut step.

**Phase 1 — in progress.** Library mirrored (209 files, 32 brands). Built: `fetch_drive_library.py`, `profile_library.py`, `extract_frames.py`, `fetch_store_assets.py`, and the `brand-kit`, `brand-research` and `mission-creatives` skills — each written from a real run on Crunchyroll, with the worked examples under `skills/*/references/`.

Outstanding in Phase 1: **`library_profile.md`** (Igor owns it; the rubric's tone criterion points at it) and the rubric calibration pass. Phase 1's "done when" is a run over 10 real brands from the queue with ≥ 7 acceptable top assets.

**Phases 2–3 — not started.** `video-generate` holds a placeholder only. Do not start a phase before the previous one's "done when" is met and confirmed by Igor.

**Entry points.** `/brand <company>` collects a brand's source assets raw (see `skills/brand-assets/`).
`/brand-shortlist <slug>` scores and normalizes what was collected. Collection and judgment are
deliberately separate: an asset is never withheld for being landscape, oversized or the wrong codec,
because resizing is a downstream step and rejecting at collection time leaves the human nothing to
disagree with.

## Working rules

- Work phase by phase. Confirm with Igor before moving on.
- Keep `AGENTS.md` and `CLAUDE.md` identical in content.
- Never commit media files or credentials. Keys go in `.env` (git-ignored); see `.env.example`.
- Changing an output spec means editing `specs.json`, not a script.
