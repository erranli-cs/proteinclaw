# PicoClaw Workspace Contract

## Purpose

This document explains how the PicoClaw workspace is expected to behave in this repository.

It complements:

- `AGENT.md` for engineering discipline
- `AGENTS.md` for agent behavior
- `TOOLS.md` for allowed tool classes
- `HEARTBEAT.md` for recurring scouting work

## Workspace files

### `AGENT.md`

Defines repo-wide engineering expectations:

- git hygiene
- TDD expectations
- PR cleanliness
- code review workflow

### `AGENTS.md`

Defines PicoClaw's operating behavior:

- mission and scope
- clarification policy
- output expectations
- memory policy
- failure handling

### `TOOLS.md`

Defines the allowed tool surface and expected failure handling.

### `HEARTBEAT.md`

Defines recurring literature scouting and tool-watch behavior.

## Working directory layout

Use the following layout as the default:

```text
artifacts/
  campaigns/<campaign_id>/
    campaign-spec.json
    report.md
    trace/
    provenance/
    candidates/
docs/
  specs/
  runbooks/
scripts/
tests/
```

## Clarification contract

The workspace agent should ask users follow-up questions only when the answer materially changes:

- execution mode
- search space
- target interpretation
- hard scientific constraints

Questions should explain why the answer matters.

## Memory contract

Allowed persistent memory:

- public target metadata caches
- tool metadata
- repo conventions
- scouting summaries

Campaign-local memory:

- user-specific decisions
- hypotheses
- candidate rankings
- trace events

Campaign-local memory should not be treated as global truth without explicit promotion.

## Verification contract

The repo should include a simple verification command that checks whether required workspace files exist and contain critical sections.
