# t_1752d5b7 — bounded multi-target PyG/GNN run

Status: PASS for a staged/bounded multi-relation PyG/HeteroData + multi-primary GraphSAGE link-prediction smoke. This is not a full production TxGNN training run, not an all-relation quality claim, and not a canonical KG promotion.

## Source and artifact paths

Reviewable code/report worktree:

- `/Users/jkobject/.openclaw/worktrees/txgnn/t_fdb7423e-pyg-gnn-run`
- branch: `feat/t_fdb7423e-pyg-gnn-run`

Canonical KG source:

- `gs://jouvencekb/kg/v2`

Embedding/fallback artifact roots:

- embedding features root: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features`
- fallback config: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json`

Staged export generated for this task:

- `artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded`
- HeteroData artifact: `artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/heterodata/full_graph.pt`
- HeteroData metadata: `artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/heterodata/full_graph.metadata.json`
- validation report: `artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/validation_report.json`

Multi-target smoke metrics JSON:

- `artifacts/reports/t_1752d5b7_pyg_gnn_multitarget_metrics.json`

Artifact existence/size check:

```text
artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/heterodata/full_graph.pt	1059403071 bytes
artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/heterodata/full_graph.metadata.json	9156 bytes
artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/validation_report.json	685 bytes
artifacts/reports/t_1752d5b7_pyg_gnn_multitarget_metrics.json	19261 bytes
```

## Subset choice and rationale

Chosen canonical relations:

1. `molecule_targets_gene` (`molecule -> gene`) — evaluated primary link-prediction target; continuity with prior bounded drug-target smoke paths and directly relevant to drug-target biology.
2. `disease_associated_gene` (`gene -> disease`) — evaluated primary link-prediction target; adds a second target relation with a different endpoint pair and disease biology context.
3. `molecule_treats_disease` (`molecule -> disease`) — auxiliary therapeutic indication context linking molecules and diseases; included for message passing only in this run.

Caps:

- node types: `molecule`, `gene`, `disease`
- node cap: disabled (`--max-nodes-per-type 0`) so endpoint maps cover full selected node files
- forward edge cap per relation: `2048`
- reverse edges: generated for all selected relations
- evaluated primary relations: `molecule_targets_gene`, `disease_associated_gene`
- per-primary training cap: `1024` positive edges
- per-primary validation/test positives: deterministic heldout splits from the selected 2,048 edges, here 409 validation and 409 test positives per primary relation

Auxiliary edge handling: for each evaluated primary relation, that primary relation's validation/test positive forward edges and corresponding reverse edges are removed from the message-passing graph. Non-selected relations remain as auxiliary message-passing context, including their reverse edges. Thus `molecule_treats_disease` is auxiliary for both primary evaluations; `disease_associated_gene` is auxiliary when evaluating `molecule_targets_gene`; `molecule_targets_gene` is auxiliary when evaluating `disease_associated_gene`.

## Build validation

Observed build validation summary:

```json
{
  "edge_counts": {
    "disease_associated_gene": 2048,
    "molecule_targets_gene": 2048,
    "molecule_treats_disease": 2048
  },
  "error_count": 0,
  "kg_root": "gs://jouvencekb/kg/v2",
  "node_counts": {
    "disease": 41859,
    "gene": 267830,
    "molecule": 31007
  },
  "status": "pass",
  "warning_count": 0
}
```

Feature and edge-attribute policy summary from HeteroData metadata:

```json
{
  "edge": {
    "('disease', 'rev_disease_associated_gene', 'gene')": {"dim": 256, "fallback_rows": 2048, "real_rows": 0},
    "('disease', 'rev_molecule_treats_disease', 'molecule')": {"dim": 256, "fallback_rows": 2048, "real_rows": 0},
    "('gene', 'disease_associated_gene', 'disease')": {"dim": 256, "fallback_rows": 2048, "real_rows": 0},
    "('gene', 'rev_molecule_targets_gene', 'molecule')": {"dim": 256, "fallback_rows": 2032, "real_rows": 16},
    "('molecule', 'molecule_targets_gene', 'gene')": {"dim": 256, "fallback_rows": 2032, "real_rows": 16},
    "('molecule', 'molecule_treats_disease', 'disease')": {"dim": 256, "fallback_rows": 2048, "real_rows": 0}
  },
  "node": {
    "disease": {"dim": 768, "fallback_rows": 41843, "real_rows": 16},
    "gene": {"dim": 768, "fallback_rows": 267814, "real_rows": 16},
    "molecule": {"dim": 768, "fallback_rows": 30991, "real_rows": 16}
  }
}
```

The fallback policy is model-side learned fallback only; fallback rows are not fabricated canonical/source-derived embeddings.

## Graph sizes

```json
{
  "forward_edge_counts": {
    "disease_associated_gene": 2048,
    "molecule_targets_gene": 2048,
    "molecule_treats_disease": 2048
  },
  "node_counts": {
    "disease": 41859,
    "gene": 267830,
    "molecule": 31007
  },
  "edge_type_count_with_reverses": 6,
  "node_feature_shapes": {
    "disease": [41859, 768],
    "gene": [267830, 768],
    "molecule": [31007, 768]
  }
}
```

## Per-primary split, leak checks, and metrics

### `molecule_targets_gene`

```json
{
  "split_counts": {
    "train_positive_edges": 1024,
    "train_negative_edges": 1024,
    "valid_positive_edges": 409,
    "valid_negative_edges": 409,
    "test_positive_edges": 409,
    "test_negative_edges": 409
  },
  "metrics": {
    "initial_train_loss": 0.6884448528289795,
    "final_train_loss": 0.6702393293380737,
    "valid_loss": 0.6508840322494507,
    "valid_accuracy": 0.8924205303192139,
    "test_loss": 0.6513704061508179,
    "test_accuracy": 0.8887530565261841,
    "runtime_seconds": 12.614346,
    "peak_rss_mb": 3213.406
  },
  "required_checks": {
    "heldout_edges_removed_from_message_passing": true,
    "message_passing_edge_count_matches_train_split": true,
    "reverse_edges_are_transpose": true,
    "split_endpoint_bounds": true,
    "selected_edge_attr_consumed_by_predictor": true,
    "edge_attr_tensors_present": true
  }
}
```

### `disease_associated_gene`

```json
{
  "split_counts": {
    "train_positive_edges": 1024,
    "train_negative_edges": 1024,
    "valid_positive_edges": 409,
    "valid_negative_edges": 409,
    "test_positive_edges": 409,
    "test_negative_edges": 409
  },
  "metrics": {
    "initial_train_loss": 0.6977522373199463,
    "final_train_loss": 0.6788227558135986,
    "valid_loss": 0.6677640676498413,
    "valid_accuracy": 0.5378972887992859,
    "test_loss": 0.6689242124557495,
    "test_accuracy": 0.5427873134613037,
    "runtime_seconds": 3.388452,
    "peak_rss_mb": 4432.25
  },
  "required_checks": {
    "heldout_edges_removed_from_message_passing": true,
    "message_passing_edge_count_matches_train_split": true,
    "reverse_edges_are_transpose": true,
    "split_endpoint_bounds": true,
    "selected_edge_attr_consumed_by_predictor": true,
    "edge_attr_tensors_present": true
  }
}
```

Overall smoke runtime/memory from metrics JSON:

```json
{
  "runtime_seconds": 17.618021,
  "peak_rss_mb": 4432.25,
  "status": "pass"
}
```

The validation/test accuracies are smoke metrics on sampled negatives. They should not be interpreted as production therapeutic-prediction or biology-quality metrics.

## Code change summary

`manage_db.run_pyg_gnn_smoke` now supports `--primary-relations`/`--relations` for multiple evaluated primary relations. It runs a separate leak-free heldout split/training/evaluation pass per selected primary relation, persists per-primary payloads under `primary_results`, and records aggregate runtime/memory in the metrics JSON. Existing single-primary `--relation` behavior remains supported.

`tests/test_build_pyg_export.py` adds a unit smoke covering two evaluated primary relations and asserts per-primary leak checks, edge-attribute consumption, and persisted metrics.

## Exact commands and observed output

Build the multi-relation export:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded \
  --node-types molecule gene disease \
  --relations molecule_targets_gene disease_associated_gene molecule_treats_disease \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 2048 \
  --embedding-features-root /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features \
  --learned-fallback-config-path /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json \
  --build-name t_1752d5b7_pyg_gnn_multitarget_bounded \
  --sort-node-ids
```

Observed build output:

```text
edge_counts: disease_associated_gene=2048, molecule_targets_gene=2048, molecule_treats_disease=2048
node_counts: disease=41859, gene=267830, molecule=31007
validation_report: artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded/validation_report.json
```

Run the multi-primary GNN smoke:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_1752d5b7_pyg_gnn_multitarget_bounded \
  --primary-relations molecule_targets_gene disease_associated_gene \
  --epochs 2 \
  --hidden-channels 8 \
  --max-train-edges 1024 \
  --seed 175257 \
  --output-json artifacts/reports/t_1752d5b7_pyg_gnn_multitarget_metrics.json
```

Observed smoke output: `status=pass`; metrics JSON written to `artifacts/reports/t_1752d5b7_pyg_gnn_multitarget_metrics.json` with per-primary `molecule_targets_gene` and `disease_associated_gene` results.

Targeted verification:

```bash
uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py tests/test_build_pyg_export.py
uv run --group dev --group gnn pytest tests/test_build_pyg_export.py -q
```

Observed py_compile output:

```text
warning: `VIRTUAL_ENV=/Users/jkobject/.hermes/hermes-agent/venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
```

Observed pytest output:

```text
warning: `VIRTUAL_ENV=/Users/jkobject/.hermes/hermes-agent/venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........                                                                 [100%]
8 passed in 3.23s
```

## Caveats

- Bounded staged run only: 3 canonical forward relations capped to 2,048 edges each, not full/all-relation TxGNN training.
- Only two selected relations are evaluated as primaries in this run: `molecule_targets_gene` and `disease_associated_gene`. `molecule_treats_disease` is auxiliary message-passing context.
- Real embedding coverage remains sparse; fallback rows are model-side learned fallback features and must be reported as such.
- No inferred-edge materialization or ablation was attempted, per the active pause guard.
- No canonical KG promotion was performed.
