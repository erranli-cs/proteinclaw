# PicoClaw Runbook

This repo is a PicoClaw workspace plus a local `proteinclaw` backend.

The intended split is simple:

- PicoClaw handles user interaction, clarification, and tool use.
- `proteinclaw` handles the actual campaign pipeline.

## Current state

- The backend is runnable now.
- The workspace files PicoClaw expects now exist:
  - `AGENTS.md`
  - `TOOLS.md`
  - `HEARTBEAT.md`
  - `USER.md`
- PicoClaw itself is not installed in this repo.

## Recommended PicoClaw usage

Point PicoClaw at this repo as its workspace and have it call:

```bash
./scripts/run_picoclaw_campaign.sh --prompt "<user prompt>"
```

Example:

```bash
./scripts/run_picoclaw_campaign.sh \
  --prompt "Please design a protein minibinder to TrkA using hotspot-guided RFdiffusion3, LigandMPNN, and AlphaFold3 scoring." \
  --execution-mode academic
```

## What PicoClaw should return

After the command starts or finishes, PicoClaw should surface:

- the campaign directory
- `report.md`
- `run_log.md`
- whether the remote Tamarind job is queued, running, failed, or complete

## Why this wrapper exists

Without the wrapper, PicoClaw would tend to reimplement the CLI behavior in chat and drift away from the tested pipeline. That is brittle and unnecessary.
