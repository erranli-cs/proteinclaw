from __future__ import annotations

from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.utils import stable_id


def generate_hypotheses(spec: dict, dossier: dict) -> list[dict]:
    target_name = spec["target"]["name"]
    campaign_id = spec["campaign_id"]
    if spec["target"]["identifier"] == "P04629":
        base = [
            {
                "name": "ngf-interface-occlusion",
                "objective": f"Occupy the NGF-facing extracellular interface on {target_name} to block agonist engagement.",
                "region_of_interest": "NGF-binding interface on the extracellular domain",
                "exclusion_zones": ["Membrane-proximal steric clash zone", "non-interface glycan-exposed surfaces"],
                "scaffold_bias": "mini-binder",
                "validation_metrics": ["complex_confidence", "epitope_correctness", "hotspot_agreement"],
                "stop_criteria": ["off_epitope", "predictor_disagreement"],
                "assumptions": ["Blocking the NGF-binding face is sufficient for antagonism.", "2IFG captures a relevant interface geometry."],
            }
        ]
    else:
        base = [
            {
                "name": "focused-pocket-blockade" if spec["target"]["identifier"].startswith("PDB:") else "domain-ii-blockade",
                "objective": (
                    f"Occupy the requested pocket on {target_name} with a single focused minibinder design."
                    if spec["target"]["identifier"].startswith("PDB:")
                    else f"Block a dimerization-relevant extracellular surface on {target_name}."
                ),
                "region_of_interest": (
                    "User-specified pocket residues"
                    if spec["target"]["identifier"].startswith("PDB:")
                    else "Extracellular domain II"
                ),
                "exclusion_zones": ["Known glycan-dense surfaces"],
                "scaffold_bias": "mini-binder",
                "validation_metrics": ["complex_confidence", "epitope_correctness", "developability"],
                "stop_criteria": ["low_interface_confidence", "off_epitope"],
                "assumptions": ["Run a single focused design branch before broadening the search space."],
            }
        ]
    evidence_refs = [source["source"] for source in dossier["sources"]]
    records: list[dict] = []
    for item in base:
        record = {
            "schema_version": SCHEMA_VERSION,
            "hypothesis_id": stable_id("hyp", f"{campaign_id}|{item['name']}"),
            "campaign_id": campaign_id,
            "name": item["name"],
            "objective": item["objective"],
            "region_of_interest": item["region_of_interest"],
            "exclusion_zones": item["exclusion_zones"],
            "scaffold_bias": item["scaffold_bias"],
            "validation_metrics": item["validation_metrics"],
            "stop_criteria": item["stop_criteria"],
            "assumptions": item["assumptions"],
            "evidence_refs": evidence_refs,
        }
        validate_record("HypothesisRecord", record)
        records.append(record)
    return records
