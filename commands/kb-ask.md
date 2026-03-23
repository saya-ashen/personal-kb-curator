---
description: Answer a user question against the curated knowledge base with bounded retrieval
agent: build
---

Answer this user question using the current curated knowledge base: $1

Before answering:

1. Read `AGENTS.md`
2. Read `docs/kb-policy.md`
3. Read `docs/kb-structure.md`
4. Read `docs/kb-query-policy.md`
5. Read `00_index/master-index.md` when present
6. If a repository-local knowledge curation skill is available, follow it

Retrieval behavior:

- route from index first
- use a small first-pass set of likely relevant canonical assets
- do not read the full repository unless explicitly requested
- expand reads incrementally only when evidence is insufficient
- prefer canonical assets over drafts and archive material

Answer requirements:

- ground claims in retrieved sources
- include source paths used for key claims
- when sources conflict, present both claims and flag uncertainty
- for writing assistance, synthesize from canonical sources and clearly mark inferred content

If evidence remains insufficient after bounded expansion:

- ask the user to narrow scope or approve broader retrieval
