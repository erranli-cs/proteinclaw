from __future__ import annotations

from pathlib import Path

from proteinclaw.campaign import apply_clarifications, build_campaign_spec, resolve_clarifications
from proteinclaw.candidates import _candidate_sequence, _extract_sequence_from_outputs, build_candidates
from proteinclaw.dossier import build_target_dossier, download_pdb_file, write_fixture_pdb
from proteinclaw.hypotheses import generate_hypotheses
from proteinclaw.ranking import rank_candidates
from proteinclaw.reporting import write_artifacts
from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.tooling import run_tool_adapter, select_route
from proteinclaw.utils import utc_now


def trace_event(campaign_id: str, event_type: str, object_id: str, summary: str, details: dict) -> dict:
    event = {
        "schema_version": SCHEMA_VERSION,
        "time": utc_now(),
        "campaign_id": campaign_id,
        "type": event_type,
        "object_id": object_id,
        "human_visible_summary": summary,
        "details": details,
    }
    validate_record("TraceEvent", event)
    return event


def run_campaign(
    prompt: str,
    root: Path,
    execution_mode: str = "academic",
    use_fixture: bool = False,
    clarifications: dict[str, str] | None = None,
    interactive: bool = False,
) -> dict:
    spec = build_campaign_spec(prompt, execution_mode=execution_mode)
    campaign_root = root / "artifacts" / "campaigns" / spec["campaign_id"]
    trace_events = [
        trace_event(spec["campaign_id"], "campaign_started", spec["campaign_id"], "Campaign initialized from user prompt.", {"prompt": prompt})
    ]

    resolved_answers, clarification_records = resolve_clarifications(spec, interactive=interactive, answers=clarifications)
    outstanding = [item["key"] for item in clarification_records if item["default_applied"]]
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "clarifications_requested",
            spec["campaign_id"],
            f"{len(clarification_records)} high-value clarifications were resolved.",
            {"clarifications": clarification_records, "defaults_applied": outstanding},
        )
    )
    spec = apply_clarifications(spec, resolved_answers)
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "clarifications_applied",
            spec["campaign_id"],
            "Clarification answers applied to campaign spec.",
            {"answers": resolved_answers},
        )
    )

    dossier = build_target_dossier(spec, root / ".cache" / "dossiers", use_fixture=use_fixture)
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "dossier_built",
            spec["campaign_id"],
            "Target dossier assembled.",
            {"warnings": dossier["warnings"], "source_count": len(dossier["sources"]), "literature_count": len(dossier["literature"])},
        )
    )
    spec["target"]["structure_ids"] = [item["pdb_id"] for item in dossier["structures"][:3]]

    hypotheses = generate_hypotheses(spec, dossier)
    trace_events.append(
        trace_event(spec["campaign_id"], "hypotheses_generated", spec["campaign_id"], f"Generated {len(hypotheses)} hypotheses.", {})
    )

    routes: dict[str, list[str]] = {}
    invocations: list[dict] = []
    invocations_by_hypothesis: dict[str, list[dict]] = {}
    for hypothesis in hypotheses:
        route = select_route(spec["execution_mode"], hypothesis)
        routes[hypothesis["hypothesis_id"]] = route
        invocations_by_hypothesis[hypothesis["hypothesis_id"]] = []
        trace_events.append(
            trace_event(
                spec["campaign_id"],
                "route_selected",
                hypothesis["hypothesis_id"],
                f"Selected route {' -> '.join(route)}.",
                {"route": route, "justification": "Preferred generation and validation tools selected from the registry."},
            )
        )
        selected_structure = dossier["structures"][0]["pdb_id"]
        local_target_pdb = campaign_root / "inputs" / hypothesis["hypothesis_id"] / f"{selected_structure}.pdb"
        if use_fixture:
            write_fixture_pdb(local_target_pdb, chain_id="A")
        else:
            download_pdb_file(selected_structure, local_target_pdb)

        target_sequence = dossier["annotations"].get("sequence") or ""
        binder_sequence = _candidate_sequence(hypothesis["name"])
        previous_structure_path = str(local_target_pdb)

        for tool in route:
            stage = "validation" if tool == "alphafold3" else ("sequence_design" if tool == "ligandmpnn" else "generation")
            tool_output_dir = campaign_root / "tools" / hypothesis["hypothesis_id"] / tool
            if tool == "rfd3":
                inputs = {
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "output_dir": str(tool_output_dir),
                    "upload_path": str(local_target_pdb),
                    "file_setting_key": "pdbFile",
                    "settings": {
                        "task": "Binder Design",
                        "targetChains": ["A"],
                        "binderLength": "20-30",
                        "numDesigns": 1,
                        "verify": False,
                    },
                }
            elif tool == "ligandmpnn":
                inputs = {
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "output_dir": str(tool_output_dir),
                    "upload_path": previous_structure_path,
                    "file_setting_key": "pdbFile",
                    "settings": {
                        "designedChains": ["B"],
                        "numSequences": 2,
                        "temperature": 0.1,
                        "noiseLevel": "0.2",
                        "omitAAs": "C",
                    },
                }
            else:
                inputs = {
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "output_dir": str(tool_output_dir),
                    "settings": {
                        "sequence": f"{target_sequence}:{binder_sequence}" if target_sequence else binder_sequence,
                        "numModels": "1",
                        "msaMode": "mmseqs2_uniref_env",
                        "numRecycles": 3,
                        "numRelax": 0,
                        "pairMode": "unpaired_paired",
                    },
                }
            invocation = run_tool_adapter(
                spec["campaign_id"],
                tool,
                stage,
                spec["execution_mode"],
                inputs,
                root,
            )
            invocations.append(invocation)
            invocations_by_hypothesis[hypothesis["hypothesis_id"]].append(invocation)
            if tool == "rfd3" and invocation["status"] == "pass":
                pdbs = [path for path in invocation["outputs"].get("downloaded_files", []) if path.lower().endswith(".pdb")]
                if pdbs:
                    previous_structure_path = pdbs[0]
            if tool == "ligandmpnn" and invocation["outputs"].get("output_dir"):
                extracted = _extract_sequence_from_outputs(Path(invocation["outputs"]["output_dir"]))
                if extracted:
                    binder_sequence = extracted
            trace_events.append(
                trace_event(
                    spec["campaign_id"],
                    "tool_invoked",
                    invocation["invocation_id"],
                    f"{tool} completed with status {invocation['status']}.",
                    {"tool": tool, "stage": stage, "status": invocation["status"], "failure_codes": invocation["failure_codes"]},
                )
            )

    candidates = build_candidates(spec, hypotheses, routes, invocations_by_hypothesis)
    ranked = rank_candidates(candidates)
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "candidates_ranked",
            spec["campaign_id"],
            f"Ranked {len(ranked)} candidates.",
            {"top_candidate": ranked[0]["candidate_id"] if ranked else None, "weights": "default"},
        )
    )

    manifest = write_artifacts(root, spec, dossier, hypotheses, invocations, ranked, trace_events)
    return {
        "campaign_spec": spec,
        "target_dossier": dossier,
        "hypotheses": hypotheses,
        "tool_invocations": invocations,
        "ranked_candidates": ranked,
        "trace_events": trace_events,
        "manifest": manifest,
    }
