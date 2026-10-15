---
name: brand-assets
description: Given a company or offer name, find the brand's official identity and collect every usable source asset raw and unfiltered into brands/<slug>/runs/<ts>/raw, with an assets_index.json describing each file. Collection only - no cropping, no scoring, no rejection.
---

# brand-assets

**Input:** a company name, offer name, store URL or website. Nothing else.
**Output:** `brands/<slug>/kit.json`, `brands/<slug>/runs/<ts>/raw/*`, `assets_index.json`.

This skill **collects**. It does not judge. Scoring and normalizing are separate
steps that run later, on the material this produces.

## The rule that defines this skill

> Collect first. Decide later.

A file is **not** rejected for being landscape, low resolution, too long, too large,
the wrong codec or the wrong aspect ratio. All of that is fixable downstream and
none of it is your call at collection time. Download it, probe it, describe it,
record it.

Only two things stop a download: the URL is dead, or ffprobe cannot read the file.

**Why this matters.** On the ATM.com run the agent judged the available video
unusable and never downloaded it, so the human had nothing to look at and no way
to disagree. Six Credit Strong videos *were* downloaded before being judged, and
those stayed useful. Withholding material is the failure mode; an oversized
landscape file the human can look at and reject themselves is not.

## 1. Resolve the name to a brand

The input is often an offer name, not a brand name -- "ATM Cash Advance・Instant
Money" resolves to ATM.com, Inc.; "Credit Strong - US - CPA" to Credit Strong.
Strip the network and country suffixes (`- US - CPA`, `- UK - CPI`) before searching.

App Store search is the fastest resolver for an app offer and returns the legal
entity name:

```
curl -s "https://itunes.apple.com/search?term=<name>&entity=software&country=us&limit=8"
```

Confirm the first result is actually the brand and not a competitor -- that search
returns rivals freely. Then run `brand-kit` for identity, logo, colours and evidence.

## 2. Enumerate sources, then take all of them

| Source | How |
|---|---|
| Official YouTube | `yt-dlp --flat-playlist --print "%(id)s\|%(duration)s\|%(view_count)s\|%(title)s" <channel>/videos` |
| App store artwork | `fetch_store_assets.py <package> --out brands/<slug>/screenshots` |
| Site media | logo SVGs, hero video, press kit |
| Instagram / TikTok | needs a logged-in session -- see Blocked sources |

Then collect everything found:

```
python3 scripts/collect_assets.py --brand "<Brand>" --out brands/<slug>/runs/<ts> \
  --video <url> --video <url> --image <url>
```

or put the URLs in a file, one per line, `# image` suffix to mark an image, and
pass `--urls-file`.

## 3. Third-party material

If no official video exists, collect third-party video anyway -- but label it.
`uploader` is already in `assets_index.json`; add a line to `needs_human` naming
the channel and saying it is not first-party.

**Do not silently include hostile content.** ATM.com's search results included
"ATM.COM LEGIT or a SCAM?" and "Several Cash Advance Apps Got Sued". Collect it if
it is the only footage of the product, flag it explicitly, and never let it reach a
shortlist without a human seeing what it is.

## 4. Blocked sources are findings, not silence

Instagram and TikTok need a logged-in session and currently fail. When a source is
unreachable, record it in `assets_index.json` failures and in `needs_human` with the
reason. "No vertical video found" and "could not reach the one place vertical video
lives" are different answers and the human needs to know which one they got.

## 5. Hand off

Report to the human:
- what the brand resolved to, and on what evidence
- every asset collected, with its real dimensions and duration
- what was looked for and not found, and what was blocked
- which files carry third-party logos or burned-in legal text

Then stop. Scoring is `brand-research`. Resizing is `normalize_video.py` /
`normalize_image.py`. Do not run them from here.

## What good output looks like

- Every file that could be downloaded was downloaded, whatever shape it is in.
- `assets_index.json` describes each file without grading it.
- Nothing was dropped silently; blocked and missing are distinguished.
- The human can disagree with any call made, because the material is in front of them.
