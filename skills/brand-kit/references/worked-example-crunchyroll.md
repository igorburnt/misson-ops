# Worked example — brand-kit on Crunchyroll

Run 2026-10-14. Output: `example-kit-crunchyroll.json`.

## What happened

| Step | Result |
|---|---|
| Brand website footer | **403** — `crunchyroll.com` blocks automated fetches, browser UA included |
| YouTube verification | `channel_is_verified=true`, 9.28M subs, id `UC6pGDc4bFGD1_36IKv3FnYg` |
| Wikidata | official site, 9 YouTube ids, Instagram, TikTok, Facebook, 4 logo files |
| Cross-check | the verified channel id appears in Wikidata P2397 — two independent sources agree |
| Logo | `Crunchyroll 2024.svg` from Commons: real SVG, single outlined path, no `<text>` |
| Licence | public domain for copyright, `Restrictions: trademarked` |
| Colors | `#FF5E00`, the only fill in the SVG |
| Play Store | icon 512×512, 10 screenshots, 4 of them native 1080×1920 |

Total: 5 network calls. No guessing, no invented assets.

## Four things this changed in the skill

**1. The website is the least reliable evidence source, not the first.** PROJECT.md §9.2 lists
"linked from the brand's own website" first. Large consumer brands block bots, so in practice
this rule often cannot be executed at all. The skill now says to expect the 403, record
`website_fetchable: false`, and lean on the verified badge plus Wikidata — and explicitly not
to read a 403 as "no official channel found".

**2. Wikidata is the highest-yield single call.** One request returned the official site, nine
YouTube channel ids, Instagram, TikTok, Facebook and four logo files. It was not in the
original plan at all.

**3. "Public domain" is not permission.** Commons marked the logo public domain for copyright
*and* `Restrictions: trademarked`. An agent reading only the licence field would conclude the
logo is free to use. The skill now requires recording the licence verbatim and routing the
trademark question to `needs_human`.

**4. The app icon is too small to be the mission image.** 512×512 against a 1024×1024 minimum.
Square and official makes it look like the obvious pick, which is exactly why the script now
warns about it explicitly rather than leaving it to judgment.

## Also worth knowing

- Wikidata listed **9** YouTube channels for this one brand. Taking the first would have been
  wrong. Record the rejected ones so the next run does not redo the work.
- PROJECT.md §9.2's own example kit lists `#F47521` — the pre-2024 orange. The current logo is
  `#FF5E00`. Brand colors go stale; the logo file is the source of truth.
- Crunchyroll's Play listing has 4 native 1080×1920 screenshots. For a brand with none, every
  downstream 9:16 and 1:1 crop is compromised and that belongs in `needs_human`.
