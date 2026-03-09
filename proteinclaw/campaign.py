from __future__ import annotations

import re
from dataclasses import dataclass

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id


@dataclass(frozen=True)
class Clarification:
    key: str
    question: str
    decision_impact: str
    default: str


PDB_PATTERN = re.compile(r"\b(?:pdb\s+)?([0-9][A-Za-z0-9]{3})\b", re.IGNORECASE)
CHAIN_RESIDUE_PATTERN = re.compile(
    r"chain\s+([A-Za-z])(?:[^0-9A-Za-z]+res(?:idue)?\s+|\s+)(\d+)(?:[^A-Za-z]+(?:which\s+should\s+be|is|=)\s+(?:an?\s+)?)?([A-Za-z]+)?",
    re.IGNORECASE,
)


def _extract_pdb_target(prompt: str) -> tuple[str, str, str, dict] | None:
    for match in PDB_PATTERN.finditer(prompt):
        pdb_id = match.group(1).upper()
        if pdb_id in {"HER2", "EGFR", "TRKA"}:
            continue
        return (pdb_id, "unknown", f"PDB:{pdb_id}", {"source": "pdb", "pdb_id": pdb_id})
    return None


def _extract_residue_constraints(prompt: str) -> list[dict]:
    residue_name_map = {
        "asp": "ASP",
        "aspartic": "ASP",
        "aspartate": "ASP",
        "glu": "GLU",
        "glutamic": "GLU",
        "glutamate": "GLU",
        "lys": "LYS",
        "lysine": "LYS",
        "arg": "ARG",
        "arginine": "ARG",
        "his": "HIS",
        "histidine": "HIS",
    }
    constraints: list[dict] = []
    for match in CHAIN_RESIDUE_PATTERN.finditer(prompt):
        residue_hint = match.group(3) or ""
        constraints.append(
            {
                "chain": match.group(1).upper(),
                "residue_number": int(match.group(2)),
                "residue_name": residue_name_map.get(residue_hint.strip().lower()) if residue_hint else None,
            }
        )
    return constraints


def infer_target_name(prompt: str) -> tuple[str, str, str]:
    lowered = prompt.lower()
    if "her2" in lowered or "erbb2" in lowered:
        return ("HER2", "human", "P04626")
    if "egfr" in lowered or "erbb1" in lowered:
        return ("EGFR", "human", "P00533")
    if "trka" in lowered or "ntrk1" in lowered:
        return ("TrkA", "human", "P04629")
    pdb_target = _extract_pdb_target(prompt)
    if pdb_target:
        return pdb_target[:3]
    raise ValueError("Could not infer a supported target from the prompt.")


def build_campaign_spec(prompt: str, execution_mode: str = "academic") -> dict:
    target_name, species, identifier = infer_target_name(prompt)
    campaign_id = stable_id("campaign", f"{prompt}|{execution_mode}")
    lowered = prompt.lower()
    modality = "mini-binder" if "minibinder" in lowered or "mini binder" in lowered else "open"
    residue_constraints = _extract_residue_constraints(prompt)
    pdb_target = _extract_pdb_target(prompt)
    target = {
        "name": target_name,
        "species": species,
        "identifier": identifier,
    }
    if pdb_target:
        target["source"] = "pdb"
        target["pdb_id"] = pdb_target[3]["pdb_id"]
    spec = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "task_type": "protein_binder_design",
        "target": target,
        "mechanism_goal": "inhibit",
        "design_space": {
            "modality": modality,
            "epitope": None,
            "oligomeric_state": "unspecified",
        },
        "constraints": {
            "max_length": 120,
            "glycan_avoidance": True,
            "commercial_safe": execution_mode == "commercial_safe",
            "target_residue_constraints": residue_constraints,
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


def resolve_clarifications(spec: dict, interactive: bool = False, answers: dict[str, str] | None = None) -> tuple[dict[str, str], list[dict]]:
    answers = dict(answers or {})
    resolved: list[dict] = []
    for item in required_clarifications(spec):
        value = answers.get(item.key)
        if value is None and interactive:
            prompt = f"{item.question} [{item.default}]: "
            response = input(prompt).strip()
            value = response or item.default
        if value is None:
            value = item.default
        answers[item.key] = value
        resolved.append(
            {
                "key": item.key,
                "value": value,
                "decision_impact": item.decision_impact,
                "default_applied": value == item.default,
            }
        )
    return answers, resolved


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
