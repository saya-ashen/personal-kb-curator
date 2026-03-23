---
description: Incrementally merge specified new files into the current knowledge base
agent: build
---

Incrementally update the current knowledge base using only: $1

**Execution Rules:**

1. Read the local `AGENTS.md` first to locate the repository's policy files.
2. Read the local `docs/kb-update-policy.md` and `docs/kb-dedup-rules.md`.
3. Classify and handle each new item **strictly according to the definitions and
   actions defined in those local rule files**.
4. For file writing operations, follow `skills/references/update-protocol.md`.

Only process the files or directory specified in `$1`. Do not rebuild the whole
repository unless explicitly requested.

Follow `skills/references/update-protocol.md` for target selection, write
classes, and required compact-layer refreshes.

Update where applicable:

- canonical notes or core assets
- master index
- topic map
- source watchlist
- recent intake ledger
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
- any compact-layer files refreshed to keep future discovery bounded
