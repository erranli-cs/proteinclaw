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
    "literature": [
        {
            "source": "bootstrap_fixture",
            "title": "HER2 extracellular targeting remains a relevant binder-design context.",
            "identifier": "fixture-her2-1",
            "year": 2026,
            "url": None,
            "reason": "Bootstrap literature placeholder for offline tests.",
        },
        {
            "source": "bootstrap_fixture",
            "title": "Known HER2 therapeutic epitope competition is a valid mechanistic branch.",
            "identifier": "fixture-her2-2",
            "year": 2026,
            "url": None,
            "reason": "Bootstrap literature placeholder for offline tests.",
        },
    ],
}

EGFR_FIXTURE = {
    "uniprot": {
        "primaryAccession": "P00533",
        "proteinDescription": {"recommendedName": {"fullName": {"value": "Epidermal growth factor receptor"}}},
        "genes": [{"geneName": {"value": "EGFR"}}],
        "organism": {"scientificName": "Homo sapiens"}
    },
    "structures": [
        {"pdb_id": "1IVO", "description": "EGFR kinase domain structure"},
        {"pdb_id": "1YY9", "description": "EGFR extracellular region structure"}
    ],
    "literature": [
        {
            "source": "bootstrap_fixture",
            "title": "EGFR-targeted protein binder concepts remain relevant for receptor blockade.",
            "identifier": "fixture-egfr-1",
            "year": 2026,
            "url": None,
            "reason": "Bootstrap literature placeholder for offline tests."
        }
    ]
}
BINDER_TERMS = ("binder", "binding", "antibody", "nanobody", "miniprotein", "protein")


FIXTURES = {
    "P04626": HER2_FIXTURE,
    "P00533": EGFR_FIXTURE,
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


def fetch_europe_pmc_literature(query: str, limit: int = 3) -> tuple[list[dict], dict]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query={urllib.parse.quote(query)}&format=json&pageSize={limit}"
    )
    payload = _fetch_json(url)
    results = []
    for item in (payload.get("resultList") or {}).get("result", []):
        results.append(
            {
                "source": "Europe PMC",
                "title": item.get("title"),
                "identifier": item.get("id") or item.get("pmid") or item.get("doi"),
                "year": item.get("pubYear"),
                "url": f"https://europepmc.org/article/MED/{item['pmid']}" if item.get("pmid") else None,
                "reason": "Biomedical literature enrichment",
            }
        )
    return results, {"source": "Europe PMC", "query": query, "url": url, "retrieved_at": utc_now()}


def fetch_openalex_literature(query: str, limit: int = 3) -> tuple[list[dict], dict]:
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(query)}&per-page={limit}"
    payload = _fetch_json(url)
    results = []
    for item in payload.get("results", []):
        results.append(
            {
                "source": "OpenAlex",
                "title": item.get("title"),
                "identifier": item.get("id"),
                "year": item.get("publication_year"),
                "url": item.get("id"),
                "reason": "Scholarly metadata enrichment",
            }
        )
    return results, {"source": "OpenAlex", "query": query, "url": url, "retrieved_at": utc_now()}


def _filter_literature_hits(results: list[dict], keywords: list[str], allow_unfiltered_fallback: bool = False) -> list[dict]:
    filtered = []
    normalized_keywords = [item.lower() for item in keywords if item]
    for item in results:
        title = (item.get("title") or "").lower()
        if not title:
            continue
        if not any(keyword in title for keyword in normalized_keywords):
            continue
        if not any(term in title for term in BINDER_TERMS):
            continue
        filtered.append(item)
    if filtered:
        return filtered
    return results if allow_unfiltered_fallback else []


def build_target_dossier(spec: dict, cache_dir: Path, use_fixture: bool = False) -> dict:
    identifier = spec["target"]["identifier"]
    target_name = spec["target"]["name"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{identifier}.json"

    sources: list[dict] = []
    warnings: list[str] = []
    annotations: dict = {}
    structures: list[dict] = []
    literature: list[dict] = []

    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        try:
            validate_record("TargetDossier", payload)
            return payload
        except (TypeError, ValueError):
            cache_path.unlink()
            warnings.append("Discarded stale cached dossier due to schema mismatch.")

    fixture = FIXTURES.get(identifier)
    if use_fixture:
        uniprot_payload = (fixture or {}).get("uniprot", {})
        structures = (fixture or {}).get("structures", [])
        literature = (fixture or {}).get("literature", [])
        sources.extend(
            [
                {"source": "bootstrap_fixture", "identifier": identifier, "retrieved_at": utc_now()},
                {"source": "bootstrap_fixture", "identifier": "RCSB HER2 fixture", "retrieved_at": utc_now()},
                {"source": "bootstrap_fixture", "identifier": "HER2 literature fixture", "retrieved_at": utc_now()},
            ]
        )
    else:
        try:
            uniprot_payload, source_meta = fetch_uniprot(identifier)
            sources.append(source_meta)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"UniProt retrieval failed: {exc}")
            uniprot_payload = (fixture or {}).get("uniprot", {})
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": identifier, "retrieved_at": utc_now()})

        try:
            structures, source_meta = fetch_pdb_structures(target_name)
            sources.append(source_meta)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"RCSB retrieval failed: {exc}")
            structures = (fixture or {}).get("structures", [])
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": f"{target_name} structures", "retrieved_at": utc_now()})

        gene_name = (((uniprot_payload.get("genes") or [{}])[0].get("geneName") or {}).get("value"))
        keywords = [target_name, gene_name]
        literature_query = f"{target_name} {gene_name or ''} protein binder".strip()
        try:
            europe_pmc_results, source_meta = fetch_europe_pmc_literature(literature_query)
            sources.append(source_meta)
            literature.extend(_filter_literature_hits(europe_pmc_results, keywords))
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"Europe PMC retrieval failed: {exc}")
            if fixture:
                literature.extend(fixture.get("literature", []))
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": f"{target_name} literature", "retrieved_at": utc_now()})

        try:
            openalex_results, source_meta = fetch_openalex_literature(literature_query)
            sources.append(source_meta)
            existing_ids = {item["identifier"] for item in literature}
            filtered_openalex = _filter_literature_hits(openalex_results, keywords)
            literature.extend(item for item in filtered_openalex if item["identifier"] not in existing_ids)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"OpenAlex retrieval failed: {exc}")
            sources.append({"source": "bootstrap_fixture_fallback", "identifier": f"{target_name} openalex", "retrieved_at": utc_now()})

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
        "literature_highlights": [item["title"] for item in literature[:3] if item.get("title")],
    }

    dossier = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": spec["campaign_id"],
        "target": spec["target"],
        "summary": (
            f"{target_name} ({identifier}) dossier assembled with {len(structures)} structure references "
            f"and {len(literature)} literature references."
        ),
        "sources": sources,
        "annotations": annotations,
        "structures": structures,
        "literature": literature,
        "warnings": warnings,
    }
    validate_record("TargetDossier", dossier)
    dump_json(cache_path, dossier)
    return dossier
