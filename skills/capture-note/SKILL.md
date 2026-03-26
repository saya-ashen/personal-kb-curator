# Skill: capture-note

## Purpose

Convert raw user input into a standardized Markdown note with frontmatter.

## Steps

1. Parse input text and infer intent.
2. Generate fields: `title`, `summary`, `tags`, `topics`, `projects`, `people`.
3. Generate stable note id format: `note-YYYYMMDD-<slug>`.
4. Write note to `notes/` as Markdown.
5. Trigger `rag/ingest` refresh pipeline.

## Note Frontmatter Template

```yaml
---
id: note-20260326-example
title: Example Title
created_at: 2026-03-26T08:00:00Z
updated_at: 2026-03-26T08:00:00Z
type: note
summary: One sentence summary.
tags: []
topics: []
projects: []
people: []
source: manual
confidence: medium
related: []
---
```
