from __future__ import annotations

from dataclasses import dataclass

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id, utc_now


@dataclass(frozen=True)
class ToolSpec:
    name: str
    stages: tuple[str, ...]
    commercial_safe: bool
    maturity: str
    strengths: tuple[str, ...]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "rfd3": ToolSpec("rfd3", ("generation",), True, "beta", ("backbone generation",)),
    "bindcraft": ToolSpec("bindcraft", ("generation",), True, "beta", ("automated binder baseline",)),
    "proteinmpnn": ToolSpec("proteinmpnn", ("sequence_design",), True, "stable", ("backbone-conditioned sequence design",)),
    "ligandmpnn": ToolSpec("ligandmpnn", ("sequence_design",), True, "beta", ("context-aware design",)),
    "rf3": ToolSpec("rf3", ("validation",), True, "beta", ("structure validation",)),
    "chai1": ToolSpec("chai1", ("validation",), True, "beta", ("alternative structure prediction",)),
    "boltz": ToolSpec("boltz", ("validation",), True, "beta", ("commercial-safe alternative",)),
    "openfold3-preview": ToolSpec("openfold3-preview", ("validation",), True, "preview", ("open alternative",)),
    "alphafold3": ToolSpec("alphafold3", ("validation",), False, "restricted", ("high-capability validation in academic mode",)),
}


def select_route(execution_mode: str, hypothesis: dict) -> list[str]:
    generation_tool = "bindcraft" if hypothesis["name"] == "therapeutic-epitope-competition" else "rfd3"
    sequence_tool = "proteinmpnn"
    validation_tools = ["rf3", "chai1"] if execution_mode == "commercial_safe" else ["alphafold3", "rf3"]

    route = [generation_tool, sequence_tool, *validation_tools]
    if execution_mode == "commercial_safe" and any(not TOOL_REGISTRY[tool].commercial_safe for tool in route):
        raise ValueError("Commercial-safe routing attempted to include a restricted tool.")
    return route


def mock_tool_invocation(campaign_id: str, tool: str, stage: str, mode: str, inputs: dict, outputs: dict) -> dict:
    record = {
        "schema_version": SCHEMA_VERSION,
        "invocation_id": stable_id("inv", f"{campaign_id}|{tool}|{stage}|{utc_now()}"),
        "campaign_id": campaign_id,
        "tool": tool,
        "stage": stage,
        "status": "pass",
        "started_at": utc_now(),
        "completed_at": utc_now(),
        "mode": mode,
        "inputs": inputs,
        "outputs": outputs,
        "failure_codes": [],
    }
    validate_record("ToolInvocationRecord", record)
    return record
