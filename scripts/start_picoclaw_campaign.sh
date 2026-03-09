#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

prompt=""
execution_mode="academic"
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --prompt" >&2
        exit 1
      fi
      prompt="$2"
      args+=("$1" "$2")
      shift 2
      ;;
    --execution-mode)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --execution-mode" >&2
        exit 1
      fi
      execution_mode="$2"
      args+=("$1" "$2")
      shift 2
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$prompt" ]]; then
  echo 'usage: ./scripts/start_picoclaw_campaign.sh --prompt "<campaign prompt>" [extra proteinclaw plan flags]' >&2
  exit 1
fi

campaign_id="$(
  python3 - "$prompt" "$execution_mode" <<'PY'
from proteinclaw.campaign import build_campaign_spec
import sys

prompt = sys.argv[1]
execution_mode = sys.argv[2]
print(build_campaign_spec(prompt, execution_mode=execution_mode)["campaign_id"])
PY
)"

campaign_root="$repo_root/artifacts/campaigns/$campaign_id"
session_log="$campaign_root/session.log"
launch_meta="$campaign_root/launch.json"
run_log="$campaign_root/run_log.md"

mkdir -p "$campaign_root"

command=(python3 -m proteinclaw plan --root "$repo_root" "${args[@]}")
nohup "${command[@]}" >"$session_log" 2>&1 &
pid=$!

python3 - "$launch_meta" "$campaign_id" "$prompt" "$execution_mode" "$repo_root" "$session_log" "$pid" "${command[@]}" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

launch_meta = Path(sys.argv[1])
campaign_id = sys.argv[2]
prompt = sys.argv[3]
execution_mode = sys.argv[4]
repo_root = sys.argv[5]
session_log = sys.argv[6]
pid = int(sys.argv[7])
command = sys.argv[8:]

payload = {
    "campaign_id": campaign_id,
    "prompt": prompt,
    "execution_mode": execution_mode,
    "repo_root": repo_root,
    "session_log": session_log,
    "pid": pid,
    "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "command": command,
}
launch_meta.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

cat <<EOF
campaign_id=$campaign_id
campaign_dir=$campaign_root
run_log=$run_log
session_log=$session_log
pid=$pid
EOF
