# PicoClaw Memory

## Active Campaigns

### campaign-b589686d11 — TrkA Minibinder
- **Started:** 2026-03-08T21:52:17Z
- **Target:** TrkA / NTRK1 (UniProt P04629)
- **Epitope:** NGF-binding interface on TrkA extracellular d5 domain
- **Structure:** PDB 2IFG (chain A = TrkA, chains E/F = NGF)
- **Route:** RFdiffusion3 → LigandMPNN → AlphaFold3
- **Binder length:** 35–45 residues
- **Mode:** academic
- **Hotspots (from 2IFG 5Å contact analysis):**
  - A297 HIS (64 contacts) — dominant anchor
  - A350 GLN (42 contacts) — secondary anchor
  - A296 MET (41 contacts) — hydrophobic
  - A327 PHE (39 contacts)
  - A333 LEU (35 contacts)
  - A343 HIS (27 contacts)
  - A379 MET (26 contacts)
- **Tamarind RFdiffusion3 job:** `rfd3-2466e12aeb` — status: Running (as of 2026-03-08T21:54)
- **Campaign dir:** artifacts/campaigns/campaign-b589686d11/
- **Provenance:** artifacts/campaigns/campaign-b589686d11/provenance/hotspot-literature.md

## Completed Campaigns
- campaign-be68d264d7
- campaign-9c0e394e4e
- campaign-0fad74fcd4
- campaign-e2842d3e22
- campaign-6185962f6d
- trka_20260308_212429

## Notes
- OpenAI API key: present
- Anthropic API key: present as fallback
- Tamarind API key: present
- All three tools (rfd3, ligandmpnn, alphafold3) route via Tamarind
- alphafold3 is academic-only (commercial_safe=false)
