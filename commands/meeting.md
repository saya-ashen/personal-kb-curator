---
description: Convert meeting transcript or notes into long-term knowledge
agent: capture-agent
---

Process this meeting content into structured knowledge: $1

Execution rules:

1. Produce meeting summary, decisions, and action items.
2. Extract related projects, topics, and participants.
3. Save a meeting note in `meetings/` with standard frontmatter.
4. Update related `projects/` notes when strong linkage exists.
5. Refresh index and return changed file list.
