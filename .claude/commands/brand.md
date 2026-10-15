---
description: Find a brand and collect all its source assets raw (no resizing, no filtering)
argument-hint: [company, offer name, store URL or website]
---

Collect source assets for: **$ARGUMENTS**

If no brand was given above, ask for one and stop.

Follow `skills/brand-assets/SKILL.md` exactly. In short:

1. Resolve the input to a real brand. Offer names carry network/country suffixes
   (`- US - CPA`) — strip them. App Store search resolves app offers to a legal entity.
2. Run `skills/brand-kit/SKILL.md` for identity, logo, colours, evidence → `brands/<slug>/kit.json`.
3. Enumerate every source: official YouTube, app-store artwork, site media, social.
4. Collect **everything** with `scripts/collect_assets.py` into `brands/<slug>/runs/<ts>/raw`.

**Collect first, decide later.** Do not skip a file because it is landscape, too long,
too large, low resolution or the wrong codec. Resizing happens in a later step. The only
reasons not to download are a dead URL or a file ffprobe cannot read.

Finish by showing the human the collected assets — actual dimensions and durations — plus
what was searched and not found, and what was blocked. Do not score and do not normalize.
