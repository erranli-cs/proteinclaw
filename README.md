# proteinclaw

Minimal MVP scaffold for Clawd, an auditable protein-design copilot.

This branch can submit the requested remote jobs through Tamarind when `TAMARIND` is configured:

- parses a natural-language binder-design prompt
- builds a target dossier
- generates hypotheses
- routes through `rfd3 -> ligandmpnn -> alphafold3`
- downloads tool outputs into the local campaign directory
- ranks candidates
- writes a reproducible artifact package
- supports interactive clarification capture
- prefers OpenAI planning when `OPENAI_API_KEY` is configured locally, with Anthropic fallback
- uses a versioned tool registry and honest adapter fallback behavior

## PicoClaw

This repo is now PicoClaw-ready.

PicoClaw should use the workspace files:

- [AGENTS.md](/Users/daanishhindustano/Documents/projects/proteinclaw/AGENTS.md)
- [TOOLS.md](/Users/daanishhindustano/Documents/projects/proteinclaw/TOOLS.md)
- [HEARTBEAT.md](/Users/daanishhindustano/Documents/projects/proteinclaw/HEARTBEAT.md)
- [USER.md](/Users/daanishhindustano/Documents/projects/proteinclaw/USER.md)

PicoClaw should orchestrate the workflow itself by reading those files, deciding which allowed tools to run, and writing campaign artifacts into the workspace.

Repo scripts and CLIs are helper entrypoints, not the required PicoClaw control plane.

See [picoclaw.md](/Users/daanishhindustano/Documents/projects/proteinclaw/docs/runbooks/picoclaw.md) for the intended interaction model.

## Run

Verify the workspace contract:

```bash
./scripts/verify_workspace.sh
```

Bootstrap the PicoClaw workspace locally:

```bash
./scripts/configure_picoclaw.sh
```

Launch a long-running campaign in the background for PicoClaw-friendly polling:

```bash
./scripts/start_picoclaw_campaign.sh \
  --prompt "Design a protein binder for PDB 4RWS around chain A residue 97" \
  --execution-mode academic
```

Check the latest campaign status:

```bash
./scripts/campaign_status.sh latest
```

Run the demo campaign:

```bash
./scripts/run_demo.sh
```

Or run the CLI directly:

```bash
python3 -m proteinclaw plan \
  --prompt "Design me a protein binder that inhibits HER2" \
  --execution-mode academic \
  --epitope "dimerization-relevant surface" \
  --modality "mini-binder" \
  --root .
```

Interactive clarification mode:

```bash
python3 -m proteinclaw plan \
  --prompt "Design me a protein binder that inhibits EGFR" \
  --interactive \
  --use-fixture \
  --root .
```

Write the heartbeat scouting queue:

```bash
python3 -m proteinclaw heartbeat --root .
```

Export the bootstrap learning dataset from stored campaign artifacts:

```bash
python3 -m proteinclaw export-learning --root .
```

## Test

```bash
./scripts/run_checks.sh
```
