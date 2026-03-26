---
description: Scan, merge, and rollback duplicate knowledge documents
agent: knowledge-agent
---

Run dedup curation on the knowledge base.

Recommended operational flow: `skills/dedup-curation/SKILL.md`

Operation contract:

- Primary operations: `dedup_scan`, `dedup_merge`, `dedup_rollback`
- Compatibility aliases: none currently published for dedup operations

Execution rules:

1. Run `dedup_scan` first to produce candidate groups and confidence bands.
2. Use `dedup_merge` only after selecting a group or explicit document ids.
3. Return merge artifacts including `merge_id`, `canonical_doc_id`, `compressed_summary`, and `diff_notes`.
4. If merge quality is questioned, run `dedup_rollback` with `merge_id`.
5. Always report actionable next step: merge, review, or rollback.
