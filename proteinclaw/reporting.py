from __future__ import annotations

import html
from pathlib import Path

from proteinclaw.schemas import SCHEMA_VERSION, dump_json, validate_record
from proteinclaw.utils import utc_now, write_jsonl


def _campaign_ui_slug(campaign_id: str) -> str:
    if campaign_id.startswith("campaign-"):
        return f"campine-{campaign_id.split('-', 1)[1]}"
    return f"campine-{campaign_id}"


def _render_report_ui(spec: dict, dossier: dict, hypotheses: list[dict], candidates: list[dict], manifest_time: str) -> str:
    top = candidates[:3]
    primary = candidates[0] if candidates else None
    target_identifier = spec["target"]["identifier"]
    target_label = f"{spec['target']['name']} ({target_identifier})"
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

      <section class="grid">
        <article class="card">
          <div class="section-title">
            <h2>Top Candidates</h2>
            <span class="route">Ranked shortlist</span>
          </div>
          <div class="grid">
            {''.join(candidate_cards) or '<p>No candidates yet.</p>'}
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
    ui_path.write_text(_render_report_ui(spec, dossier, hypotheses, candidates, utc_now()), encoding="utf-8")

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
