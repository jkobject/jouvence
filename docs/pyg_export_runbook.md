# Canonical KG PyG / HeteroData export runbook

Date: 2026-06-23
Task: `t_a28b941e`, extended by `t_015bd9a4`

## Purpose

`manage_db.build_pyg_export` materializes a bounded PyG-style derived layer from
canonical KG v2 Parquet artifacts. It reads only canonical `nodes/`, `edges/`,
and optional `features/` tables from GCS/FUSE roots such as
`gs://jouvencekb/kg/v2`; it does not depend on `.omoc` staging state.

The export follows the parent design in `docs/pyg_mapping_design.md`:

- deterministic `node_maps/{node_type}.id_to_index.parquet` and
  `index_to_id.parquet`;
- typed edge stores named `{x_type}__{relation}__{y_type}`;
- `edge_index` tensor artifacts (`.npy` always, `.pt` when PyTorch is installed),
  inspectable `edge_index.parquet`, `edge_row_map.parquet`, and `edge_attr.parquet`;
- `schema/relation_to_edge_type.parquet` relation metadata;
- feature-table row maps and feature manifests;
- reverse-edge sidecars for message passing;
- `heterodata/full_graph.metadata.json` and optional `full_graph.pt` when
  `torch_geometric` is importable;
- `validation_report.json` / `.md` with shape, endpoint, and reproducibility
  checks.

## Representative PyG + GNN smoke produced (`t_015bd9a4`)

Environment verification / install used for this run (the reusable dependency group is `gnn` in `pyproject.toml`; this run installed the same packages explicitly into the project `.venv`):

```bash
uv sync --group gnn
# command used in this task's existing .venv:
uv pip install --python .venv/bin/python torch torch-geometric
uv run python - <<'PY'
import torch, torch_geometric
print('torch', torch.__version__)
print('torch_geometric', torch_geometric.__version__)
PY
```

Observed versions:

```text
torch 2.12.1
torch_geometric 2.8.0
```

Representative multi-relation output:

```text
artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno
```

This is intentionally larger than the original 2-relation pilot but still
bounded: it uses full node maps for 5 endpoint types and caps each selected
relation to 20k rows. The selected relation family covers drug→gene/disease,
gene→disease, disease/gene→phenotype, and pathway→gene message-passing paths.

Build command:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --output-root artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno \
  --node-types molecule gene disease pathway phenotype \
  --relations molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease disease_associated_gene disease_has_phenotype gene_associated_phenotype pathway_contains_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 20000 \
  --feature-tables molecule_fingerprint \
  --build-name t_015bd9a4_rep_drug_gene_disease_pathway_pheno \
  --sort-node-ids
```

Build output summary:

```json
{
  "node_counts": {
    "disease": 41859,
    "gene": 267830,
    "molecule": 31007,
    "pathway": 48575,
    "phenotype": 16449
  },
  "edge_counts": {
    "disease_associated_gene": 20000,
    "disease_has_phenotype": 20000,
    "gene_associated_phenotype": 3330,
    "molecule_contraindicates_disease": 20000,
    "molecule_targets_gene": 20000,
    "molecule_treats_disease": 14135,
    "pathway_contains_gene": 20000
  }
}
```

The exporter now writes an actual PyG `HeteroData` object at
`heterodata/full_graph.pt` when `torch` and `torch_geometric` are importable. It
contains per-node-type structural `x` tensors, forward edge tensors, and reverse
edge tensors. Rich feature tables remain sidecars under `node_features/` until a
production feature policy promotes numeric/vector tensors into `data[node].x`.

GNN smoke/training command:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno \
  --relation molecule_targets_gene \
  --epochs 3 \
  --hidden-channels 16 \
  --max-train-edges 4096 \
  --output-json artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/gnn_smoke_metrics.json
```

Observed smoke metrics:

```json
{
  "status": "pass",
  "relation": "molecule_targets_gene",
  "split_counts": {
    "train_positive_edges": 4096,
    "train_negative_edges": 4096,
    "valid_positive_edges": 1024,
    "valid_negative_edges": 1024
  },
  "metrics": {
    "initial_train_loss": 5.26268196105957,
    "final_train_loss": 1.3462095260620117,
    "valid_loss": 0.21261024475097656,
    "valid_accuracy": 0.912109375,
    "epochs": 3.0
  },
  "validation": {
    "status": "pass",
    "checks": {
      "feature_tensors_present": true,
      "edge_tensors_present": true,
      "selected_edge_endpoint_bounds": true,
      "split_endpoint_bounds": true,
      "nonempty_splits": true,
      "reverse_edges_present": true,
      "reverse_edge_count_matches": true,
      "reverse_edges_are_transpose": true
    }
  }
}
```

What remains before full production:

- replace the current relation-level `pyarrow.read_table(...).slice(...)` pattern
  with streaming/batch writers so full 94M+ canonical edges can be tensorized
  without reading each selected relation into memory first;
- decide the production node feature policy: structural smoke `x = ones` is only
  for runtime validation, while real GNN training should promote official numeric
  or learned embeddings into per-node-type feature tensors;
- run a full all-active-relation export once streaming is implemented, then run a
  longer training job with saved model/checkpoints and task-specific metrics;
- stage/promote production artifacts to GCS only after review/QA acceptance.

## Pilot export produced (`t_a28b941e`)

Strict bounded pilot output:

```text
gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict
```

Build command:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict \
  --node-types gene disease molecule \
  --relations disease_associated_gene molecule_targets_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 10000 \
  --feature-tables gene_textual_summary molecule_textual_summary \
  --build-name t_a28b941e_pilot_strict
```

Validation summary read back from GCS:

```json
{
  "status": "pass",
  "error_count": 0,
  "warning_count": 0,
  "node_counts": {
    "disease": 41859,
    "gene": 267830,
    "molecule": 31007
  },
  "edge_counts": {
    "disease_associated_gene": 10000,
    "molecule_targets_gene": 10000
  }
}
```

The pilot keeps full node maps for the three endpoint types because those node
Parquets are modest enough for this bounded build. Edges remain capped at 10k per
relation to avoid turning this task into a full KG tensorization pass.

A first exploratory pilot also exists at
`gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e`; it intentionally used a 5k
node cap and non-strict mode, which demonstrated why endpoint-consistent pilots
should either use endpoint-closed samples or complete node maps for selected
relations.

## Output layout

For each selected node type:

```text
node_maps/{node_type}.id_to_index.parquet
node_maps/{node_type}.index_to_id.parquet
node_maps/{node_type}.stats.json
```

For each selected relation:

```text
edges/{x_type}__{relation}__{y_type}/edge_index.npy
edges/{x_type}__{relation}__{y_type}/edge_index.parquet
edges/{x_type}__{relation}__{y_type}/edge_row_map.parquet
edges/{x_type}__{relation}__{y_type}/edge_attr.parquet
edges/{x_type}__{relation}__{y_type}/edge_stats.json
reverse_edges/{y_type}__rev_{relation}__{x_type}/edge_index.npy
```

When `torch` / `torch_geometric` are installed, the script writes `.pt` tensor
sidecars and `heterodata/full_graph.pt` with node features plus forward/reverse
edge tensors. Without those imports, it still writes `.npy` tensors and
`heterodata/full_graph.metadata.json` so the export remains inspectable.

## Validation checks

`validation_report.json` records:

- node ID null/duplicate checks and deterministic ID-sequence SHA256 hashes;
- relation-column and endpoint-type consistency against `manage_db.kg_schema`;
- endpoint anti-join counts against selected node maps;
- `edge_index` shape counts;
- issue list with severity/counts.

Use strict mode for promotion-like pilots. Use `--no-strict` only for exploratory
sampling where missing endpoints should be reported and dropped instead of
failing the build.

## Tests

Targeted tests:

```bash
uv run python -m py_compile manage_db/build_pyg_export.py
uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py
uv run --group dev pytest tests/test_build_pyg_export.py tests/test_kg_storage.py -q
```

Last targeted `t_015bd9a4` run: `uv run --group dev pytest tests/test_build_pyg_export.py -q` → `3 passed, 2 warnings in 1.97s`.
