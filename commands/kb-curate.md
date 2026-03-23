---
description: Discover and stage new research items using repository index files and bounded retrieval
agent: research-curator
---

Discover, screen, and optionally stage new external information for this
knowledge base: $1

Discover, screen, and optionally stage new external information for this
knowledge base: $1.

**Execution Rules:**

1. Read the local `AGENTS.md` and `docs/kb-research-profile.md` to infer the
   active focus.
2. Read index files (like `topic-map.md`, `source-watchlist.md`) only as needed
   to verify targets.

Operate in one of these modes based on the user request:

- discover: return ranked candidates only
- draft: prepare repository-ready additions without writing them
- apply: write approved additions using the shared update protocol

Rules:

- do not scan the full repository by default
- infer active focus from the compact rule and index layer first
- only open a small, relevant subset of canonical assets when grounding is
  required
- do not call other commands; this command is the user entry point and
  `research-curator` is the executor

Return:

- the selected operating mode
- candidate items grouped by priority
- suggested repository targets
- any draft additions or applied changes
- any compact-layer files that should be refreshed
