from __future__ import annotations

from pathlib import Path

from proteinclaw.campaign import apply_clarifications, build_campaign_spec, required_clarifications
from proteinclaw.candidates import build_candidates
from proteinclaw.dossier import build_target_dossier
from proteinclaw.hypotheses import generate_hypotheses
from proteinclaw.ranking import rank_candidates
from proteinclaw.reporting import write_artifacts
from proteinclaw.schemas import SCHEMA_VERSION, validate_record
from proteinclaw.tooling import mock_tool_invocation, select_route
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
) -> dict:
    spec = build_campaign_spec(prompt, execution_mode=execution_mode)
    trace_events = [
        trace_event(spec["campaign_id"], "campaign_started", spec["campaign_id"], "Campaign initialized from user prompt.", {"prompt": prompt})
    ]

    outstanding = required_clarifications(spec)
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "clarifications_requested",
            spec["campaign_id"],
            f"{len(outstanding)} high-value clarifications remain.",
            {"questions": [item.question for item in outstanding]},
        )
    )
    spec = apply_clarifications(spec, clarifications)

    dossier = build_target_dossier(spec, root / ".cache" / "dossiers", use_fixture=use_fixture)
    trace_events.append(
        trace_event(spec["campaign_id"], "dossier_built", spec["campaign_id"], "Target dossier assembled.", {"warnings": dossier["warnings"]})
    )

    hypotheses = generate_hypotheses(spec, dossier)
    trace_events.append(
        trace_event(spec["campaign_id"], "hypotheses_generated", spec["campaign_id"], f"Generated {len(hypotheses)} hypotheses.", {})
    )

    routes: dict[str, list[str]] = {}
    invocations: list[dict] = []
    for hypothesis in hypotheses:
        route = select_route(spec["execution_mode"], hypothesis)
        routes[hypothesis["hypothesis_id"]] = route
        trace_events.append(
            trace_event(
                spec["campaign_id"],
                "route_selected",
                hypothesis["hypothesis_id"],
                f"Selected route {' -> '.join(route)}.",
                {"route": route},
            )
        )
        for tool in route:
            stage = "validation" if tool in ("alphafold3", "rf3", "chai1", "boltz", "openfold3-preview") else ("sequence_design" if "mpnn" in tool else "generation")
            invocations.append(
                mock_tool_invocation(
                    spec["campaign_id"],
                    tool,
                    stage,
                    spec["execution_mode"],
                    {"hypothesis_id": hypothesis["hypothesis_id"]},
                    {"status": "mock"},
                )
            )

    candidates = build_candidates(spec, hypotheses, routes)
    ranked = rank_candidates(candidates)
    trace_events.append(
        trace_event(
            spec["campaign_id"],
            "candidates_ranked",
            spec["campaign_id"],
            f"Ranked {len(ranked)} candidates.",
            {"top_candidate": ranked[0]["candidate_id"] if ranked else None},
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
