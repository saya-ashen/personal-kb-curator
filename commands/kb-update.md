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

Apply the classifications, required outputs, and refresh targets exactly as
defined by the local repository policies.
