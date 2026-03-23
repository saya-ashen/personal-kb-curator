# Update Protocol

Shared durable-write rules for both `kb-update` and `kb-curate`.

Use this protocol when repository content will be created, merged, or rewritten.
Commands are user entry points; agents should reuse this protocol directly
instead of calling sibling commands.

## Goals

- keep durable writes consistent across incremental maintenance and research
  curation
- preserve bounded retrieval by maintaining compact index files
- avoid duplicate canonical notes and unclear placement

## Target selection

Choose the write target in this order:

1. existing canonical asset mapped by `00_index/topic-map.md`
2. repository target specified by `docs/kb-research-profile.md`
3. intake or watchlist location for uncertain items
4. new canonical note only when no mapped target exists and the item is clearly
   durable

## Required side effects after durable writes

Refresh any impacted compact files:

- `00_index/topic-map.md` when a topic route changes or a new topic is created
- `00_index/source-watchlist.md` when tracked authors, venues, repos, or feeds
  change
- `00_index/recent-intake.md` when candidates are staged, approved, or resolved
- `00_index/change-log.md` when a durable repository change is made
- `00_index/master-index.md` when canonical asset inventory changes materially

## Repository hygiene

- prefer updating existing canonical assets over creating parallel notes
- preserve provenance when synthesizing
- do not silently collapse conflicts
- keep staged discovery output separate from canonical content until approved or
  policy-allowed
- record enough context so future updates can stay bounded
