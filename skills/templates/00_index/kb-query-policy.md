# Knowledge Base Query Policy

## Scope

Apply this policy when answering questions against an already curated knowledge
base.

Do not use this policy for repository-wide reorganization or incremental intake
processing.

## Query handling defaults

- answer from retrieved repository evidence, not assumptions
- prefer bounded retrieval
- do not scan the whole repository by default
- prefer canonical assets over drafts, staging, or archive material

## Retrieval order

1. read `AGENTS.md` if repository guidance is not already loaded
2. read the repository-defined index or routing layer first
3. select a small first-pass set of candidate canonical assets
4. read supporting notes only if canonical evidence is insufficient
5. read archive or superseded material only when history or conflict requires it

## Retrieval bounds

Default first pass:

- read the index layer
- read 3 to 5 candidate canonical assets
- read only compact summaries for intake and change logs first

Expand only when needed:

- expand incrementally
- state why expansion is needed
- prefer adjacent canonicals or directly referenced supporting notes
- do not broaden into repository-wide search without user approval
- do not open historical log archives unless the question is explicitly
  historical

## Source priority

Use sources in this order:

1. canonical assets
2. topic map, master index, and other routing files
3. supporting notes with clear provenance
4. staged intake only when clearly marked as not yet merged
5. archive or superseded material when historical context is needed

## Answer construction

- ground key claims in retrieved sources
- distinguish retrieved fact from inference
- when synthesizing, prefer canonical assets
- for writing assistance, clearly separate grounded content from bridging
  language
- do not fill evidence gaps with ungrounded assumptions

## Citation rules

- include source paths for key claims
- cite the canonical source when possible
- when multiple sources are needed, cite the minimal sufficient set
- label historical or superseded sources as such when used

## Compact file usage defaults

- prefer `topic-map` and current canonical assets over large historical logs
- if `recent-intake` is needed, use the active list first and read archived
  months only when unresolved context is required
- if change history is needed, start from the latest monthly log and expand only
  when evidence is still missing

## Conflict handling

- do not collapse conflicting claims into one unsupported narrative
- present both claims with source context
- prefer the current canonical position only when older material is explicitly
  superseded
- otherwise preserve uncertainty clearly

## Insufficient evidence

If evidence remains insufficient after bounded expansion:

1. ask the user to narrow scope, or
2. ask for permission to broaden retrieval

If the repository does not contain enough evidence, say so plainly.
