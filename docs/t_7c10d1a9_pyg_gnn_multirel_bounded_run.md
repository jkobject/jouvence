# t_7c10d1a9 — bounded multi-relation leak-free PyG/GNN baseline

Status: PASS for a staged/bounded multi-relation PyG/HeteroData + GraphSAGE smoke baseline. This is not a full production TxGNN training run, not an all-relation quality claim, and not a canonical KG promotion.

## Source and artifact paths

Reviewable code/report worktree:

- `/Users/jkobject/.openclaw/worktrees/txgnn/t_fdb7423e-pyg-gnn-run`
- branch: `feat/t_fdb7423e-pyg-gnn-run`

Canonical KG source:

- `gs://jouvencekb/kg/v2`

Embedding/fallback artifact roots:

- embedding features root: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features`
- fallback config: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json`

Multi-relation export generated for this task:

- `artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded`
- HeteroData artifact: `artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/heterodata/full_graph.pt`
- HeteroData metadata: `artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/heterodata/full_graph.metadata.json`
- validation report: `artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/validation_report.json`

Multi-relation smoke metrics JSON:

- `artifacts/reports/t_7c10d1a9_pyg_gnn_multirel_bounded_smoke_metrics.json`

Artifact existence/size check:

```text
artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/heterodata/full_graph.pt	 exists=True size_bytes=1059403071
artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/heterodata/full_graph.metadata.json	 exists=True size_bytes=9156
artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded/validation_report.json	 exists=True size_bytes=679
artifacts/reports/t_7c10d1a9_pyg_gnn_multirel_bounded_smoke_metrics.json	 exists=True size_bytes=5314
```

## Subset choice and rationale

Chosen canonical relations:

1. `molecule_targets_gene` (`molecule -> gene`) — primary link-prediction target; continuity with the accepted single-relation `t_98f305c3` path and drug-target relevance.
2. `disease_associated_gene` (`gene -> disease`) — auxiliary disease-gene biology context connecting gene nodes to disease nodes.
3. `molecule_treats_disease` (`molecule -> disease`) — auxiliary therapeutic indication context linking molecule and disease nodes without using inferred-edge ablations.

Caps:

- node types: `molecule`, `gene`, `disease`
- node cap: disabled (`--max-nodes-per-type 0`) so endpoint maps cover full selected node files
- forward edge cap per relation: `2048`
- reverse edges: generated for all selected relations
- primary relation train cap: `1024` positive `molecule_targets_gene` edges
- validation/test: deterministic heldout positives from the selected 2,048 primary edges

This is a primary-relation link-prediction baseline with two canonical auxiliary message-passing relations. It deliberately does not train/evaluate per target relation; the report and metrics record this via `config.relation_role` and `graph_sizes.auxiliary_forward_relations`.

## Build validation

Observed build validation summary:

```json
{
  "checks": {
    "edge_index_shape": true,
    "endpoint_consistency": true,
    "node_id_uniqueness": true,
    "reproducibility_hashes_present": true
  },
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

Feature and edge-attribute policies from HeteroData metadata:

```json
{
  "edge_embedding_policy": {
    "('disease', 'rev_disease_associated_gene', 'gene')": {
      "dim": 256,
      "fallback_rows": 2048,
      "real_rows": 0
    },
    "('disease', 'rev_molecule_treats_disease', 'molecule')": {
      "dim": 256,
      "fallback_rows": 2048,
      "real_rows": 0
    },
    "('gene', 'disease_associated_gene', 'disease')": {
      "dim": 256,
      "fallback_rows": 2048,
      "real_rows": 0
    },
    "('gene', 'rev_molecule_targets_gene', 'molecule')": {
      "dim": 256,
      "fallback_rows": 2032,
      "real_rows": 16
    },
    "('molecule', 'molecule_targets_gene', 'gene')": {
      "dim": 256,
      "fallback_rows": 2032,
      "real_rows": 16
    },
    "('molecule', 'molecule_treats_disease', 'disease')": {
      "dim": 256,
      "fallback_rows": 2048,
      "real_rows": 0
    }
  },
  "node_embedding_policy": {
    "disease": {
      "dim": 768,
      "fallback_rows": 41843,
      "real_rows": 16
    },
    "gene": {
      "dim": 768,
      "fallback_rows": 267814,
      "real_rows": 16
    },
    "molecule": {
      "dim": 768,
      "fallback_rows": 30991,
      "real_rows": 16
    }
  }
}
```

The fallback policy is model-side learned fallback only; fallback rows are not fabricated canonical/source-derived embeddings.

## Graph sizes and split

```json
{
  "graph_sizes": {
    "auxiliary_edge_types": [
      [
        "disease",
        "rev_disease_associated_gene",
        "gene"
      ],
      [
        "gene",
        "disease_associated_gene",
        "disease"
      ],
      [
        "disease",
        "rev_molecule_treats_disease",
        "molecule"
      ],
      [
        "molecule",
        "molecule_treats_disease",
        "disease"
      ]
    ],
    "auxiliary_forward_relations": [
      "disease_associated_gene",
      "molecule_treats_disease"
    ],
    "edge_counts": {
      "('disease', 'rev_disease_associated_gene', 'gene')": 2048,
      "('disease', 'rev_molecule_treats_disease', 'molecule')": 2048,
      "('gene', 'disease_associated_gene', 'disease')": 2048,
      "('gene', 'rev_molecule_targets_gene', 'molecule')": 2048,
      "('molecule', 'molecule_targets_gene', 'gene')": 2048,
      "('molecule', 'molecule_treats_disease', 'disease')": 2048
    },
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
    "primary_edge_count": 2048,
    "primary_edge_type": [
      "molecule",
      "molecule_targets_gene",
      "gene"
    ],
    "primary_message_passing_edge_count": 1024,
    "primary_relation": "molecule_targets_gene",
    "primary_reverse_edge_type": [
      "gene",
      "rev_molecule_targets_gene",
      "molecule"
    ]
  },
  "split_counts": {
    "test_negative_edges": 409,
    "test_positive_edges": 409,
    "train_negative_edges": 1024,
    "train_positive_edges": 1024,
    "valid_negative_edges": 409,
    "valid_positive_edges": 409
  }
}
```

Leak-free split method:

- deterministic random split of selected primary `molecule_targets_gene` edges using seed `71019`;
- validation positives: `min(edge_count // 5, 1024)`, here 409;
- test positives: `min(edge_count // 5, 1024)`, here 409;
- training positives: capped by `--max-train-edges 1024`, here 1024;
- negatives sampled uniformly from molecule/gene index pairs not present in the selected positive edge set;
- validation/test metrics are computed after removing heldout primary forward edges and their reverse edges from the message-passing graph; auxiliary relations remain as context.

## Model architecture

`manage_db.run_pyg_gnn_smoke.HeteroSageLinkPredictor`:

- encoder: two `torch_geometric.nn.HeteroConv` layers;
- per edge type convolution: `SAGEConv` over all selected forward/reverse edge types;
- hidden channels: `8`;
- input channels: `768` from exported node feature tensors;
- decoder: dot-product link predictor on the primary relation;
- edge attributes: selected primary edge attributes are projected with a learned linear layer and added to positive-edge scores;
- optimizer: Adam; loss: binary cross entropy with logits over positive and sampled negative edges.

## Smoke metrics

Observed smoke status: `pass`.

```json
{
  "epochs": 2.0,
  "final_train_loss": 0.6840834617614746,
  "initial_train_loss": 0.6964668035507202,
  "test_accuracy": 0.8251833915710449,
  "test_loss": 0.6764311194419861,
  "train_loss_trace": [
    0.6964668035507202,
    0.6840834617614746
  ],
  "valid_accuracy": 0.8264058828353882,
  "valid_loss": 0.6758055090904236
}
```

Required leak-free/edge-attr validation flags:

```json
{
  "checks": {
    "edge_attr_tensors_present": true,
    "edge_tensors_present": true,
    "feature_tensors_present": true,
    "heldout_edges_removed_from_message_passing": true,
    "message_passing_edge_count_matches_train_split": true,
    "nonempty_splits": true,
    "reverse_edge_count_matches": true,
    "reverse_edges_are_transpose": true,
    "reverse_edges_present": true,
    "selected_edge_attr_consumed_by_predictor": true,
    "selected_edge_endpoint_bounds": true,
    "split_endpoint_bounds": true
  },
  "edge_attr_usage": {
    "all_edge_types_have_edge_attr": true,
    "edge_attr_shapes": {
      "('disease', 'rev_disease_associated_gene', 'gene')": [
        2048,
        256
      ],
      "('disease', 'rev_molecule_treats_disease', 'molecule')": [
        2048,
        256
      ],
      "('gene', 'disease_associated_gene', 'disease')": [
        2048,
        256
      ],
      "('gene', 'rev_molecule_targets_gene', 'molecule')": [
        2048,
        256
      ],
      "('molecule', 'molecule_targets_gene', 'gene')": [
        2048,
        256
      ],
      "('molecule', 'molecule_treats_disease', 'disease')": [
        2048,
        256
      ]
    },
    "selected_edge_attr_consumed_by_predictor": true,
    "selected_edge_attr_shape": [
      2048,
      256
    ],
    "selected_edge_type": [
      "molecule",
      "molecule_targets_gene",
      "gene"
    ]
  }
}
```

The validation/test accuracies are smoke metrics on sampled negatives. They should not be interpreted as production therapeutic-prediction or biology-quality metrics.

## Exact commands

Build the multi-relation export:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded \
  --node-types molecule gene disease \
  --relations molecule_targets_gene disease_associated_gene molecule_treats_disease \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 2048 \
  --embedding-features-root /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features \
  --learned-fallback-config-path /Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json \
  --build-name t_7c10d1a9_pyg_gnn_multirel_bounded \
  --sort-node-ids
```

Run the multi-relation GNN smoke:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_7c10d1a9_pyg_gnn_multirel_bounded \
  --relation molecule_targets_gene \
  --epochs 2 \
  --hidden-channels 8 \
  --max-train-edges 1024 \
  --seed 71019 \
  --output-json artifacts/reports/t_7c10d1a9_pyg_gnn_multirel_bounded_smoke_metrics.json
```

Targeted verification:

```bash
uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py tests/test_build_pyg_export.py
uv run --group dev --group gnn pytest tests/test_build_pyg_export.py -q
```

Observed pytest output:

```text
.......                                                                  [100%]
7 passed in 3.06s
```

## Caveats

- Bounded staged baseline only: 3 canonical forward relations capped to 2,048 edges each, not full/all-relation TxGNN training.
- Link-prediction evaluation is on sampled negatives for primary `molecule_targets_gene`; auxiliary relations are used for message passing but are not independently evaluated in this run.
- Real embedding coverage remains sparse; fallback rows are model-side learned fallback features and must be reported as such.
- No inferred-edge materialization or ablation was attempted, per `t_437925a5` pause.
