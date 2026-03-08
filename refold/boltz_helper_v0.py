import os
import sys
import glob
from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import PPBuilder

# Target sequence (chain A in output YAML)
target_seq = "NTTVFQGVAGQSLQVSCPYDSMKHWGRRKAWCRQLGEKGPCQRVVSTHNLWLLSFLRRWNGSTAITDDTLGGTLTITLRNLQPHDAGLYQCQSLHGSEADTLRKVLVEVLAD"

if len(sys.argv) < 2:
    print("Usage: python boltz_helper.py <pdb_dir>")
    sys.exit(1)

pdb_dir = sys.argv[1]
output_dir = 'boltz_yamls'

os.makedirs(output_dir, exist_ok=True)

parser = PDBParser(QUIET=True)
ppb = PPBuilder()


def get_chain_sequences(pdb_path):
    """Return dict of {chain_id: sequence_str} for all chains in a PDB."""
    structure = parser.get_structure('s', pdb_path)
    sequences = {}
    for model in structure:
        for chain in model:
            seq_parts = [str(pp.get_sequence()) for pp in ppb.build_peptides(chain)]
            seq = ''.join(seq_parts)
            if seq:
                sequences[chain.id] = seq
        break  # only first model
    return sequences


pdb_files = sorted(glob.glob(os.path.join(pdb_dir, '*.pdb')))
if not pdb_files:
    raise FileNotFoundError(f"No PDB files found in '{pdb_dir}'")

for pdb_path in pdb_files:
    name = os.path.splitext(os.path.basename(pdb_path))[0]
    chain_seqs = get_chain_sequences(pdb_path)

    target_found = any(seq == target_seq for seq in chain_seqs.values())
    binder_seq = next((seq for seq in chain_seqs.values() if seq != target_seq), None)

    if not target_found:
        print(f"WARNING: target_seq not found in {pdb_path}. Skipping.")
        continue
    if binder_seq is None:
        print(f"WARNING: No binder chain found in {pdb_path} (all chains match target). Skipping.")
        continue

    yaml_text = f"""version: 1
sequences:
  - protein:
      id: A
      sequence: {target_seq}
      msa: /mnt/efs/erran/new_proj/boltz/refold/trem.a3m
  - protein:
      id: B
      sequence: {binder_seq}
      msa: empty
"""

    out_path = os.path.join(output_dir, f"{name}.yaml")
    with open(out_path, 'w') as f:
        f.write(yaml_text)
    print(f"Wrote {out_path}")
