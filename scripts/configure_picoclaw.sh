#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$repo_root/scripts/verify_workspace.sh"

mkdir -p \
  "$repo_root/artifacts/campaigns" \
  "$repo_root/memory" \
  "$repo_root/state" \
  "$repo_root/sessions"

planning_provider="deterministic"
if [[ -f "$repo_root/.env" ]]; then
  if rg -q '^OPENAI_API_KEY=' "$repo_root/.env"; then
    planning_provider="openai"
  elif rg -q '^(ANTHROPIC_API_KEY|ANTHROPIC_KEY|Antropic)=' "$repo_root/.env"; then
    planning_provider="anthropic"
  fi
fi

cat <<EOF
PicoClaw workspace configured for:
  $repo_root

Verified:
  - workspace contract files are present
  - planning provider: $planning_provider

Prepared directories:
  - artifacts/campaigns
  - memory
  - state
  - sessions

Next steps:
  1. Point PicoClaw at this workspace root:
     $repo_root
  2. Use the workspace contract files:
     AGENTS.md, TOOLS.md, USER.md, HEARTBEAT.md
  3. Run a campaign helper if needed:
     ./scripts/run_picoclaw_campaign.sh --prompt "<campaign prompt>" --execution-mode academic
EOF
