from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id, utc_now


@dataclass(frozen=True)
class ToolSpec:
    name: str
    stages: tuple[str, ...]
    commercial_safe: bool
    maturity: str
    strengths: tuple[str, ...]
    default_command: str | None


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "config" / "tool_registry.json"


def load_tool_registry() -> dict[str, ToolSpec]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {
        key: ToolSpec(
            name=value["name"],
            stages=tuple(value["stages"]),
            commercial_safe=bool(value["commercial_safe"]),
            maturity=value["maturity"],
            strengths=tuple(value["strengths"]),
            default_command=value["default_command"],
        )
        for key, value in payload.items()
    }


TOOL_REGISTRY = load_tool_registry()


def select_route(execution_mode: str, hypothesis: dict) -> list[str]:
    generation_tool = "bindcraft" if hypothesis["name"] == "therapeutic-epitope-competition" else "rfd3"
    sequence_tool = "proteinmpnn"
    validation_tools = ["rf3", "chai1"] if execution_mode == "commercial_safe" else ["alphafold3", "rf3"]

    route = [generation_tool, sequence_tool, *validation_tools]
    if execution_mode == "commercial_safe" and any(not TOOL_REGISTRY[tool].commercial_safe for tool in route):
        raise ValueError("Commercial-safe routing attempted to include a restricted tool.")
    return route


def _invocation_record(campaign_id: str, tool: str, stage: str, mode: str, status: str, inputs: dict, outputs: dict, failure_codes: list[str]) -> dict:
    record = {
        "schema_version": SCHEMA_VERSION,
        "invocation_id": stable_id("inv", f"{campaign_id}|{tool}|{stage}|{utc_now()}"),
        "campaign_id": campaign_id,
        "tool": tool,
        "stage": stage,
        "status": status,
        "started_at": utc_now(),
        "completed_at": utc_now(),
        "mode": mode,
        "inputs": inputs,
        "outputs": outputs,
        "failure_codes": failure_codes,
    }
    validate_record("ToolInvocationRecord", record)
    return record


def run_tool_adapter(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, workdir: Path) -> dict:
    spec = TOOL_REGISTRY[tool]
    env_key = f"PROTEINCLAW_{tool.upper().replace('-', '_')}_CMD"
    command = os.environ.get(env_key) or spec.default_command
    if mode == "commercial_safe" and not spec.commercial_safe:
        return _invocation_record(
            campaign_id,
            tool,
            stage,
            mode,
            "skipped",
            inputs,
            {"reason": "license_blocked"},
            ["license_blocked"],
        )
    if not command:
        return _invocation_record(
            campaign_id,
            tool,
            stage,
            mode,
            "mock",
            inputs,
            {"reason": "adapter_not_configured"},
            ["adapter_not_configured"],
        )
    completed = subprocess.run(
        command,
        shell=True,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return _invocation_record(
            campaign_id,
            tool,
            stage,
            mode,
            "failed",
            inputs,
            {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode},
            ["command_failed"],
        )
    return _invocation_record(
        campaign_id,
        tool,
        stage,
        mode,
        "pass",
        inputs,
        {"stdout": completed.stdout.strip(), "stderr": completed.stderr.strip(), "returncode": completed.returncode},
        [],
    )
