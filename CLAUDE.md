# Mission Creatives Pipeline — agent entry point

> Same content as `AGENTS.md` (Codex entry point). Keep both in sync.

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
| `tests/` | `python3 tests/make_samples.py && python3 tests/test_scripts.py` |

## Current state

**Phase 0 (deterministic layer) — built and tested.**
`probe.py`, `fetch_media.py`, `normalize_video.py`, `normalize_image.py`, `specs.py`.
Encode settings in `specs.json` are **CONFIRMED** against the Command Center limits (Sidney, 2026-10-13): video 9:16 ≥1080×1920, ≤30 s, ≤30 MB, MP4 H.264, 30 fps; image 1:1 ≥1024×1024, ≤1 MB, WebP. Both size caps are enforced by re-encode, not just warned about.

Phase 0 is **not signed off** until Sidney uploads a pipeline-normalized video to Command Center with no CapCut step.

**Phases 1–3 — not started.** The `brand-kit`, `brand-research`, `video-generate` and `mission-creatives` skill folders hold placeholders only. Do not start a phase before the previous one's "done when" is met and confirmed by Igor.

## Working rules

- Work phase by phase. Confirm with Igor before moving on.
- Keep `AGENTS.md` and `CLAUDE.md` identical in content.
- Never commit media files or credentials. Keys go in `.env` (git-ignored); see `.env.example`.
- Changing an output spec means editing `specs.json`, not a script.
