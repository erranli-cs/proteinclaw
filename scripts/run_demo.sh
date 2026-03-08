#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m proteinclaw plan \
  --prompt "Design me a protein binder that inhibits HER2" \
  --execution-mode commercial_safe \
  --use-fixture \
  --root "$repo_root"
