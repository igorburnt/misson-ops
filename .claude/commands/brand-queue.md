---
description: Research every pending brand in queue/brands.json and fill the generation queue (no image generation)
argument-hint: [optional brand names to add first, comma-separated]
---

Research the brand queue. Extra brands to add first: **$ARGUMENTS**

You do the research half of the pipeline; Codex does the generation half from
`skills/generate-queue/SKILL.md`. Your output is a `ready` item in `queue/generation.json`
that Codex can turn into a creative **without searching for anything**. Never generate
images here and never touch `queue/*.json` except through `scripts/work_queue.py`.

## 0. Queue

If names were given above, add each one:
`py -3 scripts/work_queue.py brand-add "<name>" [--copy "<mission copy>"] [--url <store or site>]`
(`python3` on macOS/Linux). Then list the work:
`py -3 scripts/work_queue.py brands --status pending`
and also `py -3 scripts/work_queue.py list --status needs_research`: items sent back by
review or by Codex, each with a `last_note` saying what to fix. Do those too (§4).

If both are empty, say so and stop.

## 1. Fan out

Each brand is independent. If you can run subagents, give each one brand (at most 4 at
a time) with this file's §2-§3 as its brief; queue writes are locked, so parallel agents are
safe. Otherwise work through them one by one. Mark each brand first:
`py -3 scripts/work_queue.py brand-set "<name>" researching`

## 2. Per brand: research

Follow `skills/brand-assets/SKILL.md` exactly (as `/brand` does): resolve the brand, build
`brands/<slug>/kit.json` with `skills/brand-kit/SKILL.md`, collect every asset raw.

The kit must record `logo.png` and `logo.png_url` (a PNG of at least 1600 px; Commons
`iiurlwidth=1600` thumburl, see brand-kit). Codex re-downloads the logo from that URL and
from nowhere else. No usable logo means `logo_missing: true`; the item will be blocked,
which is correct.

## 3. Per brand: static prep (static-creative §2-§3, stopping before generation)

In `brands/<slug>/runs/<ts>/static/`:

1. **`copy.json`**, format in `skills/static-creative/SKILL.md` §2. The mission copy from the
   queue entry comes first (source `mission`); otherwise the official sources, quoted exactly,
   each line with its `source_url`. Never write copy.
2. **`scene_prompt.txt`**, the §3 template, describing a scene drawn from the brand's real
   material you just collected (its world, palette, setting, light): not invented, not generic.
3. Queue it, choosing the lines to set (indexes into `copy.json`):
   `py -3 scripts/work_queue.py add <slug> brands/<slug>/runs/<ts>/static --lines 0 --by claude`
   Choose lines from one source unless a person approved mixing them. The script decides
   `ready` or `blocked` from what is on disk, and lists the reasons if blocked. Do not work
   around a block. Fix the cause or leave it blocked with the reason visible.
   **Queue notes are instructions for Codex, not warnings.** Codex reads every `--note` as
   something to act on, and sends the item back if a note says the logo or copy is in doubt.
   So a caution that does not block the item (outdated logo, parent-brand mark, trademark,
   compliance, wording to confirm) goes only in `needs_human` in the kit or `copy.json`,
   for the reviewer. It never goes in the queue note. If the caution is serious enough that
   Codex should not generate, it is a block: set `logo_missing: true` or fix the cause.
   Do not leave it queued as `ready` with a warning attached.
4. `py -3 scripts/work_queue.py brand-set "<name>" researched --slug <slug>` (or `failed` with
   `--note` if the brand could not be resolved).

## 4. Items sent back (`needs_research`)

Read `last_note`, fix the cause (new copy line, better logo PNG, corrected kit), then:
`py -3 scripts/work_queue.py set <id> ready --by claude --note "<what you fixed>" [--lines ...]`
The script re-checks everything before accepting `ready`.

## 5. Report

A table: brand, slug, item id, status (`ready`/`blocked`), copy chosen with its source,
and for blocked items the reasons. Then list everything in `needs_human`.

Close with the next step for the person:

- Codex on this machine: open Codex in this repo and send `Follow skills/generate-queue/SKILL.md.`
- Codex on another machine: commit and push first (queue, kits, copy and prompts are text and
  are tracked; logos and media are not, and Codex re-fetches the logo itself). Only commit when
  the person asks.
