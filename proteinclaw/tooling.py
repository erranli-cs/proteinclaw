from __future__ import annotations

import json
import os
import subprocess
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from proteinclaw.tamarind import (
    TamarindError,
    download_result_archive,
    extract_result_archive,
    get_result_url,
    has_tamarind_key,
    submit_job,
    upload_file,
    wait_for_job,
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
    return ["rfd3", "ligandmpnn", "alphafold3"]


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


def _run_tamarind_job(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, workdir: Path) -> dict:
    spec = TOOL_REGISTRY[tool]
    output_dir = Path(inputs["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    job_name = stable_id(tool, f"{campaign_id}|{inputs.get('hypothesis_id', tool)}")
    settings = dict(inputs["settings"])

    try:
        upload_path = inputs.get("upload_path")
        if upload_path:
            folder = f"proteinclaw/{campaign_id}/{inputs.get('hypothesis_id', tool)}"
            uploaded = upload_file(workdir, Path(upload_path), folder)
            file_key = inputs.get("file_setting_key")
            if file_key:
                settings[file_key] = uploaded["storagePath"]
        submit_job(workdir, job_name, spec.remote_type or tool, settings)
        wait_for_job(workdir, job_name)
        result_url = get_result_url(workdir, job_name)
        archive_path = output_dir / f"{job_name}.zip"
        download_result_archive(result_url, archive_path)
        extracted = extract_result_archive(archive_path, output_dir)
        outputs = {
            "job_name": job_name,
            "result_url": result_url,
            "archive_path": str(archive_path),
            "output_dir": str(output_dir),
            "downloaded_files": [str(path) for path in extracted],
        }
        return _invocation_record(campaign_id, tool, stage, mode, "pass", inputs, outputs, [])
    except TamarindError as exc:
        return _invocation_record(campaign_id, tool, stage, mode, "failed", inputs, {"output_dir": str(output_dir), "reason": str(exc)}, ["tamarind_error"])
    except urllib.error.URLError as exc:
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
        return _invocation_record(campaign_id, tool, stage, mode, "failed", inputs, {"output_dir": str(output_dir), "reason": str(exc)}, ["unexpected_error"])


def run_tool_adapter(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, workdir: Path) -> dict:
    spec = TOOL_REGISTRY[tool]
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
        return _run_tamarind_job(campaign_id, tool, stage, mode, inputs, workdir)

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
