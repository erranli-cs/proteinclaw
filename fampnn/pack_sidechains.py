"""
Minimal sidechain packing with FAMPNN 3.0.

Given a PDB with backbone + sequence (no sidechains), packs sidechains using
the fampnn_0_3 model (FAMPNN 3.0 for sequence design).

Usage:
    python pack_sidechains.py input.pdb output.pdb [checkpoint]
"""
import sys
import torch
from pathlib import Path

from fampnn import sampling_utils
from fampnn.data.data import load_feats_from_pdb, process_single_pdb
from fampnn.model.sd_model import SeqDenoiser

_KEYS = ["x", "aatype", "seq_mask", "missing_atom_mask", "residue_index", "chain_index"]
_NUM_STEPS = 50


def _build_scd_inputs(num_steps: int, device) -> dict:
    t_scd = sampling_utils.get_timesteps_from_schedule(
        num_steps=num_steps, mode="linear", t_start=0.0, t_end=1.0
    ).to(device)
    return {
        "num_steps": num_steps,
        "timesteps": t_scd[None],   # [1, T] – broadcasts over batch dimension
        "step_scale": 1.5,
        "churn_cfg": {
            "s_churn": 0, "s_noise": 1.0,
            "s_t_min": 0.01, "s_t_max": 50.0,
            "num_steps": num_steps,
        },
    }


def _load_model(checkpoint: str, device):
    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    model = SeqDenoiser(ckpt["model_cfg"]).to(device).eval()
    model.load_state_dict(ckpt["state_dict"])
    return model


def pack_sidechains(pdb_in: str, pdb_out: str, checkpoint: str = "weights/fampnn_0_3.pt"):
    """Pack sidechains for a single PDB (loads model each call; use
    pack_sidechains_batch for processing many PDBs efficiently)."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = _load_model(checkpoint, device)

    data   = load_feats_from_pdb(pdb_in)
    single = process_single_pdb(data)
    batch  = {k: single[k].unsqueeze(0).to(device) for k in _KEYS}

    scd_inputs = _build_scd_inputs(_NUM_STEPS, device)

    with torch.no_grad():
        x_denoised, aatype_denoised, aux = model.sidechain_pack(
            batch["x"], batch["aatype"],
            seq_mask=batch["seq_mask"],
            missing_atom_mask=batch["missing_atom_mask"],
            residue_index=batch["residue_index"],
            chain_index=batch["chain_index"],
            scd_inputs=scd_inputs,
        )

    samples = {
        "x_denoised":        x_denoised,
        "seq_mask":          batch["seq_mask"],
        "missing_atom_mask": torch.zeros_like(batch["missing_atom_mask"]),
        "residue_index":     batch["residue_index"],
        "chain_index":       batch["chain_index"],
        "pred_aatype":       aatype_denoised,
        "psce":              aux["psce"],
    }

    Path(pdb_out).parent.mkdir(parents=True, exist_ok=True)
    SeqDenoiser.save_samples_to_pdb(samples, [pdb_out])
    print(f"Saved packed structure to {pdb_out}")


def pack_sidechains_batch(
    pdb_in_list: list,
    pdb_out_list: list,
    checkpoint: str = "weights/fampnn_0_3.pt",
    batch_size: int = 32,
) -> None:
    """Pack sidechains for many PDBs efficiently.

    Loads the model checkpoint exactly once, then processes PDBs in batches
    of `batch_size`.  Within each batch, proteins are zero-padded to the
    length of the longest protein so they can be forwarded together through
    the GPU in a single call.  Padded positions have seq_mask=0 and are
    excluded from the output PDB by the atom-mask logic in save_samples_to_pdb.

    Args:
        pdb_in_list:  Input PDB paths (backbone + sequence, no sidechains).
        pdb_out_list: Corresponding output paths (must be same length).
        checkpoint:   Path to FAMPNN weights (.pt).
        batch_size:   Number of structures per GPU forward pass.  Reduce if
                      you run out of GPU memory on very long proteins.
    """
    assert len(pdb_in_list) == len(pdb_out_list), "input/output lists must have equal length"
    if not pdb_in_list:
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ── Load model ONCE ──────────────────────────────────────────────────────
    print(f"[fampnn] Loading model from {checkpoint} ...")
    model      = _load_model(checkpoint, device)
    scd_inputs = _build_scd_inputs(_NUM_STEPS, device)

    total = len(pdb_in_list)
    for batch_start in range(0, total, batch_size):
        batch_in  = pdb_in_list [batch_start : batch_start + batch_size]
        batch_out = pdb_out_list[batch_start : batch_start + batch_size]
        B = len(batch_in)

        # ── Load + process each PDB in this mini-batch ───────────────────────
        singles = []
        for pdb in batch_in:
            data   = load_feats_from_pdb(pdb)
            single = process_single_pdb(data)
            singles.append({k: single[k] for k in _KEYS})

        # ── Pad all to max length, stack into [B, N_max, ...] ────────────────
        max_len = max(s["seq_mask"].shape[0] for s in singles)
        batched = {}
        for k in _KEYS:
            padded = []
            for s in singles:
                t = s[k]                               # [N, ...]
                n = t.shape[0]
                if n < max_len:
                    pad = torch.zeros((max_len - n,) + t.shape[1:], dtype=t.dtype)
                    t = torch.cat([t, pad], dim=0)
                padded.append(t)
            batched[k] = torch.stack(padded, dim=0).to(device)  # [B, N_max, ...]

        # ── Single batched forward pass ──────────────────────────────────────
        with torch.no_grad():
            x_denoised, aatype_denoised, aux = model.sidechain_pack(
                batched["x"], batched["aatype"],
                seq_mask=batched["seq_mask"],
                missing_atom_mask=batched["missing_atom_mask"],
                residue_index=batched["residue_index"],
                chain_index=batched["chain_index"],
                scd_inputs=scd_inputs,
            )

        samples = {
            "x_denoised":        x_denoised,
            "seq_mask":          batched["seq_mask"],
            "missing_atom_mask": torch.zeros_like(batched["missing_atom_mask"]),
            "residue_index":     batched["residue_index"],
            "chain_index":       batched["chain_index"],
            "pred_aatype":       aatype_denoised,
            "psce":              aux["psce"],
        }

        for out_path in batch_out:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        SeqDenoiser.save_samples_to_pdb(samples, batch_out)
        print(f"[fampnn] Packed {B} structures "
              f"(#{batch_start + 1}–{batch_start + B} of {total})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pack_sidechains.py input.pdb output.pdb [checkpoint]")
        sys.exit(1)
    pdb_in = sys.argv[1]
    pdb_out = sys.argv[2]
    checkpoint = sys.argv[3] if len(sys.argv) > 3 else "weights/fampnn_0_3.pt"
    pack_sidechains(pdb_in, pdb_out, checkpoint)
