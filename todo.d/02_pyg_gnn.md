# 02 — PyG / GNN

## Current state

- `t_dc23f241` — PyG design: `design done`.
- `t_a28b941e` — bounded PyG export pilot: `pilot accepted`.
  - Strict pilot: `gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict`.
  - Outputs `.npy`/metadata + maps for a bounded representative graph.
  - Not a full KG export.
  - Not a running PyG/GNN training pipeline.

## Not done yet

- `t_015bd9a4` — full/representative KG PyG export plus actual GNN smoke/training.
- `t_1d1eb3a1` — validate full PyG/HeteroData export + GNN runtime.
- `t_468db80e` — review full PyG/HeteroData + GNN runtime.

## Definition of done

This phase is not done until:

1. `torch`/`torch_geometric` runtime is installed or exact blocker recorded.
2. Actual `HeteroData`/`.pt` or equivalent runtime object exists.
3. A GNN smoke/training job actually runs on the exported graph.
4. Full KG path exists or the remaining gap to full KG is quantified and accepted.
