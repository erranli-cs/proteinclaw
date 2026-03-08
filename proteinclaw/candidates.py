from __future__ import annotations

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id


def _candidate_sequence(seed: str) -> str:
    alphabet = "ACDEFGHIKLMNPQRSTVWY"
    return "".join(alphabet[(idx + len(seed)) % len(alphabet)] for idx in range(60))


def build_candidates(spec: dict, hypotheses: list[dict], routes: dict[str, list[str]]) -> list[dict]:
    candidates: list[dict] = []
    for index, hypothesis in enumerate(hypotheses, start=1):
        route = routes[hypothesis["hypothesis_id"]]
        candidate = {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": stable_id("cand", f"{spec['campaign_id']}|{hypothesis['hypothesis_id']}"),
            "campaign_id": spec["campaign_id"],
            "parent_hypothesis": hypothesis["hypothesis_id"],
            "generator_route": route[:2],
            "sequence": _candidate_sequence(hypothesis["name"]),
            "scores": {
                "complex_confidence": round(0.78 - (index * 0.03), 2),
                "monomer_confidence": round(0.82 - (index * 0.02), 2),
                "interface_quality": round(0.8 - (index * 0.02), 2),
                "hotspot_agreement": round(0.76 - (index * 0.01), 2),
                "epitope_correctness": round(0.74 - (index * 0.01), 2),
                "developability": round(0.71 - (index * 0.01), 2),
                "diversity": round(0.6 + (index * 0.1), 2),
                "off_target_risk": round(0.18 + (index * 0.02), 2),
            },
            "validation": {tool: "pass" for tool in route[2:]},
            "rationale": {
                "why_selected": [
                    f"Supports the {hypothesis['name']} branch objective.",
                    "Route includes two distinct validation models.",
                ],
                "main_risks": [
                    "Results are mock-generated and not experimentally validated.",
                    "Epitope assignment remains provisional without explicit user input.",
                ],
            },
            "provenance": {
                "target_entry": f"UniProt:{spec['target']['identifier']}",
                "execution_mode": spec["execution_mode"],
                "structures_used": ["PDB:1N8Z", "PDB:6OGE"],
                "mock_generation": True,
            },
        }
        validate_record("CandidateRecord", candidate)
        candidates.append(candidate)
    return candidates
