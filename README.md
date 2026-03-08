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
- uses a versioned tool registry and honest adapter fallback behavior

## PicoClaw

This repo is now PicoClaw-ready.

PicoClaw should use the workspace files:

- [AGENTS.md](/Users/daanishhindustano/Documents/projects/proteinclaw/AGENTS.md)
- [TOOLS.md](/Users/daanishhindustano/Documents/projects/proteinclaw/TOOLS.md)
- [HEARTBEAT.md](/Users/daanishhindustano/Documents/projects/proteinclaw/HEARTBEAT.md)
- [USER.md](/Users/daanishhindustano/Documents/projects/proteinclaw/USER.md)

and call the wrapper:

```bash
./scripts/run_picoclaw_campaign.sh --prompt "Design me a protein binder that inhibits HER2"
```

See [picoclaw.md](/Users/daanishhindustano/Documents/projects/proteinclaw/docs/runbooks/picoclaw.md) for the intended interaction model.

## Run

Verify the workspace contract:

```bash
./scripts/verify_workspace.sh
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
