# Skill: ask-my-knowledge

## Purpose

Answer user questions with retrieval-grounded evidence from local knowledge files.

## Steps

1. Run keyword search over frontmatter and body text.
2. Run semantic search over indexed chunks.
3. Merge and rerank results.
4. Draft answer only from retrieved context.
5. Include citations and related note recommendations.
6. Return `unknown` when evidence is insufficient.

## Output Contract

- `answer`
- `citations` (file path + snippet)
- `related_notes`
- `confidence`
