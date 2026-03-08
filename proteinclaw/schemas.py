from __future__ import annotations

import json
from pathlib import Path


SCHEMA_VERSION = "2026-03-08"


SCHEMAS: dict[str, dict] = {
    "CampaignSpec": {
        "required": {
            "schema_version": str,
            "campaign_id": str,
            "task_type": str,
            "target": dict,
            "mechanism_goal": str,
            "design_space": dict,
            "constraints": dict,
            "budget": dict,
            "execution_mode": str,
        }
    },
    "TargetDossier": {
        "required": {
            "schema_version": str,
            "campaign_id": str,
            "target": dict,
            "summary": str,
            "sources": list,
            "annotations": dict,
            "structures": list,
            "literature": list,
            "warnings": list,
        }
    },
    "HypothesisRecord": {
        "required": {
            "schema_version": str,
            "hypothesis_id": str,
            "campaign_id": str,
            "name": str,
            "objective": str,
            "region_of_interest": str,
            "exclusion_zones": list,
            "scaffold_bias": str,
            "validation_metrics": list,
            "stop_criteria": list,
            "assumptions": list,
            "evidence_refs": list,
        }
    },
    "ToolInvocationRecord": {
        "required": {
            "schema_version": str,
            "invocation_id": str,
            "campaign_id": str,
            "tool": str,
            "stage": str,
            "status": str,
            "started_at": str,
            "completed_at": str,
            "mode": str,
            "inputs": dict,
            "outputs": dict,
            "failure_codes": list,
        }
    },
    "CandidateRecord": {
        "required": {
            "schema_version": str,
            "candidate_id": str,
            "campaign_id": str,
            "parent_hypothesis": str,
            "generator_route": list,
            "sequence": str,
            "scores": dict,
            "validation": dict,
            "rationale": dict,
            "provenance": dict,
        }
    },
    "TraceEvent": {
        "required": {
            "schema_version": str,
            "time": str,
            "campaign_id": str,
            "type": str,
            "object_id": str,
            "human_visible_summary": str,
            "details": dict,
        }
    },
    "FinalReportManifest": {
        "required": {
            "schema_version": str,
            "campaign_id": str,
            "report_path": str,
            "artifact_paths": dict,
            "top_candidates": list,
            "generated_at": str,
        }
    },
}


def validate_record(schema_name: str, record: dict) -> None:
    schema = SCHEMAS[schema_name]
    missing = [key for key in schema["required"] if key not in record]
    if missing:
        raise ValueError(f"{schema_name} missing required keys: {', '.join(missing)}")

    for key, expected_type in schema["required"].items():
        if not isinstance(record[key], expected_type):
            raise TypeError(
                f"{schema_name}.{key} expected {expected_type.__name__}, got {type(record[key]).__name__}"
            )

    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"{schema_name}.schema_version expected {SCHEMA_VERSION}, got {record['schema_version']}"
        )


def dump_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
