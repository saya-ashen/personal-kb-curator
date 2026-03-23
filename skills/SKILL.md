---
name: personal-kb-curator
description: Use when an assistant needs to organize, deduplicate, and maintain a document collection as a reusable knowledge base with canonical assets, explicit keep/archive/recycle decisions, and incremental updates.
---

# Personal KB Curator

Turn scattered files into maintainable knowledge assets. Prioritize future reuse, explicit decisions, and traceable synthesis.

## Core workflow

1. Inventory items from content, not filenames only.
2. Cluster related items (duplicates, versions, supplements, conflicts, new topics).
3. Select or synthesize canonical assets for important clusters.
4. Separate active assets from supporting, archive, and recycle material.
5. For ongoing maintenance, update only impacted canonical assets.

## Decision rules

- Preserve signal and reduce noise; archive over delete when uncertain.
- Organize for future retrieval and reuse, not original folder history.
- Keep provenance visible when synthesizing.
- Do not silently merge conflicts; resolve explicitly or leave flagged.
- Mark every item with explicit status and action.

## Operating modes

### Repository bootstrap

Use for unstructured collections that need durable structure and policy anchors.

Typical outputs:

- inventory
- canonical notes
- reorganization map
- keep/archive/recycle decisions
- repository rule layer

### Incremental maintenance

Use for already curated repositories with newly added material.

Before updating, read rule files if present (agent guide, policy docs, structure docs, update or dedup rules, index, and change log).

Then classify incoming items and update only affected canonical assets.

## Output contract

When practical, produce:

1. Inventory (fields defined in `references/schemas.md`).
2. Canonical notes (use `templates/canonical-note.md` as needed).
3. Reorganization map.
4. Change log entry (use `templates/change-log.md` as needed).

## Repository rule layer

For maintainable repositories, create concise anchors:

- root agent guide (for read order and defaults)
- policy document
- structure document
- update policy document
- dedup rules document

Use `references/repo-bootstrap.md` and `templates/repo/`.

## Supporting resources

- `references/decision-model.md` for classification and canonical selection rules
- `references/schemas.md` for output fields and labels
- `references/repo-bootstrap.md` for repository anchor guidance
- `templates/` for reusable note, manifest, and policy scaffolds

## Working style

- Start with structure, then summarize.
- Keep canonical assets concise and reusable.
- Preserve enough metadata for future incremental updates.
