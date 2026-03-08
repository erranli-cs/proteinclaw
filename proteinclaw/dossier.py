from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from proteinclaw.schemas import SCHEMA_VERSION, dump_json, validate_record
from proteinclaw.utils import utc_now


HER2_FIXTURE = {
    "uniprot": {
        "primaryAccession": "P04626",
        "proteinDescription": {"recommendedName": {"fullName": {"value": "Receptor tyrosine-protein kinase erbB-2"}}},
        "genes": [{"geneName": {"value": "ERBB2"}}],
        "organism": {"scientificName": "Homo sapiens"},
    },
    "structures": [
        {"pdb_id": "1N8Z", "description": "HER2 extracellular domain complex"},
        {"pdb_id": "6OGE", "description": "HER2 extracellular domain antibody complex"},
        {"pdb_id": "7MN8", "description": "HER2-related extracellular complex"},
    ],
}


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "proteinclaw/0.1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_uniprot(identifier: str) -> tuple[dict, dict]:
    url = f"https://rest.uniprot.org/uniprotkb/{urllib.parse.quote(identifier)}.json"
    payload = _fetch_json(url)
    return payload, {"source": "UniProt", "identifier": identifier, "url": url, "retrieved_at": utc_now()}


def fetch_pdb_structures(query: str) -> tuple[list[dict], dict]:
    encoded = urllib.parse.quote(query)
    url = (
        "https://search.rcsb.org/rcsbsearch/v2/query?json="
        f"%7B%22query%22:%7B%22type%22:%22terminal%22,%22service%22:%22full_text%22,"
        f"%22parameters%22:%7B%22value%22:%22{encoded}%22%7D%7D,%22return_type%22:%22entry%22,%22request_options%22:%7B%22paginate%22:%7B%22start%22:0,%22rows%22:5%7D%7D%7D"
    )
    payload = _fetch_json(url)
    results = [{"pdb_id": item["identifier"], "description": "RCSB search hit"} for item in payload.get("result_set", [])]
    return results, {"source": "RCSB PDB", "query": query, "url": url, "retrieved_at": utc_now()}


def build_target_dossier(spec: dict, cache_dir: Path, use_fixture: bool = False) -> dict:
    identifier = spec["target"]["identifier"]
    target_name = spec["target"]["name"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{identifier}.json"

    sources: list[dict] = []
    warnings: list[str] = []
    annotations: dict = {}
    structures: list[dict] = []

    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        validate_record("TargetDossier", payload)
        return payload

    if use_fixture:
        uniprot_payload = HER2_FIXTURE["uniprot"]
        structures = HER2_FIXTURE["structures"]
        sources.extend(
            [
                {"source": "bootstrap_fixture", "identifier": identifier, "retrieved_at": utc_now()},
                {"source": "bootstrap_fixture", "identifier": "RCSB HER2 fixture", "retrieved_at": utc_now()},
            ]
        )
    else:
        try:
            uniprot_payload, source_meta = fetch_uniprot(identifier)
            sources.append(source_meta)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"UniProt retrieval failed: {exc}")
            uniprot_payload = HER2_FIXTURE["uniprot"] if identifier == "P04626" else {}
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": identifier, "retrieved_at": utc_now()})

        try:
            structures, source_meta = fetch_pdb_structures(target_name)
            sources.append(source_meta)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"RCSB retrieval failed: {exc}")
            structures = HER2_FIXTURE["structures"] if identifier == "P04626" else []
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": f"{target_name} structures", "retrieved_at": utc_now()})

    annotations = {
        "gene": (((uniprot_payload.get("genes") or [{}])[0].get("geneName") or {}).get("value")),
        "recommended_name": (
            (((uniprot_payload.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}).get("value")
        ),
        "organism": (uniprot_payload.get("organism") or {}).get("scientificName"),
        "notes": [
            "Default target region is extracellular domain unless user specifies otherwise.",
            "Glycosylation and epitope accessibility should be checked during branch setup.",
        ],
    }

    dossier = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": spec["campaign_id"],
        "target": spec["target"],
        "summary": f"{target_name} ({identifier}) dossier assembled with {len(structures)} structure references.",
        "sources": sources,
        "annotations": annotations,
        "structures": structures,
        "warnings": warnings,
    }
    validate_record("TargetDossier", dossier)
    dump_json(cache_path, dossier)
    return dossier
