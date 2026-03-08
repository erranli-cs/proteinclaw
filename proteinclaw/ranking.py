from __future__ import annotations


DEFAULT_WEIGHTS = {
    "complex_confidence": 0.30,
    "monomer_confidence": 0.15,
    "interface_quality": 0.10,
    "hotspot_agreement": 0.10,
    "epitope_correctness": 0.10,
    "developability": 0.10,
    "diversity": 0.05,
    "off_target_risk": -0.10,
}


def score_candidate(candidate: dict, weights: dict[str, float] | None = None) -> float:
    weights = weights or DEFAULT_WEIGHTS
    total = 0.0
    for metric, weight in weights.items():
        total += candidate["scores"].get(metric, 0.0) * weight
    return round(total, 4)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    scored: list[dict] = []
    for candidate in candidates:
        updated = {**candidate, "final_score": score_candidate(candidate)}
        scored.append(updated)
    return sorted(scored, key=lambda item: item["final_score"], reverse=True)
