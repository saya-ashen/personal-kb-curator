---
description: Incrementally merge specified new files into the current knowledge base
agent: build
---

Incrementally update the current knowledge base using only: $1

Before making any changes:

1. Read `AGENTS.md`
2. Read `docs/kb-policy.md`
3. Read `docs/kb-structure.md`
4. Read `docs/kb-update-policy.md`
5. Read `docs/kb-dedup-rules.md`
6. Read `00_index/master-index.md` and `00_index/change-log.md` when present
7. If a repository-local knowledge curation skill is available, follow it

Only process the files or directory specified in `$1`.
Do not rebuild the whole repository unless explicitly requested.

Classify each new item as:

- duplicate
- near_duplicate
- supplement
- conflict
- new_topic

Handle them as follows:

- duplicate: keep out of active content and mark for archive or recycle
- near_duplicate: merge only the useful delta into the canonical asset
- supplement: enrich the relevant canonical asset or topic note
- conflict: preserve both claims, keep source context, and flag for review
- new_topic: create a new canonical note or asset in the correct directory

Update where applicable:

- canonical notes or core assets
- master index
- source mapping
- change log

Return:

- items processed from `$1`
- classification result for each item
- updated notes or assets
- newly created topics
- archived or recycled items
- unresolved conflicts or uncertainties
- concise change summary
