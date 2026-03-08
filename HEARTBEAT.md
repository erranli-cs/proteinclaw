# HEARTBEAT.md

This file defines recurring research and tool-watch work for the workspace agent.

The point is controlled scouting, not random browsing.

## Recurring responsibilities

### Literature scouting

Check for recent work related to:

- protein binder design
- protein structure prediction
- sequence design
- developability scoring
- mutational effect prediction
- benchmark datasets for proteins and complexes

Preferred source classes:

- PubMed and Europe PMC
- bioRxiv and arXiv
- official project repositories
- release notes and model cards

### Tool-watch

Track changes in:

- new model releases
- license term changes
- benchmark claims
- maintenance status
- code availability

## Output requirements

Each scouting pass should produce structured notes containing:

- source
- date checked
- claim summary
- category
- license notes
- action recommendation

Action recommendations should be one of:

- `ignore`
- `watch`
- `evaluate`
- `admit_to_registry`

Never admit a tool to the active registry automatically from scouting alone.

## Evaluation gate

Before a new tool is trusted for routing, require:

- reproducible access path
- license review
- benchmark or sanity-check evidence
- explicit adapter plan

## Failure policy

- If sources are unavailable, note the gap and continue with remaining sources.
- If a claim cannot be verified, mark it unverified.
- Do not rewrite the active tool registry from heartbeat tasks alone.
