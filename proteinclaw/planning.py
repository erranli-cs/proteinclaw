from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

from proteinclaw.dossier import fetch_europe_pmc_literature, fetch_openalex_literature
from proteinclaw.env import get_env_value_any


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-1-20250805"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5"

TARGET_PROFILES = {
    "P04629": {
        "preferred_structure": "2IFG",
        "target_chain": "A",
        "partner_chains": ["E", "F"],
        "binder_length": "35-45",
        "hotspot_count": 7,
        "recommended_epitope": "NGF-binding interface on the TrkA extracellular domain",
        "mechanism": "Compete with NGF binding to antagonize TrkA activation.",
        "literature_query": "TrkA NTRK1 NGF binding interface receptor extracellular domain",
    }
}


def has_anthropic_key(root: Path) -> bool:
    return bool(get_env_value_any(root, "ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "Antropic"))


def has_openai_key(root: Path) -> bool:
    return bool(get_env_value_any(root, "OPENAI_API_KEY"))


def request_anthropic_plan(root: Path, prompt: str, context: str) -> str:
    api_key = get_env_value_any(root, "ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "Antropic")
    if not api_key:
        raise RuntimeError("Missing Anthropic API key.")
    model = get_env_value_any(root, "ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 700,
            "system": (
                "You are planning a protein minibinder design campaign. "
                "Write concise scientific planning notes with sections titled "
                "Objective, Evidence, Hotspot Rationale, and Planned Route. "
                "Do not invent experiments or structures not present in the input."
            ),
            "messages": [{"role": "user", "content": f"Prompt:\n{prompt}\n\nContext:\n{context}"}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    blocks = payload.get("content") or []
    text_parts = [block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
    return "\n".join(part for part in text_parts if part).strip()


def request_openai_plan(root: Path, prompt: str, context: str) -> str:
    api_key = get_env_value_any(root, "OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OpenAI API key.")
    model = get_env_value_any(root, "OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    body = json.dumps(
        {
            "model": model,
            "input": f"Prompt:\n{prompt}\n\nContext:\n{context}",
            "instructions": (
                "You are planning a protein minibinder design campaign. "
                "Write concise scientific planning notes with sections titled "
                "Objective, Evidence, Hotspot Rationale, and Planned Route. "
                "Do not invent experiments or structures not present in the input."
            ),
            "reasoning": {"effort": "medium"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    text_parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                text_parts.append(content["text"])
    result = "\n".join(part.strip() for part in text_parts if part and part.strip()).strip()
    if not result:
        raise RuntimeError("OpenAI planning returned no text output.")
    return result


def _parse_pdb_atoms(pdb_path: Path) -> dict[tuple[str, int, str], list[tuple[float, float, float]]]:
    residues: dict[tuple[str, int, str], list[tuple[float, float, float]]] = {}
    for line in pdb_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        chain_id = line[21].strip()
        if not chain_id:
            continue
        try:
            residue_number = int(line[22:26].strip())
            residue_name = line[17:20].strip()
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
        except ValueError:
            continue
        key = (chain_id, residue_number, residue_name)
        residues.setdefault(key, []).append((x, y, z))
    return residues


def _interface_hotspots(
    pdb_path: Path,
    target_chain: str,
    partner_chains: list[str],
    hotspot_count: int,
    cutoff: float = 5.0,
) -> list[dict]:
    residues = _parse_pdb_atoms(pdb_path)
    target_residues = {key: atoms for key, atoms in residues.items() if key[0] == target_chain}
    partner_atoms = [atom for key, atoms in residues.items() if key[0] in partner_chains for atom in atoms]
    cutoff_sq = cutoff * cutoff
    ranked: list[dict] = []
    for key, atoms in target_residues.items():
        contacts = 0
        for atom in atoms:
            for partner_atom in partner_atoms:
                distance_sq = (
                    math.pow(atom[0] - partner_atom[0], 2)
                    + math.pow(atom[1] - partner_atom[1], 2)
                    + math.pow(atom[2] - partner_atom[2], 2)
                )
                if distance_sq <= cutoff_sq:
                    contacts += 1
        if contacts:
            ranked.append(
                {
                    "chain": key[0],
                    "residue_number": key[1],
                    "residue_name": key[2],
                    "contact_count": contacts,
                }
            )
    ranked.sort(key=lambda item: (-item["contact_count"], item["residue_number"]))
    return ranked[:hotspot_count]


def _write_single_chain_pdb(source_path: Path, output_path: Path, chain_id: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kept_lines: list[str] = []
    for line in source_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(("ATOM", "HETATM")) and line[21].strip() == chain_id:
            kept_lines.append(line)
        elif line.startswith("TER") and kept_lines:
            kept_lines.append(line)
    kept_lines.append("END")
    output_path.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
    return output_path


def plan_campaign(
    root: Path,
    prompt: str,
    spec: dict,
    dossier: dict,
    campaign_root: Path,
) -> dict:
    profile = TARGET_PROFILES.get(spec["target"]["identifier"])
    residue_constraints = spec.get("constraints", {}).get("target_residue_constraints") or []
    literature_support: list[dict] = []
    warnings: list[str] = []
    hotspot_plan = {
        "preferred_structure": None,
        "target_chain": "A",
        "partner_chains": [],
        "target_input_pdb": None,
        "binder_hotspots": {},
        "ranked_hotspots": [],
        "mechanism": "General antagonist binder design.",
    }
    if profile:
        hotspot_plan["preferred_structure"] = profile["preferred_structure"]
        hotspot_plan["target_chain"] = profile["target_chain"]
        hotspot_plan["partner_chains"] = profile["partner_chains"]
        hotspot_plan["mechanism"] = profile["mechanism"]
        query = profile["literature_query"]
        try:
            europe_hits, _ = fetch_europe_pmc_literature(query, limit=5)
            literature_support.extend(europe_hits)
        except Exception as exc:
            warnings.append(f"Europe PMC planning retrieval failed: {exc}")
        try:
            openalex_hits, _ = fetch_openalex_literature(query, limit=5)
            seen_ids = {item.get('identifier') for item in literature_support}
            literature_support.extend(item for item in openalex_hits if item.get("identifier") not in seen_ids)
        except Exception as exc:
            warnings.append(f"OpenAlex planning retrieval failed: {exc}")

        structure_source = campaign_root / "planning" / f"{profile['preferred_structure']}_full.pdb"
        from proteinclaw.dossier import download_pdb_file

        download_pdb_file(profile["preferred_structure"], structure_source)
        target_only = campaign_root / "planning" / f"{profile['preferred_structure']}_{profile['target_chain']}.pdb"
        _write_single_chain_pdb(structure_source, target_only, profile["target_chain"])
        ranked_hotspots = _interface_hotspots(
            structure_source,
            target_chain=profile["target_chain"],
            partner_chains=profile["partner_chains"],
            hotspot_count=profile["hotspot_count"],
        )
        hotspot_plan["ranked_hotspots"] = ranked_hotspots
        hotspot_plan["binder_hotspots"] = {
            profile["target_chain"]: " ".join(str(item["residue_number"]) for item in ranked_hotspots)
        }
        hotspot_plan["target_input_pdb"] = str(target_only)
        hotspot_plan["recommended_epitope"] = profile["recommended_epitope"]
        hotspot_plan["binder_length"] = profile["binder_length"]
    elif spec["target"]["identifier"].startswith("PDB:"):
        pdb_id = spec["target"].get("pdb_id") or spec["target"]["identifier"].split(":", 1)[1]
        hotspot_plan["preferred_structure"] = pdb_id
        if residue_constraints:
            primary = residue_constraints[0]
            hotspot_plan["target_chain"] = primary["chain"]
            hotspot_plan["binder_hotspots"] = {primary["chain"]: str(primary["residue_number"])}
            hotspot_plan["ranked_hotspots"] = [
                {
                    "chain": primary["chain"],
                    "residue_number": primary["residue_number"],
                    "residue_name": primary.get("residue_name") or "UNK",
                    "contact_count": 1,
                }
            ]
            hotspot_plan["recommended_epitope"] = (
                f"Pocket around chain {primary['chain']} residue {primary['residue_number']}"
            )
            hotspot_plan["mechanism"] = (
                f"Target the local pocket around chain {primary['chain']} residue {primary['residue_number']}."
            )
        hotspot_plan["binder_length"] = "35-55"

    context_lines = [
        f"Target dossier summary: {dossier['summary']}",
        f"Known structures: {', '.join(item['pdb_id'] for item in dossier['structures'][:5])}",
        "Literature highlights:",
    ]
    for item in (literature_support or dossier["literature"])[:5]:
        context_lines.append(f"- {item.get('source')}: {item.get('title')}")
    if hotspot_plan["ranked_hotspots"]:
        context_lines.append(
            "Ranked interface hotspots: "
            + ", ".join(
                f"{item['residue_number']} {item['residue_name']} ({item['contact_count']} contacts)"
                for item in hotspot_plan["ranked_hotspots"]
            )
        )
    if residue_constraints:
        context_lines.append(
            "User-specified residue constraints: "
            + ", ".join(
                f"chain {item['chain']} residue {item['residue_number']}"
                + (f" {item['residue_name']}" if item.get("residue_name") else "")
                for item in residue_constraints
            )
        )
    context = "\n".join(context_lines)
    provider = "deterministic"
    hotspot_rationale = (
        "Use the NGF-facing TrkA interface from 2IFG and prioritize residues "
        + ", ".join(str(item["residue_number"]) for item in hotspot_plan["ranked_hotspots"])
        + "."
        if hotspot_plan["ranked_hotspots"] and profile
        else (
            "Bias designs toward the requested pocket residues: "
            + ", ".join(
                f"{item['chain']}{item['residue_number']}" + (f" {item['residue_name']}" if item.get("residue_name") else "")
                for item in residue_constraints
            )
            + "."
            if residue_constraints
            else "No target-specific hotspot structure was configured, so the route remains generic."
        )
    )
    planning_markdown = (
        "### Objective\n"
        f"Design a minibinder antagonist for {spec['target']['name']}.\n\n"
        "### Evidence\n"
        f"{dossier['summary']}\n\n"
        "### Hotspot Rationale\n"
        + hotspot_rationale
        + "\n\n### Planned Route\nUse literature-backed hotspot selection, then RFdiffusion3, LigandMPNN, and AlphaFold3 scoring."
    )
    if has_openai_key(root):
        try:
            planning_markdown = request_openai_plan(root, prompt, context)
            provider = "openai"
        except Exception as exc:
            warnings.append(f"OpenAI planning failed: {exc}")
    elif has_anthropic_key(root):
        try:
            planning_markdown = request_anthropic_plan(root, prompt, context)
            provider = "anthropic"
        except Exception as exc:
            warnings.append(f"Anthropic planning failed: {exc}")
    return {
        "provider": provider,
        "markdown": planning_markdown,
        "hotspot_plan": hotspot_plan,
        "literature_support": literature_support,
        "warnings": warnings,
    }
