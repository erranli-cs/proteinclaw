from __future__ import annotations

import json
from pathlib import Path

from proteinclaw.schemas import dump_json
from proteinclaw.utils import utc_now


def export_learning_dataset(root: Path, output_path: Path | None = None) -> Path:
    campaigns_root = root / "artifacts" / "campaigns"
    rows: list[dict] = []
    if campaigns_root.exists():
        for campaign_dir in sorted(campaigns_root.iterdir()):
            candidates_path = campaign_dir / "candidates" / "ranked-candidates.json"
            spec_path = campaign_dir / "campaign-spec.json"
            if not candidates_path.exists() or not spec_path.exists():
                continue
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
            for rank, candidate in enumerate(candidates, start=1):
                rows.append(
                    {
                        "campaign_id": spec["campaign_id"],
                        "execution_mode": spec["execution_mode"],
                        "target_identifier": spec["target"]["identifier"],
                        "candidate_id": candidate["candidate_id"],
                        "rank": rank,
                        "final_score": candidate["final_score"],
                        "parent_hypothesis": candidate["parent_hypothesis"],
                        "mock_generation": candidate["provenance"].get("mock_generation", False),
                    }
                )

    payload = {
        "generated_at": utc_now(),
        "row_count": len(rows),
        "rows": rows,
    }
    output = output_path or (root / "artifacts" / "learning" / "dataset.json")
    dump_json(output, payload)
    return output
