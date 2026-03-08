from __future__ import annotations

from dataclasses import dataclass

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id


@dataclass(frozen=True)
class Clarification:
    key: str
    question: str
    decision_impact: str
    default: str


def infer_target_name(prompt: str) -> tuple[str, str, str]:
    lowered = prompt.lower()
    if "her2" in lowered or "erbb2" in lowered:
        return ("HER2", "human", "P04626")
    raise ValueError("Could not infer a supported target from the prompt.")


def build_campaign_spec(prompt: str, execution_mode: str = "academic") -> dict:
    target_name, species, identifier = infer_target_name(prompt)
    campaign_id = stable_id("campaign", f"{prompt}|{execution_mode}")
    spec = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "task_type": "protein_binder_design",
        "target": {
            "name": target_name,
            "species": species,
            "identifier": identifier,
        },
        "mechanism_goal": "inhibit",
        "design_space": {
            "modality": "open",
            "epitope": None,
            "oligomeric_state": "unspecified",
        },
        "constraints": {
            "max_length": 120,
            "glycan_avoidance": True,
            "commercial_safe": execution_mode == "commercial_safe",
        },
        "budget": {
            "gpu_hours": 50,
            "max_candidates": 24,
        },
        "execution_mode": execution_mode,
    }
    validate_record("CampaignSpec", spec)
    return spec


def required_clarifications(spec: dict) -> list[Clarification]:
    questions: list[Clarification] = []
    if spec["design_space"]["epitope"] is None:
        questions.append(
            Clarification(
                key="epitope",
                question="Should this target a known therapeutic epitope, a dimerization-relevant surface, or remain open exploration?",
                decision_impact="This changes the search space and routing constraints.",
                default="open exploration",
            )
        )
    if spec["design_space"]["modality"] == "open":
        questions.append(
            Clarification(
                key="modality",
                question="Do you want a mini-binder, repeat protein, peptide, or open modality?",
                decision_impact="This changes scaffold selection and candidate filtering.",
                default="open modality",
            )
        )
    return questions


def apply_clarifications(spec: dict, answers: dict[str, str] | None = None) -> dict:
    answers = answers or {}
    updated = {
        **spec,
        "design_space": dict(spec["design_space"]),
    }
    if "epitope" in answers:
        updated["design_space"]["epitope"] = answers["epitope"]
    if "modality" in answers and answers["modality"] != "open modality":
        updated["design_space"]["modality"] = answers["modality"]
    validate_record("CampaignSpec", updated)
    return updated
