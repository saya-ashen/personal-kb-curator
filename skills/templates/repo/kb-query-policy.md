# Knowledge Base Query Policy

## Scope

Apply this policy when answering user questions against an already curated knowledge base.

## Retrieval order

1. Read `AGENTS.md` and repository policy files if not already loaded.
2. Read the index first (`00_index/master-index.md` or repository-defined index).
3. Select a small first-pass set of candidate canonical assets.
4. Read additional assets only when initial evidence is insufficient.

## Retrieval bounds

- Do not read the entire repository by default.
- Prefer canonical assets, then supporting notes, then archive only when needed.
- Keep first-pass retrieval bounded (for example, 3-5 canonical assets).
- If expansion is needed, expand incrementally and state why.

## Answer grounding

- Base claims on retrieved sources, not assumptions.
- Include source paths for the key evidence used.
- When sources conflict, preserve both claims with context and flag uncertainty.
- For writing assistance, synthesize from canonical assets and note gaps.

## Escalation

- If evidence remains insufficient after bounded expansion, ask the user for scope refinement or permission to broaden retrieval.
