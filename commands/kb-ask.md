---
description: Answer a user question against the curated knowledge base with bounded retrieval
agent: build
---

Answer this user question using the current curated knowledge base: $1.

**Execution Rules:**

1. Read the local `AGENTS.md` and `docs/kb-query-policy.md`.
2. You must strictly follow the retrieval bounds, expansion rules, and citation
   requirements defined in the local `kb-query-policy.md`.

Answer requirements:

- ground claims in retrieved sources
- include source paths used for key claims
- when sources conflict, present both claims and flag uncertainty
- for writing assistance, synthesize from canonical sources and clearly mark
  inferred content

If evidence remains insufficient after bounded expansion:

- ask the user to narrow scope or approve broader retrieval
