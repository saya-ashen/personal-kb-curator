# Skill: dedup-curation

## Purpose

Curate duplicate documents safely with scan, merge, and rollback workflows.

## Steps

1. Run `dedup_scan` to identify candidate groups and confidence tiers.
2. Review group evidence before merge, especially medium-confidence candidates.
3. Run `dedup_merge` for approved groups or explicit document id sets.
4. Validate merge output includes `merge_id`, `canonical_doc_id`, `compressed_summary`, and `diff_notes`.
5. If quality regresses, run `dedup_rollback` using the returned `merge_id`.
6. Record outcome as `merged`, `needs_review`, or `rolled_back`.

## Operation Contract

- Primary operations: `dedup_scan`, `dedup_merge`, `dedup_rollback`
- Compatibility aliases: none currently published for dedup operations
