from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

from proteinclaw.schemas import dump_json
from proteinclaw.utils import utc_now


SCOUT_SOURCES = [
    {"name": "UniProt", "category": "reference_data", "action_recommendation": "watch"},
    {"name": "RCSB PDB", "category": "reference_data", "action_recommendation": "watch"},
    {"name": "Europe PMC", "category": "literature", "action_recommendation": "evaluate"},
    {"name": "OpenAlex", "category": "literature_metadata", "action_recommendation": "watch"},
    {"name": "GitHub releases", "category": "tool_watch", "action_recommendation": "evaluate"},
]


def run_heartbeat(root: Path) -> Path:
    items = []
    for item in SCOUT_SOURCES:
        live_summary = _fetch_source_summary(item["name"])
        items.append(
            {
                "source": item["name"],
                "category": item["category"],
                "claim_summary": live_summary["summary"],
                "license_notes": "Review required before registry admission.",
                "action_recommendation": item["action_recommendation"],
                "retrieved_at": live_summary["retrieved_at"],
            }
        )
    payload = {
        "generated_at": utc_now(),
        "status": "bootstrap",
        "notes": "This heartbeat run builds a structured scouting queue with live source summaries when available.",
        "items": items,
    }
    output = root / "artifacts" / "heartbeat" / "scouting-queue.json"
    dump_json(output, payload)
    return output


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "proteinclaw/0.1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_source_summary(source_name: str) -> dict:
    try:
        if source_name == "UniProt":
            payload = _fetch_json("https://rest.uniprot.org/uniprotkb/P04626.json")
            summary = f"Reference data reachable for {payload.get('primaryAccession', 'unknown accession')}."
        elif source_name == "RCSB PDB":
            payload = _fetch_json("https://data.rcsb.org/rest/v1/core/entry/1N8Z")
            summary = f"Structure endpoint reachable for {payload.get('rcsb_id', 'unknown entry')}."
        elif source_name == "Europe PMC":
            payload = _fetch_json(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
                + urllib.parse.quote("HER2 protein binder")
                + "&format=json&pageSize=1"
            )
            hit = ((payload.get("resultList") or {}).get("result") or [{}])[0]
            summary = f"Top literature hit: {hit.get('title', 'none')}"
        elif source_name == "OpenAlex":
            payload = _fetch_json("https://api.openalex.org/works?search=" + urllib.parse.quote("HER2 protein binder") + "&per-page=1")
            hit = (payload.get("results") or [{}])[0]
            summary = f"Top metadata hit: {hit.get('title', 'none')}"
        elif source_name == "GitHub releases":
            payload = _fetch_json("https://api.github.com/repos/sipeed/picoclaw/releases")
            latest = (payload or [{}])[0]
            summary = f"Latest release: {latest.get('tag_name', 'none')}"
        else:
            summary = "Source registered for recurring scouting."
    except Exception as exc:
        summary = f"Source check failed: {exc}"
    return {"summary": summary, "retrieved_at": utc_now()}
