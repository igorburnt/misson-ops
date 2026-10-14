---
name: mission-creatives
description: The orchestrator and the only entry point to the creatives pipeline. Takes an offer, runs brand-kit then brand-research, decides whether generation is needed, writes the manifest and prints a short human summary. Never publishes, never deletes approved assets.
---

# mission-creatives

**Input:** the run input (PROJECT.md §5.1). **Output:** `brands/<slug>/runs/<ts>/manifest.json`
plus files, and a short summary for the person reviewing.

This is the **only** entry point. Do not invoke `brand-research` or `video-generate` directly
for a real mission — the order below exists so that rule 1 cannot be skipped by accident.

Read `skills/creative-standards/SKILL.md` first.

## Order

```
1. brand-kit         → brands/<slug>/kit.json   (cached < 90 days)
2. brand-research    → scored candidates
3. decide            → best score >= 70 ? stop : continue
4. video-generate    → only if step 3 says so        [Phase 2, not built]
5. write manifest
6. print the summary
```

Create the run directory first: `brands/<slug>/runs/<UTC timestamp>/` with
`candidates/`, `normalized/`, `frames/`. Everything a run produces lives under it, so a run is
self-contained and reviewable later.

## Step 3 — the decision

| Best score | Action |
|---|---|
| ≥ 70 | Research path succeeded. Stop. `path_taken: "research"`, `credits_used: 0`. |
| 55–69 | Still research, but every proposed asset is flagged for human review. Do **not** generate just because nothing cleared 70 — a real asset at 65 usually beats a generated 75. |
| < 55 across the board | Fall through to `video-generate`. `path_taken: "generate"`. |
| Human explicitly asks | Generate regardless. |

**Until Phase 2 exists**, a sub-55 result is not a failure to paper over: write the manifest
with what research found, put the reason in `needs_human`, and say plainly in the summary that
this brand needs generation and that generation is not built yet.

## Step 5 — the manifest is the contract

PROJECT.md §11 is the schema. The Command Center integration in Phase 3 reads this file and
nothing else, so anything learned during the run that is not in the manifest is lost.

Carry forward: every candidate with its score breakdown and reasoning, rejected ones included;
provenance; `fit` and `crop_loss`; `path_taken`; `credits_used`; and a `needs_human` list that
merges what `brand-kit` and `brand-research` each raised.

## Step 6 — the summary

Short, and written for someone who has not read the manifest. Four things:

1. **The top pick and why** — one sentence of actual reasoning, not its score.
2. **What else is proposed**, with scores.
3. **What needs a human** — specific and actionable. Missing logo, trademark question, no
   vertical source, licensor attribution. If this list is empty, say so explicitly rather than
   omitting it, so a reader can tell the check ran.
4. **What it cost** — credits used, and whether generation ran.

## Hard limits

- **Never publishes.** The pipeline proposes; a person approves. Nothing here uploads to the
  Command Center or marks an asset live.
- **Never deletes approved assets.** `brands/<slug>/assets/approved/` is append-only from this
  skill's point of view.
- **Never invents a logo**, never composites one the brand has not been confirmed to allow.
- **`status` lifecycle is `proposed` → `approved` | `rejected`**, and only a human moves
  something to `approved`.

## When a run is uncertain, say so

The recurring failure mode for this pipeline is a run that looks clean because the hard
questions were not asked. A brand with a trademarked logo, an unfetchable website and licensed
source footage should produce a manifest with several `needs_human` entries. An empty list
there is a signal to check the work, not a sign the run went well.
