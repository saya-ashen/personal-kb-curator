# Skill: meeting-to-knowledge

## Purpose

Transform raw meeting text into reusable long-term knowledge artifacts.

## Steps

1. Parse meeting transcript or notes.
2. Produce summary, decisions, and action items.
3. Extract participants, topics, and linked projects.
4. Save normalized note in `meetings/`.
5. Update project notes under `projects/` when strongly related.
6. Trigger index refresh.

## Meeting Frontmatter Delta

Use base schema plus meeting-specific fields:

- `type: meeting`
- `meeting_date`
- `participants`
- `decisions`
- `action_items`
