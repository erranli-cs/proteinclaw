# USER.md

This file defines the expected user-facing workflow for PicoClaw in this workspace.

## Primary workflow

When the user asks for a design campaign:

1. restate the design goal in one sentence
2. resolve only high-value clarifications
3. invoke the allowed local tools, scripts, and external APIs directly
4. write the campaign artifacts into the workspace
5. return the campaign directory, report path, and run log path

## Required execution path

For substantive campaign runs, PicoClaw should orchestrate the workflow itself.

Optional flags:

- `--execution-mode academic`
- `--execution-mode commercial_safe`
- `--epitope "..."`
- `--modality "..."`
- `--use-fixture`

Useful helper entrypoints may include:

```bash
python3 -m proteinclaw plan --prompt "<user prompt>" --root .
```

and repo-local scripts under `scripts/`.

Do not treat one wrapper command as the required workflow. PicoClaw should decide which tools to run, inspect their outputs, and assemble the final response honestly.

## User-visible outputs

After a substantive run, always surface:

- `artifacts/campaigns/<campaign_id>/report.md`
- `artifacts/campaigns/<campaign_id>/run_log.md`
- `artifacts/campaigns/<campaign_id>/tool-invocations.json`

If the run is still queued remotely, say so explicitly and provide the live `run_log.md` path.
If a required tool failed, say so explicitly and point to the trace or invocation record.

## Clarification defaults

- execution mode: `academic`
- modality: infer from prompt if possible, otherwise `open modality`
- epitope: `open exploration` unless the planner identifies a stronger target-specific interface

## Failure handling

- If PicoClaw is not installed, that is not a blocker for backend development.
- If Tamarind is queued, do not claim the campaign finished.
- If Anthropic planning fails, continue with deterministic planning and log the failure.
