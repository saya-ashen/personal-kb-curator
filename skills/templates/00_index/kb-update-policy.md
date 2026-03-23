# Incremental Update Policy

## Scope

Apply this policy when incrementally merging newly specified files or
directories into an existing curated knowledge base.

Defaults:

- only process the user-specified intake
- do not rebuild the whole repository unless explicitly requested
- do not rename or reorganize unrelated areas
- prefer small targeted updates over broad rewrites

## Update objectives

In order of priority:

1. preserve reusable information
2. keep canonical assets stable and discoverable
3. reduce duplication
4. refresh compact index layers when routing changes
5. record material changes for future maintenance

## Procedure

For each intake item:

1. identify the most likely canonical target, if any
2. classify the item using `docs/kb-dedup-rules.md`
3. apply the default action for that classification
4. refresh any affected canonical, index, or log files
5. record unresolved ambiguity instead of forcing destructive merges

When classification is ambiguous, choose the less destructive action.

## Classification source of truth

All label definitions and default actions are defined in:

- `docs/kb-dedup-rules.md`

Do not invent new labels unless the repository explicitly extends them.

## Required refresh targets

Refresh only what is affected:

- canonical note or core asset when synthesized content changes
- topic map or master index when a new topic, renamed asset, or routing change
  appears
- source mapping when source-to-canonical relationships change
- recent intake when items are staged but not fully merged
- change log for material updates
- source watchlist only when tracked entities, sources, or standing searches
  change

## Preservation defaults

- prefer archive over deletion when uncertain
- preserve provenance when merging non-trivial material
- do not silently overwrite conflicting claims
- avoid rewriting stable canonicals when a local patch is enough

## Escalate when

Escalate or ask for review when:

- no plausible canonical target can be identified
- multiple targets are equally plausible
- a conflict cannot be represented cleanly
- repository structure is missing required policy files
- the requested change implies a full rebuild

## Required update summary

Return a concise summary including:

- processed items
- classification for each item
- targets updated
- new topics created
- archived or staged items
- unresolved conflicts or uncertainties
- compact-layer files refreshed
- short change summary

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

## Token-economy guards for compact files

Apply these defaults unless the repository defines stricter limits:

- `00_index/recent-intake.md`: keep only the most recent 50 active rows
  (`candidate` or `approved`); move older or resolved entries to archived monthly
  files (for example `00_index/archive/recent-intake-YYYY-MM.md`)
- `00_index/topic-map.md`: keep one-line entries per topic; include one primary
  canonical path and at most two supporting paths
- `00_index/source-watchlist.md`: keep only active tracked entities and standing
  searches; remove or archive stale entries during periodic cleanup
- `00_index/change-log.md`: keep this file as a short pointer to recent monthly
  logs; store detailed history in monthly files (for example
  `00_index/change-log/YYYY-MM.md`)

When a compact file grows large, prefer rollover or archive over in-place
expansion.
