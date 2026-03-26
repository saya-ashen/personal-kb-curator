# Skill: weekly-synthesis

## Purpose

Generate a weekly knowledge review from notes, meetings, and project updates.

## Steps

1. Collect artifacts created/updated in target week.
2. Extract highlights, key meetings, decisions, and open items.
3. Produce next-week suggestions based on evidence.
4. Save report to `reviews/`.
5. Link related notes for follow-up.

## Weekly Frontmatter Delta

Use base schema plus review-specific fields:

- `type: review`
- `period_start`
- `period_end`
- `key_decisions`
- `open_items`
