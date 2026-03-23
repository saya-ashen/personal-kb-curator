# Decision Model

## Classification labels

- `duplicate`: same asset with immaterial differences
- `near_duplicate`: mostly same asset with useful deltas
- `version_chain`: earlier or later revision of same asset
- `supplement`: additive material that does not replace base asset
- `conflict`: materially inconsistent claims that cannot be silently merged
- `new_topic`: no existing cluster or canonical asset

## Canonical selection

Prefer the candidate that is most:

1. accurate
2. current
3. complete
4. reusable
5. internally consistent

## Action mapping

- `duplicate` -> `archive` or `recycle`
- `near_duplicate` -> `merge-into-canonical`
- `version_chain` -> newest strong version active, older archived
- `supplement` -> `keep-supporting` and link to canonical asset
- `conflict` -> `review-manually` or explicit conflict note
- `new_topic` -> `keep-active` and create canonical note

## Incremental update rule

For new batches, classify first, then update only impacted canonical assets.

## Safety rules

- Never silently collapse conflicting claims.
- Preserve source mapping when synthesizing.
- If confidence is low, prefer archive or manual review over deletion.
