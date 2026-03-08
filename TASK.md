# Clawd Build Tasks

This file turns the current product requirements into an implementation backlog for a first working system.

Assumptions baked into these tasks:

- PicoClaw is the user-facing agent shell and orchestration surface.
- External tools, scripts, or services perform scientific retrieval, scoring, and design execution.
- Security restrictions in PicoClaw may be relaxed for this project, but every tool invocation must still be explicit and auditable.
- Anthropic Opus API may be used as the main planning and reasoning model.
- The initial product scope is protein binder design against protein targets.
- The first vertical slice should optimize for reproducibility, traceability, and tool routing, not broad biology coverage.

## Task 1: Define the product boundary and system contract

### Goal
Write a short architecture spec that freezes what Clawd is and is not for v0.

### Requirements

- Define PicoClaw's role as the interaction and orchestration layer.
- Define which responsibilities belong outside PicoClaw:
  - target retrieval
  - literature retrieval
  - tool routing policy
  - GPU job execution
  - trace persistence
  - ranking
- Define the supported v0 campaign type as protein binder design against protein targets only.
- Define the two execution modes:
  - `academic`
  - `commercial_safe`
- State clearly that AlphaFold 3 family usage must be license-gated.
- State the required artifacts for every run:
  - human-readable summary
  - machine-readable campaign spec
  - candidate records
  - trace events
  - provenance manifest

### Success criteria

- A new engineer can read one document and understand the v0 boundary in under 10 minutes.
- There is no ambiguity about whether a feature belongs in PicoClaw prompts, local scripts, or backend services.
- The document includes explicit non-goals to prevent scope creep.

## Task 2: Create the PicoClaw workspace contract

### Goal
Set up the workspace files that control agent behavior, tools, memory, and recurring research actions.

### Requirements

- Create an `AGENTS.md` tailored to Clawd.
- Create a `TOOLS.md` that lists each allowed tool, input shape, output shape, and failure behavior.
- Define how PicoClaw should ask for user input:
  - only at high-value branch points
  - never for low-value confirmations
  - always with explicit decision impact
- Define the expected working directory layout for artifacts, traces, dossiers, and reports.
- Define the minimum memory policy:
  - what may be persisted between campaigns
  - what must remain campaign-local
- Define a `HEARTBEAT.md` workflow for literature scouting and tool-watch tasks.

### Success criteria

- PicoClaw can run in this repo with behavior that is constrained by project files instead of ad hoc prompting.
- Another engineer can inspect the workspace and know how the agent is expected to behave.
- User clarification behavior is deterministic enough to test.

## Task 3: Specify the core data model

### Goal
Define the schemas that all components must exchange.

### Requirements

- Write versioned JSON schemas for:
  - `CampaignSpec`
  - `TargetDossier`
  - `HypothesisRecord`
  - `CandidateRecord`
  - `TraceEvent`
  - `ToolInvocationRecord`
  - `FinalReportManifest`
- Add required fields for:
  - IDs
  - timestamps
  - source provenance
  - license mode
  - model/tool version
  - failure codes
- Make the schemas strict enough that missing provenance or invalid tool outputs fail validation.
- Include schema examples for a HER2 binder campaign.

### Success criteria

- A candidate or trace record can be validated mechanically.
- The schemas are sufficient to reconstruct why a candidate was retained or rejected.
- Tool adapters can be implemented without inventing new fields ad hoc.

## Task 4: Build the target dossier pipeline

### Goal
Create the first reliable research pipeline that turns a target name or accession into a normalized dossier.

### Requirements

- Resolve user targets to canonical identifiers.
- Retrieve and normalize at minimum:
  - UniProt entry
  - PDB structures and complexes
  - domain annotations
  - PTMs and glycosylation notes
  - isoforms if relevant
  - target accessibility notes
- Add literature retrieval for:
  - known epitopes
  - therapeutic exemplars
  - mechanism-relevant structural context
- Store provenance for every external datum.
- Cache fetched records.
- Return a structured `TargetDossier` object plus a concise scientist-facing summary.

### Success criteria

- Running the pipeline on HER2 produces a dossier with canonical target metadata and source links.
- The output is reproducible and cached.
- Missing sources degrade gracefully instead of crashing the run.

## Task 5: Implement clarification and campaign-spec generation

### Goal
Turn free text into a machine-readable campaign spec with only high-value user interruptions.

### Requirements

- Use Opus to parse user intent into a preliminary `CampaignSpec`.
- Detect ambiguities that materially change search space:
  - target state
  - epitope
  - modality
  - commercial-safe vs academic
  - size and expression constraints
- Ask follow-up questions only when uncertainty has high downstream cost.
- Record all clarifications as trace events.
- Emit a finalized `CampaignSpec` after clarification.

### Success criteria

- A prompt like "design me a protein binder that inhibits HER2" produces a valid `CampaignSpec`.
- The system asks fewer than five follow-up questions for standard binder-design prompts.
- Every asked question can be justified by a documented decision impact.

## Task 6: Build the hypothesis generation module

### Goal
Generate distinct mechanistic design branches instead of a single generic run.

### Requirements

- Produce 3 to 7 hypotheses per campaign by default.
- For each hypothesis, define:
  - objective
  - region of interest
  - exclusion zones
  - scaffold bias
  - validation metrics
  - stop criteria
- Prevent duplicate or weakly differentiated hypotheses.
- Tie each hypothesis to dossier evidence and explicit assumptions.
- Persist hypotheses before any heavy design job starts.

### Success criteria

- HER2 prompts produce materially distinct branches such as epitope competition, blockade, or avidity-based concepts.
- Every branch has enough structure to route tools independently.
- Scientists can inspect the hypotheses and understand the reasoning without reading raw model monologue.

## Task 7: Build the tool registry and routing policy

### Goal
Create the logic that decides which scientific tools are allowed and preferred per branch.

### Requirements

- Add registry entries for the first tool set:
  - RFD3
  - BindCraft
  - ProteinMPNN
  - LigandMPNN
  - RF3
  - Chai-1
  - Boltz
  - OpenFold3-preview
- For each tool, capture:
  - supported task types
  - input contract
  - output contract
  - compute footprint
  - maturity
  - deployment method
  - license restrictions
  - known strengths and weaknesses
- Implement routing rules that honor execution mode:
  - `academic`
  - `commercial_safe`
- Make routing decisions explicit in trace records.

### Success criteria

- A branch can be routed without human intervention when tool availability and license mode are known.
- AF3-like restricted tools are automatically excluded in `commercial_safe` mode.
- Routing failures are visible and explainable.

## Task 8: Build the tool adapter layer

### Goal
Wrap external tools behind stable interfaces so PicoClaw does not need tool-specific prompting logic.

### Requirements

- Define a standard adapter contract:
  - input validation
  - execution
  - output normalization
  - error mapping
  - provenance capture
- Implement stub or real adapters for the first supported tool set.
- Ensure adapters can run through local commands, containers, or remote services.
- Return normalized artifacts and machine-readable result summaries.
- Record tool versions, command invocations, and execution timestamps.

### Success criteria

- The planner can call any registered tool through one interface.
- Tool-specific failure modes map to stable reason codes.
- Adapters are testable independently from PicoClaw.

## Task 9: Build the trace store and artifact layout

### Goal
Persist enough information to audit, rerun, and learn from campaigns.

### Requirements

- Define storage for:
  - campaign metadata
  - dossier snapshots
  - hypotheses
  - tool invocations
  - candidate lineage
  - rejection reasons
  - final rankings
  - user clarifications
- Define where large artifacts live versus structured metadata.
- Add immutable IDs and timestamps to all traceable entities.
- Make every external lookup and tool call recoverable from stored records.
- Support campaign export as a portable archive.

### Success criteria

- A past campaign can be inspected without replaying live external calls.
- A candidate's lineage from prompt to final ranking can be reconstructed mechanically.
- Missing provenance becomes a detectable defect rather than silent data loss.

## Task 10: Implement the first evaluation and ranking engine

### Goal
Rank candidates using structured metrics, disagreement handling, and task-specific weights.

### Requirements

- Support score dimensions for at least:
  - complex confidence
  - monomer confidence
  - interface quality
  - hotspot agreement
  - epitope correctness
  - developability
  - diversity
  - off-target risk
- Keep raw component scores and weighted scores separate.
- Expose Pareto-front style outputs in addition to a single ranking.
- Penalize disagreement across structurally distinct evaluators.
- Explain each top candidate's ranking with structured rationale.

### Success criteria

- The ranking can be recomputed deterministically from stored inputs.
- Near-miss candidates can be compared to winners with explicit reasons.
- Score weights are editable per campaign without code changes.

## Task 11: Build the user-facing report generator

### Goal
Convert traces and scores into output that a scientist can actually use.

### Requirements

- Generate a final report that includes:
  - campaign summary
  - target dossier summary
  - hypotheses tried
  - ranked candidates
  - per-candidate rationale
  - disagreement flags
  - recommended next experiments
  - provenance appendix
- Generate machine-readable artifacts alongside the report.
- Keep rationale tied to evidence and scores, not raw hidden reasoning.
- Highlight uncertainty and failure modes explicitly.

### Success criteria

- A scientist can review the final output and know what to test next.
- The report explains why top candidates outranked near-misses.
- The report can be generated without re-querying external systems.

## Task 12: Add literature scouting and tool-watch automation

### Goal
Continuously track new methods and tool changes without hard-coding the stack forever.

### Requirements

- Use PicoClaw scheduled tasks or heartbeat flows to scan:
  - PubMed / Europe PMC
  - bioRxiv / arXiv
  - GitHub repositories
  - model cards and release notes
- Classify findings by:
  - design generation
  - structure prediction
  - scoring
  - developability
  - mutational effect
- Record:
  - claimed strengths
  - license terms
  - code availability
  - benchmark claims
- Create a review queue for manual registry admission.

### Success criteria

- The system produces a structured queue of candidate tools rather than random notes.
- New tools are not automatically trusted or enabled.
- License and reproducibility checks are part of the intake path.

## Task 13: Add benchmark and regression evaluation

### Goal
Prevent silent degradation in planning, routing, and ranking.

### Requirements

- Define a small internal benchmark set for binder-design tasks.
- Add regression checks for:
  - target resolution
  - clarification policy
  - hypothesis diversity
  - routing correctness
  - report completeness
- Add fixture-based tests for HER2 and at least one additional target.
- Add acceptance tests for `academic` and `commercial_safe` mode differences.

### Success criteria

- Changes to prompts, routing logic, or schemas can be tested before release.
- License mode regressions are caught automatically.
- The system can show whether it is getting better or just changing.

## Task 14: Define the offline learning pipeline

### Goal
Prepare for learning from campaigns without unsafe online self-modification.

### Requirements

- Define which signals are stored for future learning:
  - user preferences
  - accepted candidates
  - rejected candidates
  - assay outcomes
  - clarification usefulness
  - tool route success
- Separate observational analytics from policy-changing model updates.
- Define dataset extraction rules from the trace store.
- Define promotion criteria for updated planner or ranking policies.

### Success criteria

- Historical data can be converted into training and evaluation datasets.
- No live campaign behavior changes automatically from unreviewed feedback.
- Policy updates are benchmark-gated and auditable.

## Task 15: Build the first end-to-end vertical slice

### Goal
Ship one working path from natural-language prompt to ranked HER2 binder campaign output.

### Requirements

- Support one end-to-end prompt:
  - "Design me a protein binder that inhibits HER2"
- Include:
  - prompt intake
  - dossier generation
  - clarification
  - hypothesis generation
  - tool routing
  - mock or real adapter execution
  - ranking
  - final report generation
- Prefer a narrow, working path over broad but fake coverage.
- Make all intermediate outputs inspectable.

### Success criteria

- A user can run one command or one PicoClaw workflow and get a reproducible campaign package.
- The result contains ranked candidates or clearly marked mock candidates if scientific tools are stubbed.
- The system demonstrates the actual architecture instead of only a prompt demo.

## Recommended build order

1. Task 1: Define the product boundary and system contract
2. Task 2: Create the PicoClaw workspace contract
3. Task 3: Specify the core data model
4. Task 4: Build the target dossier pipeline
5. Task 5: Implement clarification and campaign-spec generation
6. Task 6: Build the hypothesis generation module
7. Task 7: Build the tool registry and routing policy
8. Task 8: Build the tool adapter layer
9. Task 9: Build the trace store and artifact layout
10. Task 10: Implement the first evaluation and ranking engine
11. Task 11: Build the user-facing report generator
12. Task 15: Build the first end-to-end vertical slice
13. Task 12: Add literature scouting and tool-watch automation
14. Task 13: Add benchmark and regression evaluation
15. Task 14: Define the offline learning pipeline

## Notes

- Do not start with generalized protein engineering. That is how this gets bloated and stalls.
- Do not bury routing logic inside giant prompts. Put policy in data and code.
- Do not let unrestricted tool execution remove provenance requirements. Relaxed sandboxing is not an excuse for untraceable behavior.
- If the scientific tools are not ready, use stubs with honest labels. Fake confidence will make the system worse than useless.
