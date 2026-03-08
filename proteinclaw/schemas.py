from __future__ import annotations

import json
from pathlib import Path


SCHEMA_VERSION = "2026-03-08"


TYPE_MAP = {
    "string": str,
    "object": dict,
    "array": list,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
SCHEMA_PATHS = {
    "CampaignSpec": SCHEMA_DIR / "CampaignSpec.schema.json",
    "TargetDossier": SCHEMA_DIR / "TargetDossier.schema.json",
    "HypothesisRecord": SCHEMA_DIR / "HypothesisRecord.schema.json",
    "ToolInvocationRecord": SCHEMA_DIR / "ToolInvocationRecord.schema.json",
    "CandidateRecord": SCHEMA_DIR / "CandidateRecord.schema.json",
    "TraceEvent": SCHEMA_DIR / "TraceEvent.schema.json",
    "FinalReportManifest": SCHEMA_DIR / "FinalReportManifest.schema.json",
}


def load_schema(schema_name: str) -> dict:
    return json.loads(SCHEMA_PATHS[schema_name].read_text(encoding="utf-8"))


def _validate_node(schema: dict, value: object, path: str) -> None:
    expected_type = schema.get("type")
    if expected_type:
        if not isinstance(value, TYPE_MAP[expected_type]):
            raise TypeError(f"{path} expected {expected_type}, got {type(value).__name__}")

    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path} expected const value {schema['const']}, got {value}")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} expected one of {schema['enum']}, got {value}")

    if expected_type == "object":
        value = dict(value)
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = [key for key in value if key not in properties]
            if extras:
                raise ValueError(f"{path} contains unexpected keys: {', '.join(extras)}")

        for key, child_schema in properties.items():
            if key in value:
                _validate_node(child_schema, value[key], f"{path}.{key}")

    if expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_node(item_schema, item, f"{path}[{index}]")


def validate_record(schema_name: str, record: dict) -> None:
    _validate_node(load_schema(schema_name), record, schema_name)


def dump_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
