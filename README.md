# personal-kb-curator

A skill repository for **organizing, deduplicating, curating, and continuously
maintaining a personal knowledge base or document library**.

Use it when you need to turn a messy pile of notes, PDFs, screenshots, drafts,
and repeated versions into a reusable knowledge system instead of a one-off
cleanup.

Typical situations include:

- A folder is full of notes, screenshots, PDFs, drafts, and repeated versions,
  and you want to turn it into a maintainable knowledge base.
- You already have a knowledge base structure, but new material keeps arriving
  and needs **incremental ingestion and merging**.
- You want an assistant to answer questions by **preferring curated canonical
  assets** instead of scanning the whole repository.
- You want an agent to discover new papers, repos, posts, or tracked sources by
  first reading compact repository indexes instead of re-reading the whole
  knowledge base.
- You want explicit rules for “keep / archive / recycle / merge / flag
  conflicts” so the decision model stays stable over time.

## Goals

The purpose of this skill is not just to “move files around.” It is designed to
turn scattered material into:

1. **Reusable canonical knowledge assets**
2. **An inventory with explicit status and actions**
3. **A repository rule layer that supports future incremental updates**
4. **A controlled retrieval workflow for search and question answering**

In practice, that means the skill emphasizes:

- structure before summary
- classification before merging
- explicit conflict handling
- no full rebuilds by default
- maintainability for future assistants, not just a one-time cleanup

## Main use cases

### 0. Research discovery and staged merge

When the repository already captures your themes, this skill can support a
research-curation agent that:

- infers active focus from `AGENTS.md`, `docs/`, and `00_index/` compact files
- finds relevant new external items without scanning the whole repository
- ranks candidates by fit, novelty, and likely reuse value
- stages additions before handing durable writes to `commands/kb-update.md`


### 1. Repository bootstrap

When a collection is still unstructured, this skill helps you:

- inventory the material based on content, not only filenames
- detect duplicates, near-duplicates, supplements, version chains, and conflicts
- select or synthesize canonical notes / canonical assets
- establish `AGENTS.md` and `docs/` rule files
- produce indexes, change logs, and keep/archive/recycle decisions

### 2. Incremental maintenance

When a knowledge base already exists and new files arrive, this skill helps you:

- process only the new material
- classify how each item relates to existing canonical assets
- update only the impacted assets
- record what changed and what remains unresolved

### 3. Query-time retrieval

When users ask questions against an already curated repository, this skill
encourages:

- reading the rule layer first
- routing from the index before reading source files
- limiting the first pass to a small set of likely relevant canonical assets
- expanding reads only when the available evidence is insufficient
- citing sources and marking uncertainty or unresolved conflicts clearly

## Core methodology

This repository packages a knowledge-curation decision model.

### Classification labels

When incoming or existing material is clustered, items typically fall into one
of these relationship types:

- `duplicate`: materially the same asset with trivial differences
- `near_duplicate`: mostly the same asset with useful deltas
- `version_chain`: earlier or later revisions of the same asset
- `supplement`: additive material that does not replace the base asset
- `conflict`: materially inconsistent claims that cannot be silently merged
- `new_topic`: no existing canonical asset or cluster covers the content

### Action principles

- **duplicate**: archive or recycle it; do not keep it in active content
- **near_duplicate**: merge only the meaningful delta into the canonical asset
- **version_chain**: keep the strongest newest version active and archive older
  ones
- **supplement**: keep it as supporting material linked to the canonical asset
- **conflict**: preserve the conflict and flag it explicitly for review
- **new_topic**: create a new canonical note or topic asset

### Default values

- preserve signal and reduce noise
- prefer archive over delete when uncertain
- keep source mapping visible when synthesizing
- never hide conflicts inside a summary
- give every item an explicit status and action

## Repository layout

```text
.
├── commands/
│   └── kb-update.md               # Incremental update command guidance
└── skills/
    ├── SKILL.md                   # Main skill entry point and trigger description
    ├── references/
    │   ├── decision-model.md      # Classification and canonical selection rules
    │   ├── repo-bootstrap.md      # Guidance for creating the repository rule layer
    │   └── schemas.md             # Inventory and asset field definitions
    └── templates/
        ├── canonical-note.md      # Canonical note template
        ├── change-log.md          # Change log template
        ├── intake-manifest.json   # Intake manifest template
        └── repo/                  # Repository rule-layer templates
```

## Key files

### `skills/SKILL.md`

This is the primary skill definition. It describes:

- when the skill should trigger
- the three operating modes: bootstrap, incremental maintenance, and query-time
  retrieval
- the expected output contract
- the recommended reading order and working style

### `skills/references/decision-model.md`

Defines classification labels, canonical selection priorities, action mappings,
and safety rules.

### `skills/references/schemas.md`

Defines recommended fields for inventory items and canonical assets so outputs
stay consistent.

### `skills/references/repo-bootstrap.md`

Guides repository bootstrap by describing the rule-layer files that should be
created, including:

- `AGENTS.md`
- `docs/kb-policy.md`
- `docs/kb-structure.md`
- `docs/kb-update-policy.md`
- `docs/kb-dedup-rules.md`
- `docs/kb-query-policy.md`

### `skills/templates/`

Provides reusable output templates such as:

- canonical note
- change log
- intake manifest
- repository rule files

### `commands/kb-update.md`

Defines the expected behavior of the incremental update command, including:

- reading the rule layer first
- processing only the specified input
- classifying each item
- updating impacted assets, indexes, and change logs
- returning a concise summary of the update batch

## Recommended workflow

### Bootstrap a repository

1. Inventory the current material collection.
2. Cluster items by topic and relationship.
3. Create or synthesize canonical assets for high-value topics.
4. Separate the remaining material into supporting / archive / recycle
   categories.
5. Initialize the rule layer and index.
6. Record the work in a change log for future incremental maintenance.

### Run incremental updates

1. Read `AGENTS.md` and the `docs/` rule files.
2. Process only the newly added files or directories.
3. Classify each item as duplicate, supplement, conflict, and so on.
4. Update only the impacted canonical assets.
5. Sync indexes, source mapping, and the change log.

### Retrieve for Q&A

1. Read the repository rule layer first.
2. Route from the index.
3. Open only a small number of highly relevant canonical assets on the first
   pass.
4. Expand reads only if evidence is still insufficient.
5. Cite sources clearly and mark uncertainty or conflicts in the answer.

## Typical outputs

When this skill is used to curate a repository, it commonly produces:

- **Inventory**: a record of each input item’s status and action
- **Canonical Notes / Assets**: the primary reusable knowledge artifacts
- **Reorganization Map**: a map of how files were moved or grouped
- **Change Log**: a record of what was updated in a given pass
- **Repository Rule Layer**: the files that make future maintenance and
  retrieval repeatable

## How to use it

### Use it as a skill

If your agent environment supports local skill repositories, this skill is a
good fit for prompts such as:

- “Help me turn this folder of material into a usable knowledge base.”
- “These notes contain many repeated versions; curate them into canonical
  assets.”
- “Incrementally merge this new batch of PDFs into the existing knowledge base.”
- “Answer questions from this curated repository, but do not scan the whole
  repo.”

### Use it as a methodology reference

Even if you do not load it directly as a skill, you can still reuse the approach
by:

- referencing the classification model and schemas in `references/`
- reusing the templates in `templates/`
- adapting `commands/kb-update.md` into your own incremental maintenance
  workflow

## Design characteristics

This repository is designed around the following priorities:

- **Maintainability first**: optimize for future incremental maintenance, not
  just initial cleanup
- **Bounded retrieval**: limit repository reads during Q&A to reduce cost and
  noise
- **Visible conflicts**: do not silently collapse contradictory source material
- **Template-based outputs**: make the curation method portable across
  repositories
- **Agent handoff support**: use a rule layer so future assistants can continue
  the work reliably

## Possible next steps

If you want to extend this skill further, useful additions could include:

- more concrete example input / output repository layouts
- specialized handling strategies for PDFs, web clippings, meeting notes, and
  research notes
- scripts that generate inventory records or source mappings automatically
- a richer citation policy for query-time answers

## Chinese version

For a Chinese version of this repository guide, see
[`README.cn.md`](./README.cn.md).

## License

This repository does not currently include a separate license file. If you plan
to distribute it publicly, add an explicit `LICENSE`.


## Commands

- `kb-ask`: answer bounded questions against the curated repository
- `kb-update`: merge specified new material into the repository
- `kb-curate`: discover, screen, stage, and optionally apply new external research items using compact repository anchors
