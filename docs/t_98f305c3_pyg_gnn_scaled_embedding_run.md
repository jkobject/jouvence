# t_98f305c3 — scaled leak-free real/fallback embedding PyG GNN smoke

Status: PASS for a larger bounded canonical-derived `molecule_targets_gene` PyG/GraphSAGE smoke run.

This is deliberately not a full production TxGNN training run. It scales the accepted corrected `manage_db.run_pyg_gnn_smoke` path from the earlier 64-positive strict embedding subset to a 4,096-positive canonical-derived subset while preserving deterministic train/valid/test splits, leak-free heldout message passing, real/fallback node embeddings, edge attributes, and reviewable metrics.

## Source and artifact paths

Reviewable code/report worktree:

- `/Users/jkobject/.openclaw/worktrees/txgnn/t_fdb7423e-pyg-gnn-run`
- branch: `feat/t_fdb7423e-pyg-gnn-run`

Canonical KG source:

- `gs://jouvencekb/kg/v2`

Embedding/fallback artifact roots:

- embedding features root: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features`
- fallback config: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json`

Scaled export generated for this task:

- `artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096`
- HeteroData artifact: `artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/heterodata/full_graph.pt`
- HeteroData metadata: `artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/heterodata/full_graph.metadata.json`
- validation report: `artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/validation_report.json`

Scaled smoke metrics JSON:

- `artifacts/reports/t_98f305c3_pyg_gnn_embedding_scaled_4096_smoke_metrics.json`

Artifact existence/size check:

```text
artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/heterodata/full_graph.pt	 exists=True size_bytes=926549465
artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/heterodata/full_graph.metadata.json	 exists=True size_bytes=5179
artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/validation_report.json	 exists=True size_bytes=593
artifacts/reports/t_98f305c3_pyg_gnn_embedding_scaled_4096_smoke_metrics.json	 exists=True size_bytes=1861
```

## Subset choice and rationale

Chosen subset: larger canonical-derived `molecule_targets_gene` with real/fallback embeddings and edge attributes.

Caps:

- node types: `molecule`, `gene`
- node cap: disabled (`--max-nodes-per-type 0`) so endpoint maps cover the full selected node files
- relation: `molecule_targets_gene`
- forward edge cap: `4096`, up from the previous 64-edge strict embedding subset
- reverse edges: generated for message passing as `gene --rev_molecule_targets_gene--> molecule`
- train cap: `2048` positive train edges
- validation/test: deterministic heldout positives from the selected 4,096 edges

Memory/runtime rationale:

- The prior corrected path already used full `molecule`/`gene` node maps and 768-dim feature tensors, so increasing the edge cap mainly grows edge indices/edge attributes and split/eval work rather than node tensor dimensionality.
- The produced `full_graph.pt` is about 927 MB, which is feasible on this Mac worktree for a bounded smoke. Larger all-relation/full production training was not attempted in this card because it would require broader memory/runtime planning, relation sampling strategy, and model-quality evaluation beyond a smoke gate.

## Build validation

Observed build output:

```json
{
  "edge_counts": {
    "molecule_targets_gene": 4096
  },
  "manifest": "artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/manifest.json",
  "node_counts": {
    "gene": 267830,
    "molecule": 31007
  },
  "output_root": "artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096",
  "validation_report": "artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096/validation_report.json"
}
```

Validation report summary:

```json
{
  "status": "pass",
  "kg_root": "gs://jouvencekb/kg/v2",
  "node_counts": {
    "gene": 267830,
    "molecule": 31007
  },
  "edge_counts": {
    "molecule_targets_gene": 4096
  },
  "error_count": 0,
  "warning_count": 0,
  "checks": {
    "edge_index_shape": true,
    "endpoint_consistency": true,
    "node_id_uniqueness": true,
    "reproducibility_hashes_present": true
  }
}
```

Feature and edge-attribute shapes/policies from HeteroData metadata:

```json
{
  "node_embedding_policy": {
    "gene": {"dim": 768, "real_rows": 16, "fallback_rows": 267814},
    "molecule": {"dim": 768, "real_rows": 16, "fallback_rows": 30991}
  },
  "edge_embedding_policy": {
    "('molecule', 'molecule_targets_gene', 'gene')": {"dim": 256, "real_rows": 16, "fallback_rows": 4080},
    "('gene', 'rev_molecule_targets_gene', 'molecule')": {"dim": 256, "real_rows": 16, "fallback_rows": 4080}
  }
}
```

The fallback policy is model-side learned fallback only; it is not a fabricated canonical/source-derived embedding.

## Split method

`manage_db.run_pyg_gnn_smoke` performs a deterministic random edge split using seed `983053`:

- random permutation over selected positive `molecule_targets_gene` edges;
- validation positives: `min(edge_count // 5, 1024)`, here 819;
- test positives: `min(edge_count // 5, 1024)`, here 819;
- training positives: capped by `--max-train-edges 2048`, here 2048;
- negative train/validation/test edges are sampled uniformly from molecule/gene index pairs not present in the selected positive edge set;
- train, validation, and test all include equal positive/negative counts;
- validation/test metrics are computed on a leak-free message-passing graph that retains only training positive `molecule_targets_gene` edges and their reverse edges.

Observed split:

```json
{
  "train_positive_edges": 2048,
  "train_negative_edges": 2048,
  "valid_positive_edges": 819,
  "valid_negative_edges": 819,
  "test_positive_edges": 819,
  "test_negative_edges": 819
}
```

## Model architecture

The smoke model is `HeteroSageLinkPredictor` in `manage_db/run_pyg_gnn_smoke.py`:

- encoder: two `torch_geometric.nn.HeteroConv` layers;
- per edge type convolution: `SAGEConv`;
- hidden channels: `8`;
- input channels: `768` from exported node feature tensors;
- decoder: dot-product link predictor over source/destination embeddings;
- edge attributes: projected with a learned linear layer when present, and added to the dot-product score;
- optimizer: Adam;
- loss: binary cross entropy with logits over positive and sampled negative edges.

## Scaled smoke metrics

Observed smoke status: `pass`.

```json
{
  "epochs": 3.0,
  "train_loss_trace": [
    0.6962158679962158,
    0.6899391412734985,
    0.682839035987854
  ],
  "initial_train_loss": 0.6962158679962158,
  "final_train_loss": 0.682839035987854,
  "valid_loss": 0.6783930063247681,
  "valid_accuracy": 0.8638583421707153,
  "test_loss": 0.6784116625785828,
  "test_accuracy": 0.870573878288269
}
```

Required leak-free/edge-attr validation flags:

```json
{
  "heldout_edges_removed_from_message_passing": true,
  "message_passing_edge_count_matches_train_split": true,
  "selected_edge_attr_consumed_by_predictor": true,
  "edge_attr_tensors_present": true,
  "reverse_edges_are_transpose": true,
  "split_endpoint_bounds": true,
  "nonempty_splits": true
}
```

The validation/test accuracies are smoke metrics on sampled negatives. They should not be interpreted as production therapeutic-prediction or biology-quality metrics.

## Exact commands

Build the scaled export:

```bash
mkdir -p artifacts/staged artifacts/reports
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096 \
  --node-types molecule gene \
  --relations molecule_targets_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 4096 \
  --embedding-features-root /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features \
  --learned-fallback-config-path /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json \
  --build-name t_98f305c3_pyg_gnn_embedding_scaled_4096 \
  --sort-node-ids
```

Run the scaled GNN smoke:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_98f305c3_pyg_gnn_embedding_scaled_4096 \
  --relation molecule_targets_gene \
  --epochs 3 \
  --hidden-channels 8 \
  --max-train-edges 2048 \
  --seed 983053 \
  --output-json artifacts/reports/t_98f305c3_pyg_gnn_embedding_scaled_4096_smoke_metrics.json
```

Targeted tests for split/leak-free behavior, export, and smoke CLI:

```bash
uv run --group dev --group gnn pytest tests/test_build_pyg_export.py -q
```

Observed:

```text
.......                                                                  [100%]
7 passed in 3.11s
```

Compile check:

```bash
uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py tests/test_build_pyg_export.py
```

Observed: exit code 0.

## Caveats / not production

- This is a bounded staged subset, not full all-relation KG tensorization or full TxGNN production training.
- Only `molecule_targets_gene` was trained/evaluated.
- The selected forward relation was capped at 4,096 positives; this is larger than the 64-positive strict embedding subset but still not full-scope.
- Real embedding rows are sparse in the staged embedding artifact: 16 real rows for each selected node type and 16 real edge-embedding rows for the selected relation; all other rows use model-side learned fallback tensors.
- Metrics use sampled negatives and a short 3-epoch smoke configuration; they are runtime/leak-free sanity checks, not biological/model-quality benchmarks.
- No canonical KG promotion was performed.
