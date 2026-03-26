# Deduplication and Merge Rules

## Decision principles

- compare by information content, not filename alone
- prefer semantic overlap over cosmetic similarity
- treat provenance and revision order as important signals
- when uncertain, choose the less destructive action

## Labels

### duplicate

Definition: materially the same information as an existing asset, with no
meaningful net-new content.

Default action:

- do not create a new canonical
- do not merge unless provenance must be recorded
- archive or discard the extra copy according to repository practice

### near_duplicate

Definition: mostly overlaps with an existing canonical asset, but includes minor
additions, clarifications, or structural variation.

Default action:

- merge net-new details into the existing canonical
- archive or recycle the residual copy
- do not keep parallel canonicals

### supplement

Definition: adds meaningful evidence, examples, references, or subpoints to an
existing canonical asset, but does not justify a separate topic.

Default action:

- integrate into the existing canonical or linked supporting material
- update source mapping when needed
- keep provenance if the source matters

### conflict

Definition: covers the same topic as existing material but contains materially
incompatible claims, interpretations, dates, or recommendations.

Default action:

- preserve both claims
- annotate the conflict context
- do not silently overwrite
- escalate when a clean representation is not possible

### new_topic

Definition: introduces a stable new subject, entity, workflow, or theme that
should not be absorbed into an existing canonical without overloading it.

Default action:

- create a new canonical asset
- add it to the topic map or index
- map sources to the new asset

### version_chain

Definition: belongs to a sequence of revisions of the same asset, where one item
supersedes or updates another.

Default action:

- keep lineage between versions
- prefer the latest stable version as primary
- archive earlier versions instead of treating them as peer canonicals

### superseded

Definition: older material that remains historically useful but is no longer the
current operating view.

Default action:

- mark as superseded
- point to the replacement canonical when known
- exclude from default first-pass retrieval unless history is requested

## Boundary rules

- `duplicate` vs `near_duplicate`: if there is no meaningful net-new content,
  use `duplicate`; otherwise use `near_duplicate`

- `near_duplicate` vs `supplement`: if the intake is mostly a rewritten copy of
  an existing asset, use `near_duplicate`; if it mainly contributes additive
  content to that asset, use `supplement`

- `supplement` vs `new_topic`: if the material fits naturally inside an existing
  canonical, use `supplement`; if it would create a distinct durable subject,
  use `new_topic`

- `conflict` vs `version_chain`: if one item is a later revision of the same
  asset, use `version_chain`; if they are competing claims within the same
  scope, use `conflict`

## Action mapping

- duplicate -> no new canonical; archive extra copy
- near_duplicate -> merge into canonical; archive residual copy
- supplement -> integrate into canonical or support layer
- conflict -> preserve both; annotate; escalate if needed
- new_topic -> create canonical; update index
- version_chain -> preserve lineage; keep latest primary
- superseded -> retain for history; do not treat as current default
