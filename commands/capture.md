---
description: Capture a quick note into the Mem-lite knowledge base
agent: capture-agent
---

Capture this text into the knowledge base: $1

Operation contract:

- Primary operation: `import_document`
- Compatibility aliases: `upsert_document`, `create_note`, `update_note`

Execution rules:

1. Normalize into the note frontmatter schema.
2. Extract title, summary, tags, topics, projects, people.
3. Prefer `import_document` for writes; only use aliases when compatibility routing is required.
4. Trigger local index refresh.
5. Return created note path and key metadata.
