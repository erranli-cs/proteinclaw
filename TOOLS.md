# TOOLS.md

This file defines the allowed tool surface for the PicoClaw workspace.

The goal is not to list every possible command. The goal is to constrain the agent to explicit classes of actions and force structured handling of failures.

## General rules

- Prefer repo scripts over ad hoc one-off shell commands when logic is reusable.
- Record provenance for every external datum used in a campaign artifact.
- Record major tool invocations in campaign traces once the trace layer exists.
- Never hide a routing or fallback decision.
- If a tool is unavailable, report the failure and whether the workflow can continue honestly.

## Tool classes

### Shell commands

Allowed use:

- file inspection
- repo maintenance
- running local scripts
- running tests
- preparing structured artifacts

Input shape:

- command string
- working directory
- explicit environment assumptions when relevant

Output shape:

- stdout or stderr
- exit code
- files created or updated

Failure behavior:

- non-zero exit codes must be surfaced
- partial outputs must not be treated as complete success

### Web and literature retrieval

Allowed use:

- target research
- structure and annotation lookup
- literature scouting
- license and release-note verification

Input shape:

- target identifier, paper query, or repository query

Output shape:

- structured notes with source identifiers or URLs
- retrieval date or timestamp

Failure behavior:

- missing or conflicting sources must be reported
- unverified claims must be labeled as such

### Local project scripts

Allowed use:

- dossier building
- schema validation
- report generation
- benchmark and regression checks

Input shape:

- documented CLI arguments or config files

Output shape:

- machine-readable files
- logs
- exit code

Failure behavior:

- scripts must fail loudly on invalid inputs
- schema or provenance violations must stop the run unless explicitly handled

### External scientific tools

Allowed use:

- structure generation
- sequence design
- structure prediction
- validation and scoring

Input shape:

- normalized records produced by adapters, not ad hoc prompt fragments

Output shape:

- normalized result payloads
- artifact paths
- tool metadata including version

Failure behavior:

- adapter must map tool-specific failure into stable reason codes
- license-restricted tools must be blocked in incompatible execution modes

### LLM APIs

Allowed use:

- prompt interpretation
- clarification drafting
- hypothesis generation
- report summarization

Current planning default:

- Anthropic Opus API

Input shape:

- structured context
- explicit task instruction
- relevant constraints and mode

Output shape:

- machine-readable records where possible
- concise summaries otherwise

Failure behavior:

- model output must not bypass schema validation
- unsupported scientific claims must not be upgraded to facts

## User input policy

Ask for user input only when:

- the answer changes execution mode
- the answer changes target state or epitope
- the answer changes modality or hard constraints
- the cost of defaulting is high

When asking:

- ask one compact question at a time when possible
- state the decision impact directly
- offer a safe default if one exists

## Current expected tool inventory

This repo will eventually wrap tools such as:

- UniProt retrieval
- PDB retrieval
- literature search
- RFD3
- BindCraft
- ProteinMPNN
- LigandMPNN
- RF3
- Chai-1
- Boltz
- OpenFold3-preview

Do not claim any of these are fully integrated until adapters and tests exist.
