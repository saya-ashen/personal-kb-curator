# Repository Bootstrap

## Goal

Create a compact rule layer during initial cleanup so future updates do not
rediscover structure from scratch.

## Core anchor files

Generate these when ongoing maintenance is expected:

- `AGENTS.md`
- `docs/kb-policy.md`
- `docs/kb-structure.md`
- `docs/kb-update-policy.md`
- `docs/kb-dedup-rules.md`
- `docs/kb-query-policy.md`

Optional index files:

- `<index_dir>/master-index.md`
- `<index_dir>/change-log.md`

## Optional platform adapters

Only when required by the host platform, add adapter files (for example OpenCode
command and instruction files).

## AGENTS.md responsibilities

Keep it short. It should tell a future agent:

1. what this repository is
2. which files to read first
3. which files define the detailed policy
4. that incremental updates should not rebuild the entire repository by default
5. where question-answer retrieval rules are defined

## Policy file responsibilities

### kb-policy.md

Overall principles, intended outcomes, and default preservation behavior.

### kb-structure.md

Directory meanings, canonical asset placement, archive or recycle locations, and
naming conventions.

### kb-update-policy.md

Incremental update procedure, classification labels, required updated artifacts,
and summary format.

### kb-dedup-rules.md

Duplicate, near-duplicate, version-chain, supplement, and conflict rules.

### kb-query-policy.md

Question-answer retrieval procedure, retrieval bounds, preferred source order,
citation requirements, and conflict handling rules.

## Adaptation rule

Do not dump static templates unchanged. Fit the generated files to the
repository's actual structure, directory names, and asset families.

## Token economy rule

Keep `AGENTS.md` compact and push detail into the docs policy files. Later
commands should read `AGENTS.md` first, then only the policy files needed for
the task.
