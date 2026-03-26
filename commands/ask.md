---
description: Ask a natural-language question against local knowledge
agent: knowledge-agent
---

Answer this question from the knowledge base: $1

Operation contract:

- Primary operations: `hybrid_search`, `ask_with_citations`
- Compatibility aliases: `search_notes`, `answer_from_context`

Execution rules:

1. Run `hybrid_search` first, then answer from retrieved evidence with `ask_with_citations`.
2. Prefer `hybrid_search` by default (keyword + semantic fusion).
3. Use `ask_with_citations` by default for answer generation.
4. Include source citations and related note list.
5. If results are insufficient, return `unknown` instead of guessing.
