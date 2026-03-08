#!/usr/bin/env python3
"""
PPIFlow Multi-GPU Pipeline
==========================
All three phases — backbone sampling, ProteinMPNN inverse folding, and FAMPNN
sidechain packing — are distributed across available GPUs in parallel.

Usage:
    python pipeline_multi_gpu.py --config <yaml> --output <dir> --num_samples <n>
    python pipeline_multi_gpu.py --config <yaml> --output <dir> --num_samples <n> --num_gpus 4
    python pipeline_multi_gpu.py --config <yaml> --output <dir> --num_samples <n> --resume

GPU selection:
    Respects CUDA_VISIBLE_DEVICES set before calling this script; only those
    physical GPUs are used.  --num_gpus further limits the count.

Resume:
    --resume loads pipeline_state.json from <output> and skips phases that
    already completed (binder_gen → protein_mpnn → fampnn).

Logs written to <output>/:
    worker_{i}_gpu{id}.log        – backbone sampling
    mpnn_worker_{i}_gpu{id}.log   – ProteinMPNN
    fampnn_worker_{i}_gpu{id}.log – FAMPNN
"""

import argparse
import glob as _glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import yaml


# ---------------------------------------------------------------------------
# GPU selection
# ---------------------------------------------------------------------------

def get_available_gpus() -> list[int]:
    """Return GPU indices to use, honouring CUDA_VISIBLE_DEVICES.

    If CUDA_VISIBLE_DEVICES is set, its entries are used as-is
    (e.g. "1,2,3,4,5,6,7" → [1,2,3,4,5,6,7]).  Falls back to
    querying nvidia-smi when the variable is absent.
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
        print("[multi_gpu] Warning: nvidia-smi unavailable, defaulting to GPU 0.")
        return [0]


def _resolve_gpus(cli_num_gpus: int | None) -> list[int]:
    gpus = get_available_gpus()
    return gpus[:cli_num_gpus] if cli_num_gpus else gpus


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _split_list(lst: list, n: int) -> list[list]:
    """Split lst into at most n non-empty chunks."""
    base, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for j in range(n):
        size = base + (1 if j < rem else 0)
        if size:
            chunks.append(lst[i : i + size])
        i += size
    return chunks


def _launch_and_wait(jobs: list[tuple]) -> None:
    """Launch (cmd, env, log_path, label) jobs in parallel and wait.

    Prints status for each job; calls sys.exit(1) if any fail.
    """
    procs = []
    for cmd, env, log_path, label in jobs:
        print(f"[multi_gpu] Launching {label}  →  {log_path}")
        with open(log_path, "w") as lf:
            proc = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        procs.append((proc, log_path, label))

    any_failed = False
    for proc, log_path, label in procs:
        rc = proc.wait()
        if rc == 0:
            print(f"[multi_gpu] {label}: OK")
        else:
            print(f"[multi_gpu] {label}: FAILED (exit {rc})  →  {log_path}")
            any_failed = True

    if any_failed:
        print("[multi_gpu] One or more workers failed – aborting.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Phase 1: backbone sampling
# ---------------------------------------------------------------------------

def run_sampling(cli, cfg, gpus, state, pipeline_script, worker_cfg_path) -> None:
    if state.is_done("binder_gen"):
        print("[multi_gpu] Skipping backbone sampling (already done).")
        return

    name = cfg.get("name", "design")
    n_gpus = min(len(gpus), cli.num_samples)
    active_gpus = gpus[:n_gpus]
    base, rem = divmod(cli.num_samples, n_gpus)
    sample_counts = [base + (1 if i < rem else 0) for i in range(n_gpus)]

    print(f"[multi_gpu] Sampling  GPUs={active_gpus}  samples/GPU={sample_counts}")

    jobs, worker_dirs = [], []
    for i, (gpu_id, n) in enumerate(zip(active_gpus, sample_counts)):
        wdir     = os.path.join(cli.output, f"_worker_{i}")
        log_path = os.path.join(cli.output, f"worker_{i}_gpu{gpu_id}.log")
        worker_dirs.append(wdir)
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        cmd = [
            sys.executable, pipeline_script,
            "--config",      worker_cfg_path,
            "--output",      wdir,
            "--num_samples", str(n),
            "--resume",
        ]
        jobs.append((cmd, env, log_path, f"sampling worker {i} GPU={gpu_id} n={n}"))

    _launch_and_wait(jobs)

    # Merge backbone PDBs into the final output directory
    print(f"\n[multi_gpu] Merging backbone PDBs → {cli.output}")
    pdb_re = re.compile(rf"^{re.escape(name)}_\d+\.pdb$")
    global_idx = 0
    for wdir in worker_dirs:
        if not os.path.isdir(wdir):
            continue
        for pdb_file in sorted(f for f in os.listdir(wdir) if pdb_re.match(f)):
            shutil.copy2(
                os.path.join(wdir, pdb_file),
                os.path.join(cli.output, f"{name}_{global_idx}.pdb"),
            )
            global_idx += 1
    print(f"[multi_gpu] Merged {global_idx} PDB(s).")

    if global_idx == 0:
        print("[multi_gpu] No PDBs found – check worker logs.")
        sys.exit(1)

    state.mark_done("binder_gen")


# ---------------------------------------------------------------------------
# Phase 2: ProteinMPNN (parallel across GPUs)
# ---------------------------------------------------------------------------

def run_mpnn_parallel(output_dir: str, cfg: dict, gpus: list, state, repo_root: str) -> None:
    if not cfg.get("mpnn_weights"):
        print("[multi_gpu] mpnn_weights not set – skipping MPNN.")
        return

    # Fixed-positions CSV (fast CPU step, done once)
    if state.is_done("fixed_positions_csv"):
        csv_path = os.path.join(output_dir, "mpnn_fixed_positions.csv")
        print("[multi_gpu] Skipping fixed_positions_csv (already done).")
    else:
        from helper_functions import create_mpnn_fixed_positions_csv
        csv_path = create_mpnn_fixed_positions_csv(output_dir)
        state.mark_done("fixed_positions_csv")

    from helper_functions import _detect_designed_chains, mpnn_fasta_to_csv, graft_sequences_to_pdbs

    designed_chains = _detect_designed_chains(output_dir)
    if designed_chains:
        chain_list = " ".join(designed_chains)
    else:
        chain_list = cfg.get("binder_chain", "")
        if not chain_list:
            print("[multi_gpu] Could not determine designed chain – skipping MPNN.")
            return

    if state.is_done("protein_mpnn"):
        print("[multi_gpu] Skipping protein_mpnn (already done).")
        return

    all_pdbs = sorted(_glob.glob(os.path.join(output_dir, "*.pdb")))
    if not all_pdbs:
        print(f"[multi_gpu] No backbone PDBs found in {output_dir}.")
        return

    n_workers = min(len(gpus), len(all_pdbs))
    pdb_chunks = _split_list(all_pdbs, n_workers)
    print(f"\n[multi_gpu] ProteinMPNN  GPUs={gpus[:n_workers]}  "
          f"PDBs/GPU={[len(c) for c in pdb_chunks]}")

    mpnn_dir = os.path.join(repo_root, "ProteinMPNN")
    tmpdir = tempfile.mkdtemp(prefix="ppiflow_mpnn_")
    worker_out_dirs, jobs = [], []

    for i, (gpu_id, chunk) in enumerate(zip(gpus[:n_workers], pdb_chunks)):
        # Symlink dir so each worker sees only its PDB subset
        pdb_subdir = os.path.join(tmpdir, f"pdbs_{i}")
        os.makedirs(pdb_subdir)
        for pdb in chunk:
            os.symlink(os.path.abspath(pdb),
                       os.path.join(pdb_subdir, os.path.basename(pdb)))

        worker_out = os.path.join(tmpdir, f"out_{i}")
        os.makedirs(worker_out)
        worker_out_dirs.append(worker_out)

        # Write an inline Python script for this worker
        lines = [
            "import sys",
            f"sys.path.insert(0, {repr(repo_root)})",
            f"sys.path.insert(0, {repr(mpnn_dir)})",
            "import protein_mpnn_run",
            "from argparse import Namespace",
            "args = Namespace(",
            f"    folder_with_pdbs_path={repr(pdb_subdir)},",
            f"    out_folder={repr(worker_out)},",
            f"    path_to_model_weights={repr(cfg['mpnn_weights'])},",
            f"    chain_list={repr(chain_list)},",
            f"    position_list={repr(csv_path)},",
            f"    model_name={repr(cfg.get('model_name', 'v_48_020'))},",
            f"    num_seq_per_target={int(cfg.get('num_seqs_per_target', 8))},",
            f"    batch_size={int(cfg.get('batch_size', 1))},",
            f"    sampling_temp={repr(str(cfg.get('sampling_temp', '0.1')))},",
            f"    omit_AAs={repr(cfg.get('mpnn_omit_AAs', 'X'))},",
            "    suppress_print=0, ca_only=False, use_soluble_model=False,",
            "    seed=0, backbone_noise=0.00, max_length=200000,",
            "    save_score=0, save_probs=0, score_only=0,",
            "    path_to_fasta='', conditional_probs_only=0,",
            "    conditional_probs_only_backbone=0, unconditional_probs_only=0,",
            "    pdb_path='', pdb_path_chains='', jsonl_path='',",
            "    chain_id_jsonl='', fixed_positions_jsonl='',",
            "    bias_AA_jsonl='', bias_by_res_jsonl='', omit_AA_jsonl='',",
            "    pssm_jsonl='', pssm_multi=0.0, pssm_threshold=0.0,",
            "    pssm_log_odds_flag=0, pssm_bias_flag=0,",
            "    tied_positions_jsonl='',",
            ")",
            "protein_mpnn_run.main(args)",
        ]
        script_path = os.path.join(tmpdir, f"mpnn_worker_{i}.py")
        with open(script_path, "w") as f:
            f.write("\n".join(lines) + "\n")

        log_path = os.path.join(output_dir, f"mpnn_worker_{i}_gpu{gpu_id}.log")
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        jobs.append(([sys.executable, script_path], env, log_path,
                     f"MPNN worker {i} GPU={gpu_id} n={len(chunk)}"))

    _launch_and_wait(jobs)

    # Merge per-worker FASTA files into mpnn_output/seqs/
    merged_seqs_dir = os.path.join(output_dir, "mpnn_output", "seqs")
    os.makedirs(merged_seqs_dir, exist_ok=True)
    for worker_out in worker_out_dirs:
        seqs_dir = os.path.join(worker_out, "seqs")
        if os.path.isdir(seqs_dir):
            for fname in os.listdir(seqs_dir):
                shutil.copy2(os.path.join(seqs_dir, fname),
                             os.path.join(merged_seqs_dir, fname))

    # fasta→csv and graft (CPU, single process)
    seqs_csv = os.path.join(output_dir, "mpnn_output", "seqsfinal_result.csv")
    mpnn_fasta_to_csv(
        input_dirs=[merged_seqs_dir],
        output_csv=seqs_csv,
        suffix=".pdb",
    )
    graft_sequences_to_pdbs(
        output_dir=output_dir,
        csv_path=seqs_csv,
        designed_chains=designed_chains if designed_chains else chain_list.split(),
    )
    state.mark_done("protein_mpnn")


# ---------------------------------------------------------------------------
# Phase 3: FAMPNN sidechain packing (parallel across GPUs)
# ---------------------------------------------------------------------------

def run_fampnn_parallel(output_dir: str, cfg: dict, gpus: list, state, repo_root: str) -> None:
    if not cfg.get("fampnn_weights"):
        print("[multi_gpu] fampnn_weights not set – skipping FAMPNN.")
        return

    if state.is_done("fampnn"):
        print("[multi_gpu] Skipping fampnn (already done).")
        return

    mpnn_out_dir  = os.path.join(output_dir, "mpnn_output")
    fampnn_out_dir = os.path.join(output_dir, "fampnn_designs")
    os.makedirs(fampnn_out_dir, exist_ok=True)

    all_pdbs = sorted(_glob.glob(os.path.join(mpnn_out_dir, "*.pdb")))
    if not all_pdbs:
        print(f"[multi_gpu] No grafted PDBs found in {mpnn_out_dir}.")
        return

    n_workers = min(len(gpus), len(all_pdbs))
    pdb_chunks = _split_list(all_pdbs, n_workers)
    print(f"\n[multi_gpu] FAMPNN  GPUs={gpus[:n_workers]}  "
          f"PDBs/GPU={[len(c) for c in pdb_chunks]}")

    fampnn_dir  = os.path.join(repo_root, "fampnn")
    checkpoint  = cfg["fampnn_weights"]
    tmpdir      = tempfile.mkdtemp(prefix="ppiflow_fampnn_")
    jobs        = []

    for i, (gpu_id, chunk) in enumerate(zip(gpus[:n_workers], pdb_chunks)):
        out_files = [os.path.join(fampnn_out_dir, os.path.basename(p)) for p in chunk]
        lines = [
            "import sys, os",
            f"sys.path.insert(0, {repr(fampnn_dir)})",
            "from pack_sidechains import pack_sidechains_batch",
            f"pdb_in  = {repr(chunk)}",
            f"pdb_out = {repr(out_files)}",
            f"ckpt    = {repr(checkpoint)}",
            "pack_sidechains_batch(pdb_in, pdb_out, ckpt)",
            "print('[fampnn] Worker done:', len(pdb_in), 'structures packed')",
        ]
        script_path = os.path.join(tmpdir, f"fampnn_worker_{i}.py")
        with open(script_path, "w") as f:
            f.write("\n".join(lines) + "\n")

        log_path = os.path.join(output_dir, f"fampnn_worker_{i}_gpu{gpu_id}.log")
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        jobs.append(([sys.executable, script_path], env, log_path,
                     f"FAMPNN worker {i} GPU={gpu_id} n={len(chunk)}"))

    _launch_and_wait(jobs)
    state.mark_done("fampnn")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PPIFlow multi-GPU pipeline – all phases parallelised.",
    )
    parser.add_argument("--config",      required=True,  help="Path to pipeline YAML config")
    parser.add_argument("--output",      required=True,  help="Final output directory")
    parser.add_argument("--num_samples", type=int, default=10, help="Total samples to generate")
    parser.add_argument("--num_gpus",    type=int, default=None,
                        help="Number of GPUs to use (default: all available / all in CUDA_VISIBLE_DEVICES)")
    parser.add_argument("--resume",      action="store_true",
                        help="Load existing pipeline_state.json and skip completed phases")
    cli = parser.parse_args()

    with open(cli.config) as f:
        cfg = yaml.safe_load(f)

    gpus = _resolve_gpus(cli.num_gpus)
    print(f"[multi_gpu] GPUs        : {gpus}")
    print(f"[multi_gpu] Total samples: {cli.num_samples}")
    print(f"[multi_gpu] Resume       : {cli.resume}")

    os.makedirs(cli.output, exist_ok=True)
    repo_root = os.path.dirname(os.path.abspath(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from helper_functions import PipelineState
    state = PipelineState(cli.output, cfg, resume=cli.resume)

    # Worker config: strip MPNN + FAMPNN (handled in parallel here, not per worker)
    worker_cfg = {k: v for k, v in cfg.items() if k not in ("mpnn_weights", "fampnn_weights")}
    tmpdir = tempfile.mkdtemp(prefix="ppiflow_mgpu_")
    worker_cfg_path = os.path.join(tmpdir, "worker_config.yaml")
    with open(worker_cfg_path, "w") as f:
        yaml.dump(worker_cfg, f)

    pipeline_script = os.path.join(repo_root, "pipeline.py")

    # ── Phase 1: backbone sampling ───────────────────────────────────────────
    run_sampling(cli, cfg, gpus, state, pipeline_script, worker_cfg_path)

    # ── Phase 2: ProteinMPNN ─────────────────────────────────────────────────
    run_mpnn_parallel(cli.output, cfg, gpus, state, repo_root)

    # ── Phase 3: FAMPNN ──────────────────────────────────────────────────────
    run_fampnn_parallel(cli.output, cfg, gpus, state, repo_root)

    print("\n[multi_gpu] All done.")


if __name__ == "__main__":
    main()
