# Clawd v0 System Contract

## Purpose

This document freezes the product boundary for Clawd v0.

The goal is to stop the project from turning into an oversized prompt wrapper with unclear responsibilities.

## Product definition

Clawd v0 is a scientist-facing copilot for protein binder design against protein targets.

It accepts a natural-language request, assembles target context, asks only high-value clarifying questions, launches structured design branches, and returns a ranked package of candidates with rationale and provenance.

## Supported scope

Supported in v0:

- protein binder design
- protein targets only
- scientist-facing chat or CLI interaction
- structured campaign specs
- target dossier assembly
- hypothesis generation
- tool routing
- traceable execution
- ranked reports

Not supported in v0:

- broad "all protein engineering" workflows
- uncontrolled online learning from each run
- opaque one-shot answers with no trace or provenance
- treating prompt text as a replacement for scientific execution
- automatic production use of newly discovered tools without evaluation

## Responsibility split

### PicoClaw responsibilities

PicoClaw is the interaction and orchestration layer.

It is responsible for:

- receiving user requests
- applying workspace behavior rules
- gathering high-value clarifications
- assembling structured context
- calling local scripts and external APIs
- coordinating workflow steps
- generating concise user-facing summaries
- writing structured files into the workspace

### Responsibilities outside PicoClaw

The following responsibilities must be implemented in scripts, adapters, or services outside the prompt shell:

- target retrieval and normalization
- literature retrieval and caching
- scientific tool adapters
- tool registry and routing policy
- GPU job execution
- trace persistence
- ranking and scoring engines
- benchmark evaluation
- offline learning pipelines

If any of these are simulated temporarily, that simulation must be labeled explicitly.

## Execution modes

Clawd v0 supports two execution modes:

- `academic`
- `commercial_safe`

Execution mode affects which tools may be routed.

### Academic mode

- May use tools with academic or non-commercial restrictions if the route is otherwise valid.
- Must still record the license assumption in campaign outputs.

### Commercial-safe mode

- Must exclude tools whose terms are not acceptable for commercial-safe execution.
- Must fail or reroute explicitly when a restricted tool would otherwise have been selected.

## License-aware routing rule

AlphaFold 3 family usage and similar restricted tools must be license-gated.

This is not optional.

- Restricted tools must not be routed in `commercial_safe` mode.
- If a candidate result was produced with a restricted tool, that fact must be visible in provenance.
- Route selection must include the execution mode as an input.

## Required artifacts per run

Every meaningful campaign run must produce these artifacts:

- a human-readable summary report
- a machine-readable campaign spec
- candidate records
- trace events
- a provenance manifest

Recommended workspace paths:

```text
artifacts/campaigns/<campaign_id>/
  campaign-spec.json
  report.md
  candidates/
  trace/
  provenance/
```

## Required behavior standards

- Every meaningful external datum must have provenance.
- Every meaningful tool invocation must be reconstructable.
- Every major routing decision must be explainable.
- User-visible rationale must be tied to evidence and scores.
- Missing data and blocked tools must be called out explicitly.

## Non-goals

Clawd v0 is not:

- a generic autonomous scientist
- a pure LLM answer bot
- a production assay system
- a substitute for license review
- a substitute for human scientific judgment

## Acceptance criteria

This contract is successful when:

- a new engineer can understand the v0 boundary quickly
- there is no ambiguity about what belongs in PicoClaw versus backend code
- execution mode and license handling are explicit
- outputs and responsibilities are concrete enough to guide implementation
