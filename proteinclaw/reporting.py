from __future__ import annotations

from pathlib import Path

from proteinclaw.schemas import SCHEMA_VERSION, dump_json, validate_record
from proteinclaw.utils import utc_now, write_jsonl


def write_artifacts(
    root: Path,
    spec: dict,
    dossier: dict,
    hypotheses: list[dict],
    invocations: list[dict],
    candidates: list[dict],
    trace_events: list[dict],
) -> dict:
    campaign_root = root / "artifacts" / "campaigns" / spec["campaign_id"]
    trace_path = campaign_root / "trace" / "events.jsonl"
    provenance_path = campaign_root / "provenance" / "manifest.json"
    candidates_path = campaign_root / "candidates" / "ranked-candidates.json"
    report_path = campaign_root / "report.md"

    dump_json(campaign_root / "campaign-spec.json", spec)
    dump_json(campaign_root / "target-dossier.json", dossier)
    dump_json(campaign_root / "hypotheses.json", hypotheses)
    dump_json(campaign_root / "tool-invocations.json", invocations)
    dump_json(candidates_path, candidates)
    write_jsonl(trace_path, trace_events)
    dump_json(
        provenance_path,
        {
            "campaign_id": spec["campaign_id"],
            "generated_at": utc_now(),
            "sources": dossier["sources"],
            "mock_generation": any(candidate["provenance"]["mock_generation"] for candidate in candidates),
        },
    )

    top = candidates[:3]
    report_lines = [
        f"# Clawd Campaign Report: {spec['campaign_id']}",
        "",
        "## Summary",
        f"- Target: {spec['target']['name']} ({spec['target']['identifier']})",
        f"- Execution mode: {spec['execution_mode']}",
        f"- Hypotheses explored: {len(hypotheses)}",
        f"- Candidates ranked: {len(candidates)}",
        "",
        "## Dossier",
        dossier["summary"],
        "",
        "## Literature Highlights",
    ]

    for item in dossier["literature"][:3]:
        report_lines.append(f"- {item['source']}: {item['title']}")

    report_lines.extend([
        "",
        "## Clarifications Needed",
    ])

    for field in ("epitope", "modality"):
        if spec["design_space"].get(field) in (None, "open"):
            report_lines.append(f"- {field}: unresolved")
        else:
            report_lines.append(f"- {field}: {spec['design_space'][field]}")
    report_lines.extend(["", "## Top Candidates"])
    for candidate in top:
        report_lines.extend(
            [
                f"### {candidate['candidate_id']}",
                f"- Score: {candidate['final_score']}",
                f"- Hypothesis: {candidate['parent_hypothesis']}",
                f"- Why selected: {', '.join(candidate['rationale']['why_selected'])}",
                f"- Risks: {', '.join(candidate['rationale']['main_risks'])}",
                f"- Validation statuses: {candidate['validation']}",
            ]
        )

    report_lines.extend(
        [
            "",
            "## Notes",
            "- Tool outputs are downloaded into the local campaign directory whenever remote execution succeeds.",
            "- Any tool without a configured or successful backend is marked explicitly as mock or failed in the trace.",
            "",
            "## Next Experiments",
            "- Inspect the downloaded tool outputs before trusting rankings.",
            "- Tighten binder-chain selection and AF3 score extraction once Tamarind result formats are observed.",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": spec["campaign_id"],
        "report_path": str(report_path),
        "artifact_paths": {
            "campaign_spec": str(campaign_root / "campaign-spec.json"),
            "target_dossier": str(campaign_root / "target-dossier.json"),
            "hypotheses": str(campaign_root / "hypotheses.json"),
            "tool_invocations": str(campaign_root / "tool-invocations.json"),
            "candidates": str(candidates_path),
            "trace": str(trace_path),
            "provenance": str(provenance_path),
        },
        "top_candidates": [candidate["candidate_id"] for candidate in top],
        "generated_at": utc_now(),
    }
    validate_record("FinalReportManifest", manifest)
    dump_json(campaign_root / "report-manifest.json", manifest)
    return manifest
