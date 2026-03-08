from __future__ import annotations

import json
import os
import subprocess
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from proteinclaw.tamarind import (
    TamarindError,
    has_tamarind_key,
    run_tamarind_job,
)
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
    provider: str | None
    remote_type: str | None


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
            provider=value.get("provider"),
            remote_type=value.get("remote_type"),
        )
        for key, value in payload.items()
    }


TOOL_REGISTRY = load_tool_registry()


def select_route(execution_mode: str, hypothesis: dict) -> list[str]:
    preferred_route = ["rfd3", "ligandmpnn", "alphafold3"]
    route: list[str] = []
    for tool in preferred_route:
        spec = TOOL_REGISTRY[tool]
        if execution_mode == "commercial_safe" and not spec.commercial_safe:
            continue
        route.append(tool)
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


def _is_quota_exceeded_error(message: str) -> bool:
    normalized = message.lower()
    return "monthly job limit exceeded" in normalized or "job limit exceeded" in normalized


def _write_mock_tool_outputs(tool: str, output_dir: Path, reason: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mock_files: list[Path] = []
    summary_path = output_dir / "mock-response.json"
    summary_path.write_text(
        json.dumps(
            {
                "tool": tool,
                "mock": True,
                "reason": reason,
                "generated_at": utc_now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    mock_files.append(summary_path)
    if tool == "ligandmpnn":
        fasta_path = output_dir / "mock_sequences.fa"
        fasta_path.write_text(
            ">mock_quota_placeholder\nACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY\n",
            encoding="utf-8",
        )
        mock_files.append(fasta_path)
    return [str(path) for path in mock_files]


def _run_tamarind_job(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, workdir: Path, logger=None) -> dict:
    spec = TOOL_REGISTRY[tool]
    output_dir = Path(inputs["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    job_name = stable_id(tool, f"{campaign_id}|{inputs.get('hypothesis_id', tool)}|{utc_now()}")

    try:
        folder = f"proteinclaw/{campaign_id}/{inputs.get('hypothesis_id', tool)}"
        outputs = run_tamarind_job(
            workdir,
            job_name,
            spec.remote_type or tool,
            inputs["settings"],
            output_dir,
            upload_path=Path(inputs["upload_path"]) if inputs.get("upload_path") else None,
            upload_folder=folder,
            file_setting_key=inputs.get("file_setting_key"),
            logger=(lambda message: logger(f"{tool}: {message}") if logger else None),
        )
        outputs.pop("settings", None)
        return _invocation_record(campaign_id, tool, stage, mode, "pass", inputs, outputs, [])
    except TamarindError as exc:
        if _is_quota_exceeded_error(str(exc)):
            if logger:
                logger(f"{tool}: quota exceeded, writing explicit mock outputs.")
            mock_files = _write_mock_tool_outputs(tool, output_dir, str(exc))
            return _invocation_record(
                campaign_id,
                tool,
                stage,
                mode,
                "mock",
                inputs,
                {
                    "output_dir": str(output_dir),
                    "reason": str(exc),
                    "mocked": True,
                    "downloaded_files": mock_files,
                },
                ["tamarind_quota_exceeded_mocked"],
            )
        if logger:
            logger(f"{tool}: Tamarind error `{exc}`.")
        return _invocation_record(campaign_id, tool, stage, mode, "failed", inputs, {"output_dir": str(output_dir), "reason": str(exc)}, ["tamarind_error"])
    except urllib.error.URLError as exc:
        if logger:
            logger(f"{tool}: transport error `{exc}`.")
        return _invocation_record(
            campaign_id,
            tool,
            stage,
            mode,
            "failed",
            inputs,
            {"output_dir": str(output_dir), "reason": str(exc)},
            ["tamarind_transport_error"],
        )
    except Exception as exc:
        if logger:
            logger(f"{tool}: unexpected error `{exc}`.")
        return _invocation_record(campaign_id, tool, stage, mode, "failed", inputs, {"output_dir": str(output_dir), "reason": str(exc)}, ["unexpected_error"])


def run_tool_adapter(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, workdir: Path, logger=None) -> dict:
    spec = TOOL_REGISTRY[tool]
    if mode == "commercial_safe" and not spec.commercial_safe:
        return _invocation_record(
            campaign_id,
            tool,
            stage,
            mode,
            "skipped",
            inputs,
            {"reason": "license_blocked", "output_dir": inputs.get("output_dir")},
            ["license_blocked"],
        )
    if spec.provider == "tamarind":
        if not has_tamarind_key(workdir):
            return _invocation_record(
                campaign_id,
                tool,
                stage,
                mode,
                "mock",
                inputs,
                {"reason": "missing_tamarind_api_key", "output_dir": inputs.get("output_dir")},
                ["missing_tamarind_api_key"],
            )
        return _run_tamarind_job(campaign_id, tool, stage, mode, inputs, workdir, logger=logger)

    env_key = f"PROTEINCLAW_{tool.upper().replace('-', '_')}_CMD"
    command = os.environ.get(env_key) or spec.default_command
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
