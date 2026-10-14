# Mission Creatives Pipeline — Project Spec

> Owner: Igor · Stakeholders: Jean (product), Sidney & James (mission ops)
> Status: Phase 0 — built and tested against confirmed specs; awaiting upload sign-off
> This document is the source of truth for the agent (Codex / Claude) building this project.
> When something here is marked **OPEN**, ask before assuming.

---

## 1. Context

EarnOS is a rewards app. Users complete **missions** (sign up to a brand, reach a level in a game, make a first trade…) and get paid. Missions come from ad networks (via Swaarm), direct brand deals and self-funded campaigns.

Missions are created in the internal **Command Center** (`command.earnos.com`) through **Offer Discovery**:
pick offer → create mission (offer data auto-filled) → review description → **add creatives** → publish.

Every step takes minutes **except creatives**. Today Sidney sources them by hand: brand website → YouTube → Instagram → download → fix format in CapCut → upload. For small brands with no good assets this can take very long, and the result often looks cheap next to self-funded missions.

The feed autoplays video, TikTok-style. Only ~15 feed positions get real traffic, so the business needs **many more new missions live, faster, and looking premium**.

## 2. Goal

Go from **offer → mission-ready creatives** with minimal human work, at a quality level matching our best missions.

### Success metrics
- Time spent on creatives per mission: from today's manual baseline (**OPEN**: Sidney to estimate) to **< 5 min of human review**.
- % of missions where the pipeline's top asset is used without manual edits: target **≥ 70%** by end of Phase 2.
- 0 missions published with a wrong logo, wrong brand or wrong format.

## 3. Core principles (non-negotiable)

1. **Research first, generate second.** Always look for real, official brand assets before generating anything. Generation is a fallback for brands without usable material. Real assets are cheaper, safer (brand approval) and look more authentic.
2. **AI for judgment, scripts for mechanics.** The LLM decides *which* channel is official, *which* video is premium, *what* to prompt. Downloading, cutting, resizing, encoding, overlaying and uploading are **deterministic Python scripts**. Never ask the model to do what a script can.
3. **AI never draws logos or text.** Video models get logos and lettering wrong. Generated footage must be text-free and logo-free; the real logo and any copy are composited afterwards with FFmpeg.
4. **Agent-agnostic.** Everything is plain skills (`SKILL.md`), scripts and JSON. It must work the same from Codex (Sidney) and Claude Code (James).
5. **The manifest is the contract.** Every run writes a `manifest.json`. Later the Command Center integration only needs to read it.
6. **Cache per brand.** Once a brand has approved assets, reuse them for every network / country variant of that brand.
7. **Human in the loop until tuned.** The pipeline proposes; a person approves. Automation increases only after quality is proven.

## 4. Creative specs

Command Center limits confirmed by Sidney, 2026-10-13:

| Asset | Aspect | Resolution | Size | Format | Duration |
|---|---|---|---|---|---|
| Mission image | 1:1 | ≥ 1024×1024 | rec. ≤ 1.0 MB | PNG · JPG · WebP | — |
| Mission video | 9:16 | ≥ 1080×1920 | rec. ≤ 30.0 MB | MP4 H.264 · WebM | ≤ 30 s |

What the pipeline exports, and why:

| Asset | Export | Decision |
|---|---|---|
| Mission image | 1:1, 1080×1080, **WebP q92**, ≤ 1.0 MB | PNG blows the 1.0 MB cap on photographic sources (measured 1.59 MB worst case) and has no quality knob. WebP is in the accepted list and fits comfortably. |
| Feed video (sourced) | 9:16, 1080×1920, **30 fps**, MP4 H.264 high@4.0, CRF 21, ≤ 30 MB | **8–30 s** — calibrated against the library, where 12 of 27 shipped creatives are under 15 s. 30 fps is confirmed by all 27. |
| Feed video (generated) | **Generated at 720×1280, exported at 1080×1920**, 5–10 s | 720p generation keeps artifacts and credits down (§9.4), but 1080×1920 is the platform minimum, so the export upscales. Intended, flagged as a note not a warning. |

- Both size caps are **enforced, not warned about**: `normalize_video.py` re-encodes against a bitrate computed from the remaining budget, `normalize_image.py` steps down a quality ladder. An oversized file means a rejected upload, which is worse than a slightly softer one.
- MP4/H.264 over WebM: H.264 decodes in hardware on every phone and WebM buys nothing at this size.
- Image sources: Google Play previews are higher-res than App Store. Command Center's own screenshots are low-res — upscale before use, and expect the softness warning.

> **Implementation note.** These values live in machine-readable form in
> `skills/creative-standards/references/specs.json`, which every script reads, with the
> reasoning in `specs.md`. Changing a spec is a JSON edit, never a code change.

## 5. Inputs

### 5.1 Per run
```json
{
  "brand_name": "Crunchyroll",
  "brand_url": "https://www.crunchyroll.com",
  "offer_id": "swaarm-12345",
  "country": "US",
  "offer_summary": "Start a free trial",
  "app_store_url": "optional",
  "play_store_url": "optional"
}
```

### 5.2 Reference library (the "good examples")
Igor/Sidney's Google Drive folder with high-quality mission videos.
- **OPEN:** Drive folder link: `<DRIVE_FOLDER_URL>`
- Mirrored with `scripts/fetch_drive_library.py` to `references/library/raw/` (git-ignored, do not commit media). See `references/library/README.md` for what is actually in it — the folders mix shipped finals with the raw sources they were cut from, and only the 27 `feed*.mp4` files are the house standard.
- This is **not** model fine-tuning. The library is used to (a) derive a written style profile and rubric, and (b) provide visual references/keyframes for generation prompts.
- Later: add a `references/library/negative/` folder with examples of what we **don't** want (corporate, low-effort influencer UGC, blurry, wrong format).

## 6. Pipeline

```
offer input
   │
   ▼
[brand-kit]  → find official channels, logo, colors, app screenshots   (cached in brands/<slug>/)
   │
   ▼
[brand-research]  → collect candidates → download → normalize → score
   │
   ├── best score ≥ 70  ──────────────► top 3 assets → manifest → human review
   │
   └── best score < 70  ──► [video-generate] → 3–4 variants → overlay logo → normalize → score
                                                                   │
                                                                   ▼
                                                     top variants → manifest → human review
```

The orchestrator skill `mission-creatives` is the **only entry point** and enforces this order.

## 7. Repository structure

```
mission-creatives/
├── PROJECT.md                     # this file
├── AGENTS.md                      # Codex entry: points to skills/ and rules
├── CLAUDE.md                      # Claude Code entry: same content as AGENTS.md
├── skills/
│   ├── creative-standards/        # shared reference, read by every other skill
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── specs.json         # machine-readable, read by the scripts
│   │       ├── specs.md
│   │       ├── rubric.md
│   │       └── library_profile.md # generated in Phase 1 from the Drive library
│   ├── brand-kit/SKILL.md
│   ├── brand-research/SKILL.md
│   ├── video-generate/
│   │   ├── SKILL.md
│   │   └── templates/             # script templates (see §9.4)
│   └── mission-creatives/SKILL.md # orchestrator
├── scripts/
│   ├── specs.py                   # loads specs.json; no script hardcodes a spec
│   ├── probe.py                   # ffprobe wrapper, used by everything
│   ├── fetch_media.py
│   ├── normalize_video.py
│   ├── normalize_image.py
│   ├── extract_frames.py          # Phase 1
│   ├── brand_overlay.py           # Phase 2
│   └── profile_library.py         # Phase 1
├── references/library/            # raw/ and negative/ are git-ignored
├── brands/<slug>/                 # per-brand cache
│   ├── kit.json
│   ├── logo/ (svg/png, transparent)
│   ├── assets/approved/
│   └── runs/<timestamp>/manifest.json
└── tests/
```

## 8. Scripts (deterministic layer)

All scripts: Python 3.11+, CLI with `argparse`, JSON output on stdout, non-zero exit on failure, no LLM calls.

| Script | Purpose | Key behavior | Status |
|---|---|---|---|
| `probe.py <file>` | Read media metadata | width, height, aspect, duration, codec, fps, bitrate, size | **built** |
| `fetch_media.py <url> --out <dir>` | Download video/image | yt-dlp; best quality ≤ 1080p; save source URL + uploader in a sidecar `.json` | **built** |
| `normalize_video.py <in> --profile feed\|generated` | Make spec-compliant video | 9:16 via smart crop (center by default, `--focus x,y` override) or blurred-pad if crop loses subject; trim to duration window; export exact codec from §4 | **built** |
| `normalize_image.py <in>` | Make spec-compliant image | 1:1 crop, upscale if below min resolution, export format from §4 | **built** |
| `extract_frames.py <in> --out <dir> --n 6` | Frames for AI review | first frame + evenly spaced; scene-cut times, cuts/second, mean shot length | **built** |
| `brand_overlay.py <in> --logo <png> [--text] [--endcard]` | Composite real branding | logo position presets, safe margins for feed UI, optional 1.5 s end card | Phase 2 |
| `fetch_store_assets.py <play-url\|package> --out <dir>` | Pull icon + screenshots from Google Play | requests originals rather than carousel thumbnails; probes and sorts every candidate by resolution; warns when the icon is under the mission-image minimum or no vertical screenshot exists | **built** |
| `fetch_drive_library.py <folder> --out <dir>` | Mirror the Drive reference library | walks the tree, keeps per-brand structure, skips files already present, writes `_index.json` | **built** |
| `profile_library.py <dir>` | Analyze reference library | per-file stats + aggregates **per group** (feed / source / undersized / images), durations, cuts/second, aspect distribution, brand-skew share, first-frame thumbnails → JSON for the agent to interpret | **built** |

**Phase 0 acceptance:** a video downloaded from YouTube or Instagram goes through `normalize_video.py` and is accepted by the Command Center upload with no CapCut step.

## 9. Skills (judgment layer)

### 9.1 `creative-standards`
Reference-only skill. Contains `specs.json` / `specs.md` (§4), `rubric.md` (§10) and `library_profile.md`.
`library_profile.md` is written by the agent in Phase 1 from `profile_library.py` output + viewing frames of the library: pacing, typical length, framing, color, what makes the best ones premium, with 5–10 named examples and *why* each is good. **Igor reviews and owns this file.**

### 9.2 `brand-kit`
**Input:** run input (§5.1). **Output:** `brands/<slug>/kit.json` + logo files.
1. If `brands/<slug>/kit.json` exists and is < 90 days old, reuse it.
2. Identify **official** channels. Accept a channel only if at least one is true: verified badge (`yt-dlp` exposes `channel_is_verified`); listed on Wikidata; linked from the app-store listing; linked from the brand's own website. Record the evidence, and prefer two independent sources agreeing. **Note:** large brands routinely 403 automated fetches of their own site, so the website rule is the least executable of the four — see `skills/brand-kit/references/worked-example-crunchyroll.md`.
3. Collect logo (prefer SVG / transparent PNG from press/media kit, then Wikimedia Commons via Wikidata P154), primary colors **extracted from the logo file**, tagline, high-res app/product screenshots (Play Store first, via `fetch_store_assets.py`).
4. Never invent a logo. If none found at sufficient quality → flag `logo_missing: true` for human input.

```json
{
  "brand": "Crunchyroll",
  "slug": "crunchyroll",
  "official_channels": [
    {"platform": "youtube", "url": "...", "evidence": "linked in website footer"}
  ],
  "logo": {"path": "brands/crunchyroll/logo/logo.svg", "source": "...", "on_dark": true},
  "colors": ["#FF5E00"],
  "tagline": "...",
  "screenshots": ["..."],
  "logo_missing": false,
  "updated_at": "2026-10-13"
}
```

### 9.3 `brand-research` (workflow 1 — always runs first)
**Input:** run input + `kit.json`. **Output:** scored candidates in the manifest.
1. Check `brands/<slug>/assets/approved/` first — previously approved assets win if still on-spec.
2. Search sources in priority order:
   1. Official YouTube — Shorts first, then regular videos
   2. Official Instagram Reels (may fail due to login walls — log and continue)
   3. Brand website (hero videos, press/media kit)
   4. App Store / Google Play preview videos and screenshots
   5. Official TikTok
3. Shortlist up to **10** candidates by metadata (vertical first, recent, high views, not influencer-hosted).
4. Download, normalize, extract frames.
5. Score each with the rubric (§10) by looking at the frames. Write the reasoning.
6. Keep the top 3. Also always produce the 1:1 mission image.

### 9.4 `video-generate` (workflow 2 — fallback only)
Runs only if research's best score < 70, or a human explicitly asks.
1. Pick a script template from `templates/`:
   - `app-showcase` — phone/app UI in motion (fintech, games, apps)
   - `product-hero` — product close-ups (DTC, food, consumer goods)
   - `lifestyle` — person using the service in context
2. Start from a **real brand image** (screenshot / product photo from kit) as first frame — image-to-video, not pure text-to-video.
3. Prompt rules: describe scene, motion, camera, light, mood aligned with `library_profile.md`. **Explicitly forbid text, letters, logos, watermarks.** 9:16, 5–10 s, 720p.
4. Generate **3–4 variants** (tool: Higgsfield via MCP — **OPEN**: confirm access/models; max credits per mission, suggested cap: 60).
5. Score variants with the rubric; discard any with distorted product/UI or visible gibberish text.
6. Apply `brand_overlay.py` with the real logo (and optional end card), then `normalize_video.py --profile generated`.

### 9.5 `mission-creatives` (orchestrator)
**Input:** run input. **Output:** `brands/<slug>/runs/<ts>/manifest.json` + files.
1. `brand-kit` → 2. `brand-research` → 3. decide (§6) → 4. `video-generate` if needed → 5. write manifest → 6. print a short human summary: top pick, why, what needs a human (e.g. missing logo).
Never publishes. Never deletes approved assets.

## 10. Scoring rubric (0–100)

See `skills/creative-standards/references/rubric.md` — that file is the working copy.

| Criterion | Weight | What good looks like |
|---|---|---|
| Brand fidelity | 30 | Official source; correct logo/product; on-brand colors |
| Visual quality | 20 | Sharp, well lit, no compression artifacts, ≥ 720p source |
| Format fit | 15 | Native 9:16, or crops to 9:16 without losing the subject |
| Hook | 15 | Something compelling in the first 2 s; motion, not a static title |
| Tone | 10 | Matches `library_profile.md`; not stiff corporate, not low-effort UGC |
| Clean frame | 10 | No burned-in subtitles clutter, no foreign-language text, no CTA conflicting with the mission |

**Hard fails (score = 0):** wrong brand · another platform's watermark (e.g. TikTok logo) · competitor visible · explicit or sensitive content · source < 480p · AI-generated gibberish text.

**Thresholds:** ≥ 70 accept · 55–69 usable with human review · < 55 reject (→ generate).
Calibrate in Phase 1: scores on library videos should land ≥ 80; if not, adjust the rubric, not the library.

## 11. Manifest (contract)

```json
{
  "run_id": "2026-10-13T14:02:11Z",
  "input": { "...": "§5.1" },
  "path_taken": "research",
  "assets": [
    {
      "id": "a1",
      "kind": "video",
      "origin": "sourced",
      "file": "brands/crunchyroll/runs/.../a1_feed.mp4",
      "source_url": "https://youtube.com/shorts/...",
      "aspect": "9:16",
      "width": 1080, "height": 1920,
      "duration_s": 18.4,
      "score": 84,
      "score_breakdown": {"brand": 28, "quality": 18, "format": 15, "hook": 12, "tone": 6, "clean": 5},
      "reasoning": "Official Short, strong opening shot, native vertical.",
      "status": "proposed"
    },
    {
      "id": "i1",
      "kind": "image",
      "origin": "sourced",
      "file": ".../i1_mission.png",
      "aspect": "1:1",
      "score": 78,
      "status": "proposed"
    }
  ],
  "needs_human": [],
  "credits_used": 0
}
```
`status` lifecycle: `proposed` → `approved` (copied to `assets/approved/`) | `rejected`.

## 12. Phases

| Phase | Deliverable | Done when | Status |
|---|---|---|---|
| **0** | Repo skeleton, `probe`, `fetch_media`, `normalize_video`, `normalize_image` | Sidney uploads a pipeline-normalized video to Command Center with no CapCut | **Chain verified end to end 2026-10-14**: official Crunchyroll Short → 1080×1920 / 29.97 s / H.264 / 30 fps / 4.9 MB, every spec check passing, no CapCut. 26 tests green. Open: Sidney doing the actual upload. |
| **1** | Library downloaded, `profile_library.py`, `creative-standards` with `library_profile.md` + calibrated rubric, `brand-kit`, `brand-research`, `mission-creatives` (research path only) | Run on 10 real brands from the queue; ≥ 7 have an acceptable top asset; time per mission measured | **In progress** — library mirrored; `profile_library.py`, `extract_frames.py`, `fetch_store_assets.py` built; `brand-kit`, `brand-research` and `mission-creatives` written from real runs. Remaining: `library_profile.md` (Igor owns) + rubric calibration, then the 10-brand run |
| **2** | `video-generate` + `brand_overlay` + templates | On 5 small brands with no good assets, ≥ 3 produce an approved video with the correct logo | Not started |
| **3** | Command Center integration via MCP: read "needs creatives" draft queue, upload to Cloudflare, attach to mission | A draft saved without creatives gets proposals automatically. **Depends on Jean** (draft-without-creatives + Cloudflare) | Not started |

## 13. Open questions

- [x] ~~Exact codec/container/bitrate/size limits accepted by Command Center~~ — answered by Sidney 2026-10-13, see §4
- [x] ~~Mission image min resolution and format~~ — answered by Sidney 2026-10-13, see §4
- [x] ~~Drive library link~~ — https://drive.google.com/drive/folders/1j0s9X3HxP5ya7B9-2HZg2CXjD_p3Yifr ("Feed - Demos"), mirrored 2026-10-13. **Still open: who maintains it** (Igor/Sidney)
- [ ] **New:** the library's shipped creatives are 26/27 HEVC, but the stated Command Center spec is "MP4 H.264 · WebM". Does the uploader accept HEVC? If so it is ~30–40% more quality inside the same 30 MB (Sidney)
- [ ] **New:** `Crypto.com/` holds 40 DSP banner videos (1024×768, 480×320…) that are not feed creatives and skew every aggregate. Move them out of the library, or confirm they should be excluded (Sidney)
- [ ] Higgsfield MCP access, which models, credit budget per mission (Jean)
- [ ] Brand approval policy: when is sourced/generated content OK without brand sign-off? (Pascal/Jean)
- [ ] Instagram: acceptable to use a logged-in session for downloads, or YouTube/website only? (Jean)
- [ ] Where the pipeline runs long-term: local per person vs. a server triggered by Command Center (Jean)
- [x] ~~the local `yt-dlp` (2025.06.30) is blocked by YouTube~~ — upgraded to 2026.08.19 on Igor's machine 2026-10-14; YouTube downloads work. **Still open: the same upgrade on Sidney's and James's machines**, and a minimum version in the setup notes.

## 14. Instructions for the agent building this

- Work **phase by phase**. Do not start Phase N+1 until Phase N's "done when" is met and confirmed by Igor.
- Keep scripts small, tested (`tests/`) and free of LLM calls.
- Keep `AGENTS.md` and `CLAUDE.md` in sync; both must point to `skills/` and restate §3.
- Never commit media files or credentials. Use `.env` for any API keys.
- When unsure about a creative judgment, add it to `needs_human` instead of guessing.
- Output specs live only in `skills/creative-standards/references/specs.json`. Never hardcode one.
