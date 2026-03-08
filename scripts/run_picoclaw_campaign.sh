#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ $# -eq 0 ]]; then
  echo "usage: ./scripts/run_picoclaw_campaign.sh --prompt \"<campaign prompt>\" [extra proteinclaw plan flags]" >&2
  exit 1
fi

python3 -m proteinclaw plan --root "$repo_root" "$@"
