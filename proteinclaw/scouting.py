from __future__ import annotations

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
    payload = {
        "generated_at": utc_now(),
        "status": "bootstrap",
        "notes": "This heartbeat run creates a structured scouting queue. It does not yet fetch live source content.",
        "items": [
            {
                "source": item["name"],
                "category": item["category"],
                "claim_summary": "Source registered for recurring scouting.",
                "license_notes": "Review required before registry admission.",
                "action_recommendation": item["action_recommendation"],
            }
            for item in SCOUT_SOURCES
        ],
    }
    output = root / "artifacts" / "heartbeat" / "scouting-queue.json"
    dump_json(output, payload)
    return output
