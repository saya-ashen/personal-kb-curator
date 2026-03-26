# Schemas

## Inventory item

Recommended fields:

- `item_id`
- `original_name`
- `inferred_type`
- `cluster`
- `status`
- `action`
- `time_relevance`
- `notes`

## Canonical asset

Recommended fields:

- `asset_id`
- `title`
- `purpose`
- `summary`
- `key_points`
- `source_items`
- `reuse_guidance`
- `related_assets`
- `last_updated`
- `confidence`

## Cluster relationship types

Allowed values:

- `duplicate`
- `near_duplicate`
- `version_chain`
- `supplement`
- `conflict`
- `new_topic`

## File action values

Allowed values:

- `keep-active`
- `keep-supporting`
- `merge-into-canonical`
- `archive`
- `recycle`
- `review-manually`
