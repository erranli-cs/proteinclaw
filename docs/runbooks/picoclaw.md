# PicoClaw Runbook

This repo is a PicoClaw workspace plus a local `proteinclaw` backend.

The intended split is simple:

- PicoClaw is the primary orchestrator.
- `proteinclaw` provides local helpers, schemas, and backend components PicoClaw may use.

## Current state

- The backend is runnable now.
- The workspace files PicoClaw expects now exist:
  - `AGENTS.md`
  - `TOOLS.md`
  - `HEARTBEAT.md`
  - `USER.md`
- PicoClaw itself is not installed in this repo.

## Recommended PicoClaw usage

Point PicoClaw at this repo as its workspace and have it:

1. read the workspace instruction files
2. gather only high-value clarifications
3. run the relevant tools directly
4. inspect outputs and failures
5. write the campaign artifacts under `artifacts/campaigns/<campaign_id>/`
6. return a concise summary plus artifact paths

Example:

```bash
python3 -m proteinclaw plan \
  --prompt "Please design a protein minibinder to TrkA using hotspot-guided RFdiffusion3, LigandMPNN, and AlphaFold3 scoring." \
  --execution-mode academic \
  --root .
```

This CLI is a helper entrypoint, not the definition of the PicoClaw workflow.

## What PicoClaw should return

After the workflow starts or finishes, PicoClaw should surface:

- the campaign directory
- `report.md`
- `run_log.md`
- whether the remote Tamarind job is queued, running, failed, or complete

## Why helper scripts exist

Helper scripts and CLIs keep repeated backend operations testable and reproducible.

They do not replace PicoClaw's job. PicoClaw should still choose the tools, run them, inspect outputs, and explain the result instead of blindly proxying one wrapper command.
