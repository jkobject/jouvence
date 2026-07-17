# t_fdb7423e — bounded real PyG GNN training run

Status: PASS for a minimal, real, bounded PyG/GraphSAGE link-prediction run on a canonical KG-derived subset.

This is deliberately not a full production TxGNN training run. It is a small staged runtime proof that a real PyG `HeteroData` export can be loaded, split, trained, and evaluated with real/fallback embedding tensors and edge attributes.

## Source and artifact paths

Workspace used for artifact generation:

- `/Users/jkobject/.openclaw/workspace/work/txgnn`

Reviewable code/report worktree:

- `/Users/jkobject/.openclaw/worktrees/txgnn/t_fdb7423e-pyg-gnn-run`
- branch: `feat/t_fdb7423e-pyg-gnn-run`

Canonical KG source:

- `gs://jouvencekb/kg/v2`

Staged export generated for this task:

- `artifacts/staged/t_fdb7423e_pyg_gnn_embedding_subset`

Run metrics JSON:

- `artifacts/reports/t_fdb7423e_pyg_gnn_embedding_subset_smoke_metrics.json`

## Bounded graph subset

The subset uses the canonical PyG export path, built by `manage_db.build_pyg_export` from canonical KG Parquets:

- node types: `molecule`, `gene`
- relation: `molecule_targets_gene`
- edge cap: `64` forward edges
- reverse edges: generated for message passing as `gene --rev_molecule_targets_gene--> molecule`
- node maps: full selected endpoint maps, not capped, so endpoint validation passes

Graph sizes from `validation_report.json` / `full_graph.metadata.json`:

```json
{
  "node_counts": {
    "gene": 267830,
    "molecule": 31007
  },
  "edge_counts": {
    "molecule_targets_gene": 64,
    "rev_molecule_targets_gene": 64
  },
  "feature_shapes": {
    "gene": [267830, 768],
    "molecule": [31007, 768]
  }
}
```

Export validation:

```json
{
  "status": "pass",
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

## Embedding / fallback wiring

The export used the previously staged real embedding feature root:

- `artifacts/staged/real_embeddings_20260623_t_f8bae791/features`
- fallback config: `artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json`

Policy summary from `heterodata/full_graph.metadata.json`:

```json
{
  "node_embedding_policy": {
    "gene": {"dim": 768, "real_rows": 16, "fallback_rows": 267814},
    "molecule": {"dim": 768, "real_rows": 16, "fallback_rows": 30991}
  },
  "edge_embedding_policy": {
    "molecule_targets_gene": {"dim": 256, "real_rows": 16, "fallback_rows": 48},
    "rev_molecule_targets_gene": {"dim": 256, "real_rows": 16, "fallback_rows": 48}
  }
}
```

The fallback policy is model-side learned fallback only; it is not a fabricated source-derived canonical embedding.

## Split method

`manage_db.run_pyg_gnn_smoke` performs a deterministic random edge split for the selected relation using seed `7423`:

- sample a random permutation over positive `molecule_targets_gene` edges;
- validation positives: `min(edge_count // 5, 1024)`, here 12;
- test positives: `min(edge_count // 5, 1024)`, here 12;
- training positives: up to `--max-train-edges 32`, here 32;
- negative train/validation/test edges are sampled uniformly from molecule/gene index pairs not present in the selected positive edge set;
- train, validation, and test all include equal positive/negative counts;
- validation/test metrics are computed on a leak-free message-passing graph that retains only the training positive `molecule_targets_gene` edges and their reverse edges. Validation and test positive labels are removed from both forward and reverse adjacency before `model.encode(...)`.

Observed split:

```json
{
  "train_positive_edges": 32,
  "train_negative_edges": 32,
  "valid_positive_edges": 12,
  "valid_negative_edges": 12,
  "test_positive_edges": 12,
  "test_negative_edges": 12
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

The PASS validation confirms edge attributes were present and consumed:

```json
{
  "feature_tensors_present": true,
  "edge_tensors_present": true,
  "edge_attr_tensors_present": true,
  "selected_edge_attr_consumed_by_predictor": true,
  "selected_edge_endpoint_bounds": true,
  "split_endpoint_bounds": true,
  "nonempty_splits": true,
  "reverse_edges_present": true,
  "reverse_edge_count_matches": true,
  "reverse_edges_are_transpose": true,
  "message_passing_edge_count_matches_train_split": true,
  "heldout_edges_removed_from_message_passing": true
}
```

## Training/eval trace

Command output status: `pass`.

```json
{
  "epochs": 5.0,
  "train_loss_trace": [
    0.6924418210983276,
    0.6362107396125793,
    0.5813294053077698,
    0.5217739343643188,
    0.4602312445640564
  ],
  "initial_train_loss": 0.6924418210983276,
  "final_train_loss": 0.4602312445640564,
  "valid_loss": 0.5280608534812927,
  "valid_accuracy": 0.8333333134651184,
  "test_loss": 0.5178394913673401,
  "test_accuracy": 0.875
}
```

Because the subset is tiny and negatives are sampled, the validation/test accuracies are only leak-free heldout smoke metrics. They should not be interpreted as production biology/model quality.

## Commands to rerun

Build the bounded strict export:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root artifacts/staged/t_fdb7423e_pyg_gnn_embedding_subset \
  --node-types molecule gene \
  --relations molecule_targets_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 64 \
  --embedding-features-root artifacts/staged/real_embeddings_20260623_t_f8bae791/features \
  --learned-fallback-config-path artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/reports/learned_fallback_config.json \
  --build-name t_fdb7423e_pyg_gnn_embedding_subset \
  --sort-node-ids
```

Run the GNN smoke/training job:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_fdb7423e_pyg_gnn_embedding_subset \
  --relation molecule_targets_gene \
  --epochs 5 \
  --hidden-channels 8 \
  --max-train-edges 32 \
  --seed 7423 \
  --output-json artifacts/reports/t_fdb7423e_pyg_gnn_embedding_subset_smoke_metrics.json
```

## Verification commands run

Runtime/version check:

```bash
uv run python - <<'PY'
import json, sys
import torch, torch_geometric
from torch_geometric.data import HeteroData
print(json.dumps({
  'python': sys.version.split()[0],
  'torch': torch.__version__,
  'torch_geometric': torch_geometric.__version__,
  'heterodata_class': f'{HeteroData.__module__}.{HeteroData.__name__}',
  'cuda_available': bool(torch.cuda.is_available()),
}, indent=2, sort_keys=True))
PY
```

Observed:

```json
{
  "cuda_available": false,
  "heterodata_class": "torch_geometric.data.hetero_data.HeteroData",
  "python": "3.11.15",
  "torch": "2.12.1",
  "torch_geometric": "2.8.0"
}
```

Targeted tests in the dedicated review worktree:

```bash
uv run --group dev --group gnn pytest tests/test_build_pyg_export.py -q
```

Observed:

```text
6 passed in 2.13s
```

Compile check:

```bash
uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py
```

Observed: exit code 0.

## Additional attempted run and caveat

I also ran the older larger representative export at:

- `artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno`

It trained for 3 epochs on `molecule_targets_gene` with 4096 train positives and 1024 validation positives, but the smoke script returned `status: fail` because that older export has structural 1D node features and no `edge_attr`; therefore `edge_attr_tensors_present=false` and `selected_edge_attr_consumed_by_predictor=false`. I did not use that as the acceptance PASS for this task.

## Caveats / not production

- This is a bounded staged subset, not full all-relation KG tensorization.
- Only `molecule_targets_gene` was trained/evaluated.
- Only 64 positive edges were included in the strict embedding/fallback run.
- Real embedding rows are sparse in this staged embedding artifact: most node/edge rows use model-side learned fallback tensors.
- The reported validation/test accuracies are leak-free heldout smoke metrics on a tiny random split, not therapeutic prediction benchmarks.
- No canonical KG promotion was performed.
