#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require_file() {
  local file="$1"
  if [[ ! -f "$repo_root/$file" ]]; then
    echo "Missing required file: $file" >&2
    exit 1
  fi
}

require_heading() {
  local file="$1"
  local pattern="$2"
  if ! rg -q "$pattern" "$repo_root/$file"; then
    echo "Missing required content in $file: $pattern" >&2
    exit 1
  fi
}

require_file "AGENT.md"
require_file "AGENTS.md"
require_file "USER.md"
require_file "TASK.md"
require_file "TOOLS.md"
require_file "HEARTBEAT.md"
require_file "docs/specs/v0-system-contract.md"
require_file "docs/specs/workspace-contract.md"
require_file "docs/runbooks/picoclaw.md"

require_heading "TASK.md" "^## Task 0: Bootstrap the repository contract"
require_heading "TASK.md" "^## Task 1: Define the product boundary and system contract"
require_heading "TASK.md" "^## Task 2: Create the PicoClaw workspace contract"
require_heading "AGENTS.md" "^## User input policy"
require_heading "AGENTS.md" "^## Execution modes"
require_heading "USER.md" "^## Primary workflow"
require_heading "USER.md" "^## Required execution path"
require_heading "TOOLS.md" "^## Tool classes"
require_heading "HEARTBEAT.md" "^## Recurring responsibilities"
require_heading "docs/specs/v0-system-contract.md" "^## Responsibility split"
require_heading "docs/specs/v0-system-contract.md" "^## Execution modes"
require_heading "docs/specs/workspace-contract.md" "^## Working directory layout"
require_heading "docs/runbooks/picoclaw.md" "^## Recommended PicoClaw usage"

echo "Workspace contract verification passed."
