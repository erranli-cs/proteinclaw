# proteinclaw

Minimal MVP scaffold for Clawd, an auditable protein-design copilot.

This branch does not run real scientific design tools yet. It does run a traceable end-to-end campaign flow that:

- parses a natural-language binder-design prompt
- builds a target dossier
- generates hypotheses
- applies license-aware routing
- creates mock candidate records
- ranks candidates
- writes a reproducible artifact package

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
  --execution-mode commercial_safe \
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
