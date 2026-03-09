from __future__ import annotations

import html
from pathlib import Path

from proteinclaw.schemas import SCHEMA_VERSION, dump_json, validate_record
from proteinclaw.utils import utc_now, write_jsonl


def _campaign_ui_slug(campaign_id: str) -> str:
    if campaign_id.startswith("campaign-"):
        return f"campine-{campaign_id.split('-', 1)[1]}"
    return f"campine-{campaign_id}"


def _find_alphafold_outputs(invocations: list[dict], root: Path) -> dict[str, str]:
    for invocation in invocations:
        if invocation.get("tool") != "alphafold3":
            continue
        for path in invocation.get("outputs", {}).get("downloaded_files", []):
            candidate = Path(path)
            if candidate.suffix.lower() == ".pdb" and "unrelaxed" in candidate.name:
                outputs = {"pdb": str(candidate.relative_to(root))}
                score_json = next(
                    (
                        str(Path(item).relative_to(root))
                        for item in invocation.get("outputs", {}).get("downloaded_files", [])
                        if str(item).lower().endswith(".json") and "scores_rank" in Path(item).name
                    ),
                    None,
                )
                if score_json:
                    outputs["scores"] = score_json
                return outputs
    return {}


def _render_report_ui(
    spec: dict,
    dossier: dict,
    hypotheses: list[dict],
    invocations: list[dict],
    candidates: list[dict],
    manifest_time: str,
    artifact_links: dict[str, str],
) -> str:
    top = candidates[:3]
    primary = candidates[0] if candidates else None
    target_identifier = spec["target"]["identifier"]
    target_label = f"{spec['target']['name']} ({target_identifier})"
    tool_statuses = {item["tool"]: item["status"] for item in invocations}
    alphafold_outputs = artifact_links.get("alphafold", {})
    overall_status = "complete"
    if any(status == "failed" for status in tool_statuses.values()):
        overall_status = "degraded"
    elif any(status in {"mock", "skipped"} for status in tool_statuses.values()):
        overall_status = "partial"

    def badge(label: str, tone: str = "neutral") -> str:
        return f'<span class="badge badge-{tone}">{html.escape(label)}</span>'

    def artifact_href(name: str) -> str:
        return html.escape(artifact_links[name])

    candidate_cards = []
    for candidate in top:
        validation = ", ".join(f"{key}: {value}" for key, value in candidate["validation"].items()) or "pending"
        candidate_cards.append(
            f"""
            <article class="card candidate">
              <div class="candidate-head">
                <div>
                  <div class="eyebrow">Candidate</div>
                  <h3>{html.escape(candidate['candidate_id'])}</h3>
                </div>
                <p class="score">{candidate['final_score']}</p>
              </div>
              <p class="muted">{html.escape(candidate['parent_hypothesis'])}</p>
              <p>{html.escape(', '.join(candidate['rationale']['why_selected']))}</p>
              <p class="meta"><strong>Validation:</strong> {html.escape(validation)}</p>
              <p class="meta"><strong>Risks:</strong> {html.escape(', '.join(candidate['rationale']['main_risks']))}</p>
            </article>
            """
        )

    literature_items = "".join(
        f"<li><strong>{html.escape(item['source'])}</strong> {html.escape(item['title'])}</li>"
        for item in dossier["literature"][:3]
    ) or "<li>No literature hits captured yet.</li>"

    hypothesis_items = "".join(
        f"<li>{html.escape(item['objective'])}</li>"
        for item in hypotheses
    )

    validation_block = (
        "".join(
            badge(f"{tool}: {status}", "good" if status == "pass" else ("bad" if status == "failed" else "warn"))
            for tool, status in tool_statuses.items()
        )
        or badge("no tool records", "warn")
    )

    alphafold_card = (
        f"""
        <article class="card">
          <div class="section-title">
            <h2>AlphaFold Structure</h2>
            {badge(tool_statuses.get('alphafold3', 'pending'), 'good' if tool_statuses.get('alphafold3') == 'pass' else ('bad' if tool_statuses.get('alphafold3') == 'failed' else 'warn'))}
          </div>
          <p class="muted">Predicted complex structure and scoring outputs from the AlphaFold validation stage.</p>
          <div class="artifact-list">
            <a class="artifact-link" href="{html.escape(alphafold_outputs['pdb'])}"><span>Predicted Complex PDB</span><span>.pdb</span></a>
            {f'<a class="artifact-link" href="{html.escape(alphafold_outputs["scores"])}"><span>Score Summary</span><span>.json</span></a>' if alphafold_outputs.get('scores') else ''}
          </div>
        </article>
        """
        if alphafold_outputs.get("pdb")
        else f"""
        <article class="card">
          <div class="section-title">
            <h2>AlphaFold Structure</h2>
            {badge(tool_statuses.get('alphafold3', 'pending'), 'good' if tool_statuses.get('alphafold3') == 'pass' else ('bad' if tool_statuses.get('alphafold3') == 'failed' else 'warn'))}
          </div>
          <p class="muted">No AlphaFold structure file is available in the current artifact bundle.</p>
        </article>
        """
    )

    top_candidate_block = (
        f"""
        <article class="card featured">
          <div class="section-title">
            <h2>Top Candidate</h2>
            {badge(overall_status, "good" if overall_status == "complete" else "warn")}
          </div>
          <div class="featured-grid">
            <div>
              <div class="eyebrow">Candidate ID</div>
              <h3 class="featured-title">{html.escape(primary['candidate_id'])}</h3>
              <p class="muted">{html.escape(primary['parent_hypothesis'])}</p>
            </div>
            <div class="metric-block">
              <div class="eyebrow">Score</div>
              <p class="hero-score">{primary['final_score']}</p>
            </div>
          </div>
          <div class="info-list">
            <div><span>Why selected</span><strong>{html.escape(', '.join(primary['rationale']['why_selected']))}</strong></div>
            <div><span>Validation</span><strong>{html.escape(', '.join(f"{k}: {v}" for k, v in primary['validation'].items()) or 'pending')}</strong></div>
            <div><span>Risks</span><strong>{html.escape(', '.join(primary['rationale']['main_risks']))}</strong></div>
          </div>
        </article>
        """
        if primary
        else '<article class="card featured"><h2>Top Candidate</h2><p>No candidates yet.</p></article>'
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(spec['campaign_id'])}</title>
    <style>
      :root {{
        --ink: #11222d;
        --muted: #60727d;
        --line: rgba(17, 34, 45, 0.12);
        --paper: #f4f1ea;
        --panel: rgba(255, 252, 247, 0.92);
        --accent: #0f6c78;
        --accent-strong: #0b4b53;
        --accent-soft: rgba(15, 108, 120, 0.12);
        --signal: #a64b00;
        --shadow: 0 18px 50px rgba(17, 34, 45, 0.08);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(15,108,120,0.18), transparent 22rem),
          radial-gradient(circle at bottom right, rgba(166,75,0,0.16), transparent 26rem),
          linear-gradient(180deg, #ebe6dc 0%, var(--paper) 55%, #eeebe3 100%);
      }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 72px; }}
      .hero {{
        position: relative;
        overflow: hidden;
        background: linear-gradient(135deg, rgba(255,252,247,0.96), rgba(226,236,235,0.94));
        border: 1px solid var(--line);
        border-radius: 30px;
        padding: 30px;
        box-shadow: var(--shadow);
      }}
      .hero::after {{
        content: "";
        position: absolute;
        inset: auto -8% -28% auto;
        width: 280px;
        height: 280px;
        border-radius: 999px;
        background: radial-gradient(circle, rgba(15,108,120,0.16), transparent 70%);
      }}
      .hero-top {{
        display: flex;
        gap: 24px;
        justify-content: space-between;
        align-items: flex-start;
      }}
      .hero h1 {{ margin: 0 0 10px; font-size: clamp(2.4rem, 5vw, 5rem); line-height: 0.95; max-width: 10ch; }}
      .eyebrow {{ text-transform: uppercase; letter-spacing: 0.14em; color: var(--accent); font-size: 0.74rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
      .lede {{ max-width: 62ch; font-size: 1.02rem; color: #2a3d48; }}
      .hero-grid, .grid {{
        display: grid; gap: 18px; margin-top: 22px;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }}
      .dashboard {{
        display: grid;
        gap: 18px;
        grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr);
        margin-top: 18px;
      }}
      .stack {{ display: grid; gap: 18px; }}
      .card {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 20px;
        box-shadow: var(--shadow);
      }}
      .card h2, .card h3 {{ margin-top: 0; }}
      .muted {{ color: var(--muted); }}
      .score {{ font-size: 2.4rem; margin: 0; color: var(--accent-strong); font-weight: 700; }}
      ul {{ margin: 0; padding-left: 18px; }}
      .candidate {{
        border-color: rgba(15,108,120,0.22);
        background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(238,246,246,0.92));
      }}
      .featured {{
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(244,248,248,0.94));
        border-color: rgba(15,108,120,0.26);
      }}
      .featured-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) 180px;
        gap: 20px;
        align-items: end;
      }}
      .featured-title {{
        margin: 6px 0 4px;
        font-size: clamp(1.8rem, 3vw, 2.5rem);
      }}
      .metric-block {{
        padding: 16px;
        border-radius: 20px;
        background: rgba(15,108,120,0.07);
        border: 1px solid rgba(15,108,120,0.12);
      }}
      .hero-score {{
        margin: 4px 0 0;
        font-size: 3rem;
        line-height: 0.95;
        color: var(--accent-strong);
        font-weight: 700;
      }}
      .info-list {{
        display: grid;
        gap: 10px;
        margin-top: 18px;
      }}
      .info-list div {{
        display: grid;
        gap: 4px;
        padding-top: 10px;
        border-top: 1px solid rgba(17,34,45,0.08);
      }}
      .info-list span {{
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.72rem;
        color: var(--muted);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }}
      .candidate-head {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: baseline;
      }}
      .meta {{
        margin: 10px 0 0;
        font-size: 0.95rem;
        color: #304651;
      }}
      .stat {{
        background: rgba(255,255,255,0.66);
        border-radius: 18px;
        padding: 14px 16px;
        border: 1px solid rgba(17,34,45,0.08);
      }}
      .stat strong {{
        display: block;
        margin-top: 6px;
        font-size: 1.2rem;
        color: var(--accent-strong);
      }}
      .route {{
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        background: var(--accent-soft);
        margin: 0 6px 6px 0;
        color: var(--accent-strong);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.88rem;
      }}
      .badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 10px;
        border-radius: 999px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.82rem;
        border: 1px solid transparent;
      }}
      .badge-good {{ background: rgba(33, 125, 89, 0.12); color: #1f6a4d; border-color: rgba(33, 125, 89, 0.18); }}
      .badge-warn {{ background: rgba(166, 75, 0, 0.12); color: #8a430b; border-color: rgba(166, 75, 0, 0.18); }}
      .badge-bad {{ background: rgba(160, 33, 33, 0.12); color: #8f2222; border-color: rgba(160, 33, 33, 0.18); }}
      .badge-neutral {{ background: rgba(17,34,45,0.08); color: #304651; border-color: rgba(17,34,45,0.1); }}
      .artifact-list {{
        display: grid;
        gap: 10px;
      }}
      .artifact-link {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: center;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(255,255,255,0.7);
        border: 1px solid rgba(17,34,45,0.08);
        color: inherit;
        text-decoration: none;
      }}
      .artifact-link:hover {{ background: rgba(15,108,120,0.08); }}
      .artifact-link span:last-child {{
        color: var(--accent-strong);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.82rem;
      }}
      .banner {{
        min-width: 240px;
        padding: 18px 20px;
        border-radius: 20px;
        background: rgba(17,34,45,0.9);
        color: #f8f5ef;
      }}
      .banner p {{ margin: 0; }}
      .banner .eyebrow {{ color: #9fdbe0; }}
      .section-title {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        margin-bottom: 14px;
      }}
      .footnote {{
        margin-top: 22px;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      @media (max-width: 760px) {{
        .hero-top {{ flex-direction: column; }}
        .banner {{ min-width: 0; width: 100%; }}
        .dashboard, .featured-grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-top">
          <div>
            <div class="eyebrow">Campaign UI</div>
            <h1>{html.escape(spec['target']['name'])}</h1>
            <p class="lede">{html.escape(dossier['summary'])}</p>
          </div>
          <aside class="banner">
            <div class="eyebrow">Campaign ID</div>
            <p>{html.escape(spec['campaign_id'])}</p>
            <p class="muted" style="color: rgba(248,245,239,0.72); margin-top: 10px;">Target: {html.escape(target_label)}</p>
          </aside>
        </div>
        <div class="hero-grid">
          <div class="stat">
            <div class="eyebrow">Execution</div>
            <strong>{html.escape(spec['execution_mode'])}</strong>
          </div>
          <div class="stat">
            <div class="eyebrow">Epitope</div>
            <strong>{html.escape(spec['design_space'].get('epitope') or 'unresolved')}</strong>
          </div>
          <div class="stat">
            <div class="eyebrow">Candidates</div>
            <strong>{len(candidates)}</strong>
          </div>
          <div class="stat">
            <div class="eyebrow">Generated</div>
            <strong>{html.escape(manifest_time)}</strong>
          </div>
        </div>
      </section>

      <section class="dashboard">
        <div class="stack">
          {top_candidate_block}
          <article class="card">
            <div class="section-title">
              <h2>Validation and Tool Status</h2>
              {badge(spec['execution_mode'], 'neutral')}
            </div>
            <p>{validation_block}</p>
          </article>
          {alphafold_card}
          <article class="card">
            <div class="section-title">
              <h2>Other Candidates</h2>
              <span class="route">{len(top)} shown</span>
            </div>
            <div class="grid">
              {''.join(candidate_cards[1:]) or '<p class="muted">Single-candidate run.</p>'}
            </div>
          </article>
        </div>

        <div class="stack">
          <article class="card">
            <div class="section-title">
              <h2>Artifacts</h2>
              {badge("machine-readable", "neutral")}
            </div>
            <div class="artifact-list">
              <a class="artifact-link" href="{artifact_href('report')}"><span>Report</span><span>report.md</span></a>
              <a class="artifact-link" href="{artifact_href('run_log')}"><span>Run Log</span><span>run_log.md</span></a>
              <a class="artifact-link" href="{artifact_href('tool_invocations')}"><span>Tool Invocations</span><span>tool-invocations.json</span></a>
              <a class="artifact-link" href="{artifact_href('target_dossier')}"><span>Target Dossier</span><span>target-dossier.json</span></a>
            </div>
          </article>
          <article class="card">
            <div class="section-title">
              <h2>Hypothesis</h2>
              <span class="route">{html.escape(hypotheses[0]['name']) if hypotheses else 'pending'}</span>
            </div>
            <ul>{hypothesis_items}</ul>
          </article>
          <article class="card">
            <div class="section-title">
              <h2>Literature</h2>
              <span class="route">{len(dossier['literature'])} references</span>
            </div>
            <ul>{literature_items}</ul>
          </article>
          <article class="card">
            <div class="section-title">
              <h2>Route</h2>
              <span class="route">{html.escape(primary['candidate_id']) if primary else 'no candidate'}</span>
            </div>
            <p>
              <span class="route">RFdiffusion3</span>
              <span class="route">LigandMPNN</span>
              <span class="route">AlphaFold3</span>
            </p>
            <p class="footnote">This page is a static snapshot generated from campaign artifacts. It is presentation only and does not replace the underlying trace, provenance, or tool outputs.</p>
          </article>
        </div>
      </section>

      <section class="grid">
        <article class="card">
          <div class="section-title">
            <h2>Executive Summary</h2>
            {badge(target_identifier, "neutral")}
          </div>
          <p>{html.escape(dossier['summary'])}</p>
          <p class="footnote">Generated at {html.escape(manifest_time)}. Campaign scope, provenance, and trace are preserved in the linked artifacts above.</p>
        </article>
      </section>
    </main>
  </body>
</html>
"""


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
    run_log_path = campaign_root / "run_log.md"
    ui_slug = _campaign_ui_slug(spec["campaign_id"])
    ui_root = root / "site" / ui_slug
    ui_path = ui_root / "index.html"
    alphafold_outputs = _find_alphafold_outputs(invocations, root)
    artifact_links = {
        "report": str(report_path.relative_to(root)),
        "run_log": str(run_log_path.relative_to(root)),
        "tool_invocations": str((campaign_root / "tool-invocations.json").relative_to(root)),
        "target_dossier": str((campaign_root / "target-dossier.json").relative_to(root)),
        "alphafold": alphafold_outputs,
    }

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
    ui_root.mkdir(parents=True, exist_ok=True)
    ui_path.write_text(
        _render_report_ui(spec, dossier, hypotheses, invocations, candidates, utc_now(), artifact_links),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": spec["campaign_id"],
        "report_path": str(report_path),
        "ui_path": f"/{ui_slug}",
        "artifact_paths": {
            "campaign_spec": str(campaign_root / "campaign-spec.json"),
            "target_dossier": str(campaign_root / "target-dossier.json"),
            "hypotheses": str(campaign_root / "hypotheses.json"),
            "tool_invocations": str(campaign_root / "tool-invocations.json"),
            "candidates": str(candidates_path),
            "trace": str(trace_path),
            "provenance": str(provenance_path),
            "run_log": str(run_log_path),
            "ui": str(ui_path),
        },
        "top_candidates": [candidate["candidate_id"] for candidate in top],
        "generated_at": utc_now(),
    }
    validate_record("FinalReportManifest", manifest)
    dump_json(campaign_root / "report-manifest.json", manifest)
    return manifest
