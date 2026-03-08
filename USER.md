# USER.md

This file defines the expected user-facing workflow for PicoClaw in this workspace.

## Primary workflow

When the user asks for a design campaign:

1. restate the design goal in one sentence
2. resolve only high-value clarifications
3. run the local wrapper script instead of reconstructing the pipeline in chat
4. return the campaign directory, report path, and run log path

## Required execution path

For substantive campaign runs, PicoClaw should call:

```bash
./scripts/run_picoclaw_campaign.sh --prompt "<user prompt>"
```

Optional flags:

- `--execution-mode academic`
- `--execution-mode commercial_safe`
- `--epitope "..."`
- `--modality "..."`
- `--use-fixture`

Do not bypass the wrapper by manually calling Tamarind or rewriting the route in chat unless debugging the backend.

## User-visible outputs

After a successful run, always surface:

- `artifacts/campaigns/<campaign_id>/report.md`
- `artifacts/campaigns/<campaign_id>/run_log.md`
- `artifacts/campaigns/<campaign_id>/tool-invocations.json`

If the run is still queued remotely, say so explicitly and provide the live `run_log.md` path.

## Clarification defaults

- execution mode: `academic`
- modality: infer from prompt if possible, otherwise `open modality`
- epitope: `open exploration` unless the planner identifies a stronger target-specific interface

## Failure handling

- If PicoClaw is not installed, that is not a blocker for backend development.
- If Tamarind is queued, do not claim the campaign finished.
- If Anthropic planning fails, continue with deterministic planning and log the failure.
