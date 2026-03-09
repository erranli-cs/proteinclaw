#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

target="${1:-latest}"
interval_seconds="${2:-30}"
model="${PICOCLAW_MODEL:-gpt-5.2}"
session_prefix="${PICOCLAW_SESSION_PREFIX:-proteinclaw-watch}"

resolve_campaign_id() {
  if [[ "$target" == "latest" ]]; then
    ./scripts/campaign_status.sh latest | awk -F= '/^campaign_id=/{print $2; exit}'
  else
    echo "$target"
  fi
}

campaign_id="$(resolve_campaign_id)"
if [[ -z "$campaign_id" ]]; then
  echo "could not resolve campaign id" >&2
  exit 1
fi

campaign_dir="$repo_root/artifacts/campaigns/$campaign_id"
watch_log="$campaign_dir/picoclaw-watch.log"
analysis_log="$campaign_dir/picoclaw-analysis.log"
analysis_marker="$campaign_dir/.picoclaw-analysis-triggered"
session_name="${session_prefix}-${campaign_id}"

mkdir -p "$campaign_dir"

echo "watching campaign_id=$campaign_id interval_seconds=$interval_seconds session=$session_name" | tee -a "$watch_log"

while true; do
  status_output="$(./scripts/campaign_status.sh "$campaign_id")"
  printf '[%s]\n%s\n\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$status_output" >>"$watch_log"

  report_status="$(printf '%s\n' "$status_output" | awk -F= '/^report_status=/{print $2; exit}')"
  tamarind_status="$(printf '%s\n' "$status_output" | awk -F= '/^tamarind_status=/{print $2; exit}')"
  run_log_path="$(printf '%s\n' "$status_output" | awk -F= '/^run_log=/{print $2; exit}')"
  report_path="$(printf '%s\n' "$status_output" | awk -F= '/^report_path=/{print $2; exit}')"
  tool_invocations_path="$(printf '%s\n' "$status_output" | awk -F= '/^tool_invocations_path=/{print $2; exit}')"

  if [[ ! -f "$analysis_marker" ]] && { [[ "$report_status" == "ready" ]] || [[ "$tamarind_status" == "Complete" ]]; }; then
    prompt="Check ./scripts/campaign_status.sh $campaign_id. Read $run_log_path"
    if [[ -n "$report_path" ]]; then
      prompt="$prompt, $report_path"
    fi
    if [[ -n "$tool_invocations_path" ]]; then
      prompt="$prompt, and $tool_invocations_path"
    fi
    prompt="$prompt. Analyze the campaign results honestly. If outputs are partial, say what is missing and what the current Tamarind status implies."

    {
      printf '[%s] triggering analysis\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      picoclaw agent -s "$session_name" --model "$model" -m "$prompt"
      touch "$analysis_marker"
      printf '[%s] analysis complete\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    } >>"$analysis_log" 2>&1 || true
  fi

  sleep "$interval_seconds"
done
