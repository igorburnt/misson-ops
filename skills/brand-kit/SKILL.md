---
name: brand-kit
description: Find a brand's official channels, logo, colors and app screenshots, with recorded evidence for each, and cache them in brands/<slug>/kit.json. Runs first in the mission-creatives pipeline. Never invents a logo.
---

# brand-kit

**Input:** the run input (PROJECT.md §5.1). **Output:** `brands/<slug>/kit.json`, logo files, screenshots.

Read `skills/creative-standards/SKILL.md` first. Worked example: `references/worked-example-crunchyroll.md`.

## 0. Check the cache

If `brands/<slug>/kit.json` exists and `updated_at` is under 90 days old, reuse it and stop.
A brand's kit is reused across every network and country variant of that brand.

## 1. Identify official channels — evidence, not vibes

A channel is official only with recorded evidence. Accept on **any** of:

| Evidence | How to get it | Cost |
|---|---|---|
| Verified badge | `yt-dlp --playlist-items 1 --print "%(channel_id)s\|%(channel_is_verified)s\|%(channel_follower_count)s" <channel>/videos` | one call |
| Listed on Wikidata | `wikidata.org/w/api.php?action=wbgetentities&sites=enwiki&titles=<Brand>&props=claims&format=json` → P856 website, P2397 YouTube, P2003 Instagram, P7085 TikTok, P2013 Facebook, P154 logo | one call |
| Linked from the brand's own site | fetch the site footer | often blocked — see below |
| Linked from the app-store listing | `fetch_store_assets.py` output | one call |

**Prefer two independent sources agreeing.** For Crunchyroll the verified `@Crunchyroll` channel
id matched a Wikidata P2397 entry — that is a much stronger claim than either alone.

**Expect the brand's own website to be unfetchable.** `crunchyroll.com` returns 403 to any
automated request, including with a browser user-agent. This is normal for large consumer
brands. PROJECT.md §9.2 lists the website first, but in practice it is the *least* reliable
source. Do not burn calls retrying it — record `website_fetchable: false` and use the other
two. Never treat a 403 as "no official channel found".

**Wikidata often lists many channels** for one brand — 9 YouTube ids for Crunchyroll, mostly
regional and franchise accounts. Take the one matching the verified primary handle, and record
the others under `channels_rejected` with a note, so the next run does not re-investigate them.

## 2. Logo — never invent one

Rule 3 is absolute: the model never draws a logo. Sources, in order:

1. **The brand's press / media kit** — authoritative, and the only source that comes with usage terms. Try it first; it is often on a separate domain that is not blocked.
2. **Wikimedia Commons**, via Wikidata P154 → `commons.wikimedia.org/w/api.php?action=query&titles=File:<name>&prop=imageinfo&iiprop=url|size|mime|extmetadata`. Gives a real SVG plus licence metadata.
3. **The app-store icon** — a last resort, and usually too small (see §3).

Prefer SVG or transparent PNG. Check the SVG has no `<text>` element: an outlined path renders
identically everywhere, where a `<text>` logo depends on a font the compositor may not have.

**Read the licence metadata and record it.** Commons marked the Crunchyroll logo public domain
for *copyright* while `Restrictions: trademarked`. Those are different things, and "public
domain" is not permission to put a mark in a creative. Record the licence verbatim and put the
trademark question in `needs_human` — do not decide it.

If no logo is found at sufficient quality, set `logo_missing: true` and stop looking. A missing
logo is a clean handoff to a human; a wrong logo is one of the three things PROJECT.md §2 says
must never ship.

## 3. Screenshots and icon

`python3 scripts/fetch_store_assets.py <play-url-or-package-id> --out brands/<slug>/screenshots`

Google Play over the App Store: higher resolution, and Play serves any size, so the script
requests originals rather than carousel thumbnails. Results come back probed and sorted by
resolution — **pick by the reported dimensions, never by position in the list.**

Two things to check in the output:

- **The app icon is usually too small.** Crunchyroll's maxes out at 512×512, below the
  1024×1024 mission-image minimum. The script warns. Do not use the icon as the mission image
  on the strength of it being square.
- **Prefer vertical screenshots.** They crop to both 9:16 and 1:1 without losing the subject.
  Crunchyroll's listing had 4 native 1080×1920 among 10. If the warning says there are none,
  say so in `needs_human` — every downstream crop will be compromised.

## 4. Colors

Extract from the logo SVG's fills — that is the brand's own definition, and it is current by
construction. Crunchyroll's 2024 mark defines exactly one: `#FF5E00`.

Do not carry colors over from memory or from an older asset. PROJECT.md §9.2's own example kit
lists `#F47521`, the pre-2024 orange — stale by one rebrand. If the SVG and a remembered value
disagree, the SVG wins.

## 5. Write `kit.json`

Follow `references/example-kit-crunchyroll.json`. Every claim carries its evidence; anything
uncertain goes to `needs_human` rather than being guessed. Set `updated_at` to today.

## What good output looks like

- Each channel has an `evidence` string naming the specific source, not "official".
- Rejected candidates are recorded with the reason.
- The logo has `source`, `license` and `source_type` — a human can re-verify without redoing the work.
- Colors trace to the logo file.
- `needs_human` is populated with specific blockers. An empty `needs_human` on a brand with a
  trademarked logo and an unfetchable site is a sign the check was not done.
