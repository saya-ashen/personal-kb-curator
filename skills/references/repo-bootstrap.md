# Repository Bootstrap

## Goal

Create a compact rule layer during initial cleanup so future updates do not
rediscover structure from scratch.

## Core anchor files

Generate these when ongoing maintenance is expected:

- `AGENTS.md`
- `docs/kb-policy.md`
- `docs/kb-structure.md`
- `docs/kb-update-policy.md`
- `docs/kb-dedup-rules.md`
- `docs/kb-query-policy.md`
- `docs/kb-research-profile.md` when discovery or monitoring is expected

Optional index files:

- `<index_dir>/master-index.md`
- `<index_dir>/topic-map.md`
- `<index_dir>/source-watchlist.md`
- `<index_dir>/recent-intake.md`
- `<index_dir>/change-log.md`

## Optional platform adapters

Only when required by the host platform, add adapter files (for example OpenCode
command and instruction files).

## AGENTS.md responsibilities

Keep it short. It should tell a future agent:

1. what this repository is
2. which files to read first
3. which files define the detailed policy
4. that incremental updates should not rebuild the entire repository by default
5. where question-answer retrieval rules are defined

## Policy file responsibilities

### kb-policy.md

Overall principles, intended outcomes, and default preservation behavior.

### kb-structure.md

Directory meanings, canonical asset placement, archive or recycle locations, and
naming conventions.

### kb-update-policy.md

Incremental update procedure, classification labels, required updated artifacts,
and summary format.

### kb-dedup-rules.md

Duplicate, near-duplicate, version-chain, supplement, and conflict rules.

### kb-query-policy.md

Question-answer retrieval procedure, retrieval bounds, preferred source order,
citation requirements, and conflict handling rules.

## Adaptation rule

Do not dump static templates unchanged. Fit the generated files to the
repository's actual structure, directory names, and asset families.

## Token economy rule

Keep `AGENTS.md` compact and push detail into the docs policy files. Later
commands should read `AGENTS.md` first, then only the policy files needed for
the task.

## Discovery-friendly compact layer

When the repository will be used for proactive research discovery, add a compact
layer so future agents can infer current focus without scanning many canonical
notes.

Recommended files:

- `docs/kb-research-profile.md`: active priorities, exclusions, tracked
  entities, and update targets
- `00_index/topic-map.md`: topic routing map from themes to canonical files
- `00_index/source-watchlist.md`: tracked authors, venues, repos, feeds, and
  standing search seeds
- `00_index/recent-intake.md`: staging area for candidate additions before full
  merge

The compact layer should be cheap to read and must be updated when new topics,
new tracked entities, or new staged candidates are introduced.
