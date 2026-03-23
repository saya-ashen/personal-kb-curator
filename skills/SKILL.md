---
name: personal-kb-curator
description: Use when an assistant needs to organize, deduplicate, and maintain a document collection... (保留原有头部描述)
---

# Personal KB Curator

Turn scattered files into maintainable knowledge assets.

## Operating modes & Commands

This skill acts as a router to the following execution commands. **The actual
rules and workflows are defined in the target repository's `docs/` layer.**

- **`kb-ask`**: Answer bounded questions against the curated repository.
  (Triggers for Q&A)
- **`kb-update`**: Merge specified new material into the repository. (Triggers
  for incremental maintenance)
- **`kb-curate`**: Discover, screen, stage, and optionally apply new external
  research items. (Triggers for proactive research)

## Supporting resources (For initial bootstrap only)

If the target repository does not have a rule layer (no `AGENTS.md` or `docs/`),
refer to:

- `references/repo-bootstrap.md` for repository anchor guidance.
- `templates/repo/` for reusable rule scaffolds.
- `references/schemas.md` for output fields.
