"""
boltz_helper.py – Generate Boltz YAML inputs from PDB files and run
predictions in parallel across multiple GPUs.

Usage:
    python boltz_helper.py <pdb_dir> [options] [-- extra boltz args]

    # YAML creation only:
    python boltz_helper.py fampnn_designs/ --no_predict

    # Predict on 4 GPUs (all in CUDA_VISIBLE_DEVICES):
    CUDA_VISIBLE_DEVICES=0,1,2,3 python boltz_helper.py fampnn_designs/

    # Limit to 2 GPUs, custom output:
    python boltz_helper.py fampnn_designs/ --num_gpus 2 --output my_boltz_out

    # Pass extra boltz flags (after --):
    python boltz_helper.py fampnn_designs/ -- --recycling_steps 10 --diffusion_samples 5
"""

import os
import sys
import glob
import shutil
import subprocess
import tempfile
import argparse
from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import PPBuilder

# ---------------------------------------------------------------------------
# Constants – edit these to match your target protein
# ---------------------------------------------------------------------------

TARGET_SEQ = (
    "NTTVFQGVAGQSLQVSCPYDSMKHWGRRKAWCRQLGEKGPCQRVVSTHNLWLLSFLRRWNGSTAIT"
    "DDTLGGTLTITLRNLQPHDAGLYQCQSLHGSEADTLRKVLVEVLAD"
)
MSA_PATH = "/mnt/efs/erran/new_proj/boltz/refold/trem.a3m"


# ---------------------------------------------------------------------------
# GPU helpers
# ---------------------------------------------------------------------------

def get_available_gpus() -> list:
    """Return GPU indices to use, honouring CUDA_VISIBLE_DEVICES.

    If CUDA_VISIBLE_DEVICES is set (e.g. "1,2,3"), those IDs are returned.
    Falls back to querying nvidia-smi; defaults to [0] on failure.
    """
    cvd = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
    if cvd and cvd.lower() != "nodevfiles":
        return [int(x.strip()) for x in cvd.split(",") if x.strip()]
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            capture_output=True, text=True, check=True,
        )
        return [int(x.strip()) for x in result.stdout.strip().splitlines() if x.strip()]
    except Exception:
        print("[boltz] Warning: nvidia-smi unavailable, defaulting to GPU 0.")
        return [0]


def _split_list(lst: list, n: int) -> list:
    """Split lst into at most n non-empty chunks."""
    base, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for j in range(n):
        size = base + (1 if j < rem else 0)
        if size:
            chunks.append(lst[i : i + size])
        i += size
    return chunks


# ---------------------------------------------------------------------------
# YAML creation
# ---------------------------------------------------------------------------

def _get_chain_sequences(pdb_path: str, parser, ppb) -> dict:
    """Return {chain_id: sequence_str} for all chains in a PDB."""
    structure = parser.get_structure("s", pdb_path)
    sequences = {}
    for model in structure:
        for chain in model:
            seq = "".join(str(pp.get_sequence()) for pp in ppb.build_peptides(chain))
            if seq:
                sequences[chain.id] = seq
        break  # first model only
    return sequences


def create_yaml_files(pdb_dir: str, yaml_dir: str) -> list:
    """Read PDB files, write one Boltz YAML per structure.

    Returns list of paths to the created YAML files.
    """
    os.makedirs(yaml_dir, exist_ok=True)
    parser = PDBParser(QUIET=True)
    ppb = PPBuilder()

    pdb_files = sorted(glob.glob(os.path.join(pdb_dir, "*.pdb")))
    if not pdb_files:
        raise FileNotFoundError(f"No PDB files found in '{pdb_dir}'")

    yaml_paths = []
    for pdb_path in pdb_files:
        name = os.path.splitext(os.path.basename(pdb_path))[0]
        chain_seqs = _get_chain_sequences(pdb_path, parser, ppb)

        target_found = any(seq == TARGET_SEQ for seq in chain_seqs.values())
        binder_seq = next(
            (seq for seq in chain_seqs.values() if seq != TARGET_SEQ), None
        )

        if not target_found:
            print(f"WARNING: target_seq not found in {pdb_path}. Skipping.")
            continue
        if binder_seq is None:
            print(
                f"WARNING: No binder chain found in {pdb_path} "
                "(all chains match target). Skipping."
            )
            continue

        yaml_text = (
            f"version: 1\n"
            f"sequences:\n"
            f"  - protein:\n"
            f"      id: A\n"
            f"      sequence: {TARGET_SEQ}\n"
            f"      msa: {MSA_PATH}\n"
            f"  - protein:\n"
            f"      id: B\n"
            f"      sequence: {binder_seq}\n"
            f"      msa: empty\n"
        )
        out_path = os.path.join(yaml_dir, f"{name}.yaml")
        with open(out_path, "w") as f:
            f.write(yaml_text)
        print(f"Wrote {out_path}")
        yaml_paths.append(out_path)

    return yaml_paths


# ---------------------------------------------------------------------------
# Parallel prediction
# ---------------------------------------------------------------------------

def run_boltz_parallel(
    yaml_paths: list,
    output_dir: str,
    gpus: list,
    extra_args: list,
) -> None:
    """Run ``boltz predict`` on yaml_paths in parallel, one worker per GPU.

    Each worker gets a temporary directory with symlinks to its YAML subset.
    Results are merged into output_dir/predictions/ when all workers finish.
    """
    n_workers = min(len(gpus), len(yaml_paths))
    active_gpus = gpus[:n_workers]
    chunks = _split_list(yaml_paths, n_workers)

    print(
        f"\n[boltz] {len(yaml_paths)} YAMLs  |  "
        f"GPUs {active_gpus}  |  "
        f"per-GPU: {[len(c) for c in chunks]}"
    )

    os.makedirs(output_dir, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="boltz_worker_")
    jobs = []
    worker_out_dirs = []

    for i, (gpu_id, chunk) in enumerate(zip(active_gpus, chunks)):
        # Symlink subset so boltz sees only this worker's files
        yaml_subdir = os.path.join(tmpdir, f"yamls_{i}")
        os.makedirs(yaml_subdir)
        for y in chunk:
            os.symlink(os.path.abspath(y), os.path.join(yaml_subdir, os.path.basename(y)))

        worker_out = os.path.join(tmpdir, f"out_{i}")
        os.makedirs(worker_out)
        worker_out_dirs.append(worker_out)

        cmd = ["boltz", "predict", yaml_subdir, "--out_dir", worker_out] + extra_args
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        log_path = os.path.join(output_dir, f"boltz_worker_{i}_gpu{gpu_id}.log")
        jobs.append((cmd, env, log_path, f"worker {i} GPU={gpu_id} n={len(chunk)}"))

    # Launch all workers in parallel
    procs = []
    for cmd, env, log_path, label in jobs:
        print(f"[boltz] Launching {label}  →  {log_path}")
        with open(log_path, "w") as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        procs.append((proc, log_path, label))

    any_failed = False
    for proc, log_path, label in procs:
        rc = proc.wait()
        if rc == 0:
            print(f"[boltz] {label}: OK")
        else:
            print(f"[boltz] {label}: FAILED (exit {rc})  →  {log_path}")
            any_failed = True

    if any_failed:
        print("[boltz] One or more workers failed – see logs above.")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)

    # Merge worker outputs: predictions/, msa/, processed/
    print(f"\n[boltz] Merging results → {output_dir}")
    merged = 0
    for worker_out in worker_out_dirs:
        for subdir in ("predictions", "msa", "processed"):
            src = os.path.join(worker_out, subdir)
            if not os.path.isdir(src):
                continue
            dest = os.path.join(output_dir, subdir)
            os.makedirs(dest, exist_ok=True)
            for entry in os.listdir(src):
                s = os.path.join(src, entry)
                d = os.path.join(dest, entry)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                    if subdir == "predictions":
                        merged += 1
                else:
                    shutil.copy2(s, d)

    print(f"[boltz] Done – {merged} prediction(s) in '{output_dir}/predictions/'.")
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Boltz YAML inputs from PDB files and run structure "
            "predictions in parallel across multiple GPUs."
        ),
        epilog=(
            "Any arguments after -- are forwarded verbatim to boltz predict, "
            "e.g.:  python boltz_helper.py pdbs/ -- --recycling_steps 10"
        ),
    )
    parser.add_argument(
        "pdb_dir",
        help="Directory containing input PDB files.",
    )
    parser.add_argument(
        "--yaml_dir",
        default="boltz_yamls",
        help="Directory to write Boltz YAML files (default: boltz_yamls).",
    )
    parser.add_argument(
        "--output",
        default="boltz_results",
        help="Output directory for Boltz predictions (default: boltz_results).",
    )
    parser.add_argument(
        "--num_gpus",
        type=int,
        default=None,
        help="Maximum number of GPUs to use (default: all from CUDA_VISIBLE_DEVICES).",
    )
    parser.add_argument(
        "--no_predict",
        action="store_true",
        help="Only create YAML files; skip running boltz predict.",
    )

    args, extra_args = parser.parse_known_args()

    # Step 1: create YAML files from PDBs
    yaml_paths = create_yaml_files(args.pdb_dir, args.yaml_dir)
    if not yaml_paths:
        print("No valid structures found. Exiting.")
        sys.exit(1)
    print(f"\nCreated {len(yaml_paths)} YAML file(s) in '{args.yaml_dir}'.")

    if args.no_predict:
        return

    # Step 2: resolve GPUs
    gpus = get_available_gpus()
    if args.num_gpus:
        gpus = gpus[: args.num_gpus]
    print(f"[boltz] GPUs available: {gpus}")

    # Step 3: run predictions in parallel
    run_boltz_parallel(yaml_paths, args.output, gpus, extra_args)


if __name__ == "__main__":
    main()
