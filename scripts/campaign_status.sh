#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

target="${1:-latest}"

python3 - "$repo_root" "$target" <<'PY'
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
target = sys.argv[2]
campaigns_root = repo_root / "artifacts" / "campaigns"

if target == "latest":
    campaign_dirs = [path for path in campaigns_root.iterdir() if path.is_dir()]
    if not campaign_dirs:
        raise SystemExit("no campaigns found")
    campaign_root = max(campaign_dirs, key=lambda path: path.stat().st_mtime)
else:
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = repo_root / "artifacts" / "campaigns" / target
    campaign_root = candidate

if not campaign_root.exists():
    raise SystemExit(f"campaign path does not exist: {campaign_root}")

launch_path = campaign_root / "launch.json"
report_path = campaign_root / "report.md"
run_log_path = campaign_root / "run_log.md"
tool_invocations_path = campaign_root / "tool-invocations.json"

pid = None
process_state = "unknown"
if launch_path.exists():
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    pid = launch.get("pid")
    if isinstance(pid, int):
        try:
            os.kill(pid, 0)
        except OSError:
            process_state = "exited"
        else:
            process_state = "running"

tamarind_status = "none"
tamarind_job = None
if run_log_path.exists():
    run_log = run_log_path.read_text(encoding="utf-8", errors="ignore")
    job_matches = re.findall(r"Tamarind job `([^`]+)`", run_log)
    status_matches = re.findall(r"Tamarind status for `([^`]+)` -> ([^.]+)\.", run_log)
    if status_matches:
        tamarind_job, tamarind_status = status_matches[-1]
    elif job_matches:
        tamarind_job = job_matches[-1]
        tamarind_status = "submitted"

report_status = "ready" if report_path.exists() else "pending"
tool_invocation_status = "ready" if tool_invocations_path.exists() else "pending"

lines = [
    f"campaign_id={campaign_root.name}",
    f"campaign_dir={campaign_root}",
    f"process_state={process_state}",
    f"report_status={report_status}",
    f"run_log={run_log_path}",
    f"tool_invocations_status={tool_invocation_status}",
]
if pid is not None:
    lines.append(f"pid={pid}")
if tamarind_job:
    lines.append(f"tamarind_job={tamarind_job}")
lines.append(f"tamarind_status={tamarind_status}")
if report_path.exists():
    lines.append(f"report_path={report_path}")
if tool_invocations_path.exists():
    lines.append(f"tool_invocations_path={tool_invocations_path}")

print("\n".join(lines))
PY
