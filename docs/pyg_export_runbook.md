# Canonical KG PyG / HeteroData export runbook

Date: 2026-06-23
Task: `t_a28b941e`, extended by `t_015bd9a4`

## Purpose

`manage_db.build_pyg_export` materializes a bounded PyG-style derived layer from
canonical KG v2 Parquet artifacts. It reads only canonical `nodes/`, `edges/`,
and optional `features/` tables from GCS/FUSE roots such as
`gs://jouvencekb/kg/v2`; it does not depend on `.omoc` staging state.

Status as of the `t_59851ed4` / `t_c505a206` production-scale gate:

- validated representative/staged export: available and accepted at
  `artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno`;
  this includes a real `heterodata/full_graph.pt` and a passing GNN smoke run;
- production-scale dry-run/offload path: validated by footer-only planning in
  `artifacts/reports/t_59851ed4/` with 13 node types, 39 active relations,
  52,565,491 selected node rows, and 101,743,458 selected edge rows;
- production/full-KG export: still pending. Do not describe plan-only manifests
  or the representative export as production/full done until the sidecar-first
  remote export, validation, sidecar-backed GNN smoke, and review gates below
  pass. A monolithic `heterodata/full_graph.pt` is not required for the
  production/no-edge-cap sidecar feasibility gate.

Heavy-job guardrail (`t_d682b7ad`): production/full PyG/HeteroData exports, no-edge-cap tensorization, and GNN training over full/staged production artifacts must run on `txgnn-worker` or another explicitly approved in-region worker with `--kg-root gs://jouvencekb/kg/v2`. Do **not** run heavy PyG/GNN jobs through `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE. Future heavy cards must include `must_run_on=txgnn-worker`, preflight `hostname`, use `gcloud compute ssh` for worker launch/inspection, check for an existing related export/training process, and fail if any heavy input/output path starts with `/Users/jkobject/mnt/gcs`.

The export follows the parent design in `docs/pyg_mapping_design.md`:

- deterministic `node_maps/{node_type}.id_to_index.parquet` and
  `index_to_id.parquet`;
- typed edge stores named `{x_type}__{relation}__{y_type}`;
- `edge_index` tensor artifacts (`.npy` always, `.pt` when PyTorch is installed),
  inspectable `edge_index.parquet`, `edge_row_map.parquet`, and `edge_attr.parquet`;
- `schema/relation_to_edge_type.parquet` relation metadata;
- feature-table row maps and feature manifests;
- reverse-edge sidecars for message passing;
- `heterodata/full_graph.metadata.json` plus optional `full_graph.pt` for
  bounded pilots or `--artifact-mode heterodata|both` runs;
- `validation_report.json` / `.md` with shape, endpoint, and reproducibility
  checks.

Manifest feature policy update (`t_95eca063`): `manifest.json` now records
embedding and missing-feature policy alongside sidecar paths. The manifest has
top-level `node_embeddings`, `edge_embeddings`, and `missing_feature_policy`
sections. These distinguish: available embedding sidecars, absent embeddings
filled by model-side learned fallback rows, available categorical/numeric/raw
feature values, and intentionally deferred production modalities such as
protein/transcript sequence embeddings, molecule chemical encoder embeddings,
and gene/enhancer/mutation DNA embeddings. Embedding sidecars are mapped back to
PyG IDs via `node_maps/{node_type}.id_to_index.parquet` on
`embedding.node_id == node_maps.id`; edge embeddings map through
`edge_row_map.parquet` on `embedding.edge_key == edge_row_map.edge_key` with
`edge_pos` as the PyG row. This manifest scan is footer/schema-based and must
not require materializing a full no-cap `HeteroData` pickle or full 100M-edge
tensors.

Implementation contract for that manifest feature policy (expanded standalone note:
`docs/pyg_manifest_metadata_contract_t_a3b15bc8.md`):

- Source of truth: `artifacts/reports/t_e4f08d5a/kg_embedding_sidecar_audit.md`
  and its raw evidence JSON (`artifacts/reports/t_e4f08d5a/raw_audit.json`) are
  the accepted audit inputs for current feature/embedding availability. Current
  exporter metadata scans may refine row counts/paths for the selected export,
  but must not silently contradict the audit without a new audit report.
- Top-level manifest keys: `node_embeddings`, `edge_embeddings`, and
  `missing_feature_policy` are required. `missing_feature_policy` must include
  `source_of_truth`, `materialization_policy`, `node_types`, and `edge_types`.
- Node embedding entries under `node_embeddings[{node_type}]` are lists of
  sidecar descriptors. Each descriptor must include at least `path`,
  `embedding_model`, `embedding_dim`, `rows`, and `sidecar_node_id_mapping` with
  shape `{embedding_join_key: "node_id", node_map_join_key: "id",
  pyg_index_column: "node_index"}`. The PyG row for a sidecar embedding is found
  by joining `embedding.node_id` to `node_maps/{node_type}.id_to_index.parquet:id`.
- Edge embedding entries under `edge_embeddings[{relation}]` are lists of sidecar
  descriptors. Each descriptor must include at least `path`, `embedding_model`,
  `embedding_dim`, `rows`, and `sidecar_edge_id_mapping` with shape
  `{embedding_join_key: "edge_key", edge_row_map_join_key: "edge_key",
  pyg_index_column: "edge_pos"}`. Reverse-edge stores inherit the same embedding
  via `forward_edge_pos`; no reverse canonical edge key is minted.
- `missing_feature_policy.node_types[{node_type}]` must record `node_count`,
  `embedding_status` (`available` or `absent`), `available_embeddings`,
  `absent_embeddings`, `available_feature_values`, `intentionally_deferred`,
  `fallback_policy`, and `sidecar_node_id_mapping`.
- `missing_feature_policy.edge_types[{relation}]` must record `edge_count`,
  `embedding_status` (`available` or `absent`), `available_embeddings`,
  `absent_embeddings`, `available_feature_values`, `intentionally_deferred`,
  `fallback_policy`, and `sidecar_edge_id_mapping`.
- Absent embeddings are represented as metadata, not zero tensors:
  `embedding_status: "absent"` plus an `absent_embeddings[]` reason and fallback
  of model-side learned `torch.nn.Embedding` rows. Materialized bounded
  `HeteroData` may contain those learned rows, but the manifest must make clear
  they are fallbacks and not source embeddings.
- Available categorical/numeric values are represented in
  `available_feature_values[]` with `field` or `feature_table`, `status:
  "available"`, `value_kind` (`categorical`, `numeric`, `text/raw`,
  `sequence/raw`, `sparse_vector`, or `mixed/raw`), source path/sidecar, mapped
  row count where applicable, and row-map path for node feature tables.
- Intentionally deferred fields are represented in `intentionally_deferred[]` as
  `{field, status: "deferred", reason}`. Current deferred examples include
  protein/transcript sequence model embeddings, molecule chemical encoder
  embeddings, gene/enhancer/mutation DNA embeddings, and dense all-evidence
  payload tensors.
- Representative node types that tests must cover: `gene` with available text
  embeddings and fallback for unmapped rows; `disease` with no visible embedding
  sidecar; `molecule` with available `molecule_fingerprint` sidecar values and a
  deferred chemical encoder embedding; and `protein`/`transcript` sequence rows
  marked as raw/deferred until sequence-model embeddings exist.
- Representative edge types that tests must cover: `disease_associated_gene` or
  `molecule_targets_gene` with edge embeddings when a sidecar is present;
  `molecule_targets_gene` or another selected relation with absent edge
  embeddings and learned fallback; and reverse stores such as
  `gene__rev_molecule_targets_gene__molecule` preserving forward-edge mapping
  through `forward_edge_pos`.

How to read these manifest fields:

- Treat `node_embeddings` and `edge_embeddings` as the list of source-backed
  sidecar embeddings that can be joined into PyG rows. Empty lists mean no
  manifest-visible source embedding exists for that selected type/relation; they
  do not mean the exporter materialized an all-zero tensor.
- For node embeddings, read the descriptor under
  `node_embeddings[{node_type}]`, open `path`, and join sidecar
  `node_id` to `node_maps/{node_type}.id_to_index.parquet:id`. The resulting
  `node_index` is the PyG row. Rows in the node map without a joined sidecar row
  use the model-side learned fallback described by `fallback_policy`.
- For edge embeddings, read the descriptor under `edge_embeddings[{relation}]`,
  open `path`, and join sidecar `edge_key` to the selected relation's
  `edge_row_map.parquet:edge_key`. The resulting `edge_pos` is the PyG edge row.
  Reverse-edge stores reuse the forward row via `forward_edge_pos`; do not look
  for a separately minted reverse edge embedding key.
- `missing_feature_policy.node_types` and `.edge_types` are the per-type decision
  table. `embedding_status: "available"` means at least one listed sidecar can be
  used for some or all rows. `embedding_status: "absent"` plus
  `absent_embeddings[]` means no source embedding sidecar was visible and the
  model should initialize learned fallback rows. `intentionally_deferred[]`
  means the field/modality is known and deliberately not represented yet (for
  example future sequence or chemical encoder embeddings); do not confuse this
  with an unexpected missing sidecar.
- `available_feature_values[]` is the non-embedding feature inventory. It records
  whether each usable sidecar/field is categorical, numeric, text/raw,
  sequence/raw, sparse-vector, or mixed/raw, and includes row-map/source paths
  when available. These entries say the values can be consumed or encoded by a
  downstream model; they are not necessarily dense tensors in `HeteroData.x`.
- The policy is metadata derived from the accepted audit output plus current
  Parquet footer/schema scans. It must remain inspectable without loading full
  embedding vectors, a full no-cap `HeteroData` pickle, or full edge tensors.

Bounded fixture-style manifest excerpt (`tests/test_build_pyg_export.py` uses a
three-node-type KG with unit text embeddings for `gene`, unit edge embeddings for
`disease_associated_gene`, and `gene_textual_summary` as a raw/text feature):

```json
{
  "node_embeddings": {
    "gene": [
      {
        "status": "available",
        "modality": "text",
        "embedding_model": "unit-model",
        "embedding_version": "policy_v1",
        "path": "embeddings/text/gene/unit-model/policy_v1/part-000.parquet",
        "rows": 2,
        "embedding_dim": 4,
        "embedding_dtype": "float32",
        "sidecar_node_id_mapping": {
          "embedding_join_key": "node_id",
          "node_map_join_key": "id",
          "pyg_index_column": "node_index"
        }
      }
    ],
    "disease": [],
    "molecule": []
  },
  "edge_embeddings": {
    "disease_associated_gene": [
      {
        "status": "available",
        "modality": "edge_evidence",
        "embedding_model": "unit-encoder",
        "embedding_version": "edge_policy_v1",
        "path": "edge_embeddings/by_relation/disease_associated_gene/unit-encoder/edge_policy_v1/part-000.parquet",
        "rows": 2,
        "embedding_dim": 3,
        "embedding_dtype": "float32",
        "sidecar_edge_id_mapping": {
          "embedding_join_key": "edge_key",
          "edge_row_map_join_key": "edge_key",
          "pyg_index_column": "edge_pos"
        }
      }
    ],
    "molecule_targets_gene": []
  },
  "missing_feature_policy": {
    "source_of_truth": "artifact audit t_e4f08d5a plus current exporter metadata scan",
    "materialization_policy": "Manifest generation records Parquet footer/schema metadata and sidecar mapping contracts only; it must not require a full HeteroData pickle or full 100M-edge tensor materialization.",
    "node_types": {
      "gene": {
        "node_count": 3,
        "embedding_status": "available",
        "available_embeddings": ["see node_embeddings.gene"],
        "absent_embeddings": [],
        "available_feature_values": [
          {
            "feature_table": "gene_textual_summary",
            "status": "available",
            "value_kind": "text/raw",
            "mapped_rows": 2,
            "row_map": "node_features/gene/gene_textual_summary.row_map.parquet"
          }
        ],
        "intentionally_deferred": [
          {
            "field": "dna_sequence_embedding",
            "status": "deferred",
            "reason": "DNA/foundation sequence feature production build pending"
          }
        ],
        "fallback_policy": "use real sidecar rows when present; fill missing node rows with learned fallback embeddings at model materialization time",
        "sidecar_node_id_mapping": {
          "node_map": "node_maps/gene.id_to_index.parquet",
          "join_key": "embedding.node_id == node_maps.id",
          "pyg_index_column": "node_index"
        }
      },
      "disease": {
        "node_count": 2,
        "embedding_status": "absent",
        "available_embeddings": [],
        "absent_embeddings": [
          {
            "embedding_family": "textual_summary",
            "status": "absent",
            "reason": "no manifest-visible embedding sidecar found for selected node type",
            "fallback": "model-side learned torch.nn.Embedding rows"
          }
        ],
        "available_feature_values": [],
        "intentionally_deferred": []
      },
      "molecule": {
        "embedding_status": "absent",
        "intentionally_deferred": [
          {
            "field": "chemical_encoder_embedding",
            "status": "deferred",
            "reason": "learned chemical encoder production build pending"
          }
        ]
      }
    },
    "edge_types": {
      "disease_associated_gene": {
        "edge_count": 2,
        "embedding_status": "available",
        "available_feature_values": [
          {"field": "credibility", "status": "available", "value_kind": "numeric"},
          {"field": "source", "status": "available", "value_kind": "categorical"}
        ],
        "sidecar_edge_id_mapping": {
          "edge_row_map": "edges/gene__disease_associated_gene__disease/edge_row_map.parquet",
          "join_key": "embedding.edge_key == edge_row_map.edge_key",
          "pyg_index_column": "edge_pos",
          "reverse_edge_mapping": "reverse_edges/*/edge_row_map.parquet carries forward_edge_pos for reverse stores"
        }
      },
      "molecule_targets_gene": {
        "edge_count": 2,
        "embedding_status": "absent",
        "absent_embeddings": [
          {
            "embedding_family": "relation_value_evidence_mlp",
            "status": "absent",
            "fallback": "model-side learned torch.nn.Embedding rows"
          }
        ],
        "intentionally_deferred": [
          {
            "field": "all_evidence_payload_tensor",
            "status": "deferred",
            "reason": "rich evidence remains sidecar/provenance, not dense tensor hot path"
          }
        ]
      }
    }
  }
}
```

Graph policy update (`t_c07b8b57`): `dataset` and `paper` node types are
provenance/catalog metadata only, not training/inference graph nodes. The PyG
builder excludes `dataset`, `paper`, and any relation touching those endpoint
types by default even when canonical metadata files remain under `nodes/` or
`edges/`. Use `--include-provenance-node-types` only for explicit audit/debug
exports, not default model training.

Cleanup promotion (`t_d97c4547`): the reviewed backup gate retained the existing
dataset/paper canonical Parquets in place with metadata-only/non-training labels
instead of deleting them. Default export manifests now record the full
`GRAPH_DISCONNECTED_RELATIONS` policy set and a `policy_label`; the canonical KG
sidecar is `metadata/dataset_paper_graph_policy_t_d97c4547.{json,md}`.

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

- complete true chunked tensor/row-map writers for unbounded full-relation exports;
  the bounded reader now uses Parquet batches, but unbounded `HeteroData` materialization
  still needs bucket-local/GCP memory sizing and review before production;
- decide the production node feature policy: structural smoke `x = ones` is no longer
  the default fallback; real GNN training should use official numeric/learned embeddings
  with model-side learned fallback rows for missing values;
- run a full all-active-relation export from a bucket-local worker, then run a
  longer training job with saved model/checkpoints and task-specific metrics;
- stage/promote production artifacts to GCS only after review/QA acceptance.

## Safe local bounded workflow

Use bounded local/FUSE exports only for endpoint-consistent pilots and smoke
tests. Keep either relation caps or a deliberately small selected relation set;
do not run an all-active-relation, no-edge-cap tensorization through Mac
GCS-FUSE. If the card involves production/full scale, full/staged production
artifacts, all-active relations, or no edge caps, switch to the VM-only workflow
below before launch.

Recommended safe local pattern:

```bash
uv sync --group gnn

uv run python -m manage_db.build_pyg_export \
  --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --output-root artifacts/staged/<task-id>_pyg/<pilot-name> \
  --node-types molecule gene disease pathway phenotype \
  --relations molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease disease_associated_gene disease_has_phenotype gene_associated_phenotype pathway_contains_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 20000 \
  --build-name <task-id>_<pilot-name> \
  --sort-node-ids

uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/<task-id>_pyg/<pilot-name> \
  --relation molecule_targets_gene \
  --epochs 3 \
  --hidden-channels 16 \
  --max-train-edges 4096 \
  --output-json artifacts/staged/<task-id>_pyg/<pilot-name>/gnn_smoke_metrics.json
```

The representative command in the previous section is the validated example of
this workflow. It proves the exporter can write a real PyG `HeteroData` object
and that the smoke model can train, but it remains capped/staged rather than
production/full-KG.

## Production-scale planning / offload gate (`t_59851ed4`, QA `t_c505a206`)

`manage_db.build_pyg_export` has a metadata-only planning mode for production/full-KG
export gates. This is the required Mac-side preflight before a no-edge-cap
production-scale run:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --output-root artifacts/reports/t_59851ed4/full_available_active_plan \
  --node-types gene transcript protein disease cell_type tissue molecule phenotype pathway mutation organism cell_line enhancer \
  --relations gene_has_transcript transcript_encodes_protein mutation_in_gene mutation_associated_gene mutation_affects_transcript mutation_causes_protein_change mutation_overlaps_enhancer mutation_associated_disease mutation_associated_phenotype gene_associated_phenotype mutation_affects_molecule_response gene_ortholog_gene enhancer_regulates_gene tissue_expresses_gene tissue_expresses_protein cell_type_expresses_gene cell_line_expresses_gene gene_interacts_gene protein_interacts_protein pathway_contains_gene pathway_child_of_pathway molecule_in_pathway molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease molecule_synergizes_molecule molecule_parent_of_molecule molecule_associated_phenotype disease_associated_gene disease_involves_pathway disease_manifests_in_tissue disease_subtype_of_disease disease_has_phenotype phenotype_subtype_of_phenotype tissue_subtype_of_tissue cell_line_derived_from_tissue cell_line_from_organism organism_has_gene organism_has_tissue \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 0 \
  --build-name t_59851ed4_full_available_active_plan \
  --plan-only \
  --remote-output-root gs://jouvencekb/kg/staging/ml/pyg/t_59851ed4_full_available_active_plan
```

Outputs:

- `production_plan_manifest.json` / `.md`: selected node/relation Parquet-footer row
  counts, rough memory/disk estimates for node maps and forward edge indices,
  training-graph exclusion policy, and a bucket-local remote build command.
- `validation_report.json` / `.md`: PASS when the planning manifest was produced
  without materializing full tables.

Validated QA evidence:

- `artifacts/reports/t_59851ed4/production_scale_pyg_next_step_design.md`
- `artifacts/reports/t_59851ed4/t_c505a206_qa_report.md`
- `artifacts/reports/t_59851ed4/full_available_active_plan/production_plan_manifest.json`
- `artifacts/reports/t_59851ed4/full_available_active_plan/validation_report.json`

The `t_c505a206` QA run passed this gate without local full-table
materialization: footer-only planning selected 52,565,491 node rows and
101,743,458 edge rows, validation status was `pass`, and max RSS was about
343 MiB. The manifest estimates roughly 21.3 GB before pandas join overhead,
PyG/HeteroData object overhead, feature tensors, embeddings, and training
memory; therefore the real no-edge-cap export should not be run through Mac
GCS-FUSE.

This mode is deliberately not a substitute for the actual `HeteroData` artifact.
It is the safe Mac gate before handing the full export to `txgnn-worker` or
another approved bucket-local/GCP worker. Plan-only outputs must not create
`heterodata/full_graph.pt`.

## GCP / bucket-local production-scale export workflow

After the plan manifest is reviewed, run the emitted command on `txgnn-worker` or
another explicitly approved bucket-local worker. Production/no-edge-cap export is
sidecar-first: it should write `sidecar_artifact.metadata.json`, relation-wise
`edge_index.npy`/`.pt` sidecars, Parquet `edge_row_map.parquet` files, schema,
reverse-edge sidecars, and manifests, and must not require a single full
`HeteroData` pickle.
The remote command must use the bucket KG root, write to a staging bucket path,
include `--artifact-mode sidecar`, and omit `--plan-only`:

```bash
hostname
gcloud compute ssh txgnn-worker --zone <zone> --command 'hostname; pgrep -af "build_pyg_export|run_pyg_gnn_smoke|python" || true'
```

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root gs://jouvencekb/kg/staging/ml/pyg/t_c505a206_qa_full_available_active_plan \
  --node-types cell_line cell_type disease enhancer gene molecule mutation organism pathway phenotype protein tissue transcript \
  --relations gene_has_transcript transcript_encodes_protein mutation_in_gene mutation_associated_gene mutation_affects_transcript mutation_causes_protein_change mutation_overlaps_enhancer mutation_associated_disease mutation_associated_phenotype gene_associated_phenotype mutation_affects_molecule_response gene_ortholog_gene enhancer_regulates_gene tissue_expresses_gene tissue_expresses_protein cell_type_expresses_gene cell_line_expresses_gene gene_interacts_gene protein_interacts_protein pathway_contains_gene pathway_child_of_pathway molecule_in_pathway molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease molecule_synergizes_molecule molecule_parent_of_molecule molecule_associated_phenotype disease_associated_gene disease_involves_pathway disease_manifests_in_tissue disease_subtype_of_disease disease_has_phenotype phenotype_subtype_of_phenotype tissue_subtype_of_tissue cell_line_derived_from_tissue cell_line_from_organism organism_has_gene organism_has_tissue \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 0 \
  --build-name t_c505a206_qa_full_available_active_plan \
  --artifact-mode sidecar
```

If the validated worktree artifact is available, the same command is also in the
executable helper script reported by QA:

```text
/Users/jkobject/.openclaw/worktrees/txgnn/t_59851ed4-pyg-production/artifacts/reports/t_59851ed4/run_t_c505a206_full_available_remote_export.sh
```

Then smoke-test one selected relation from the real staged sidecars on the same
worker. The smoke loader falls back to `sidecar_artifact.metadata.json` when
`heterodata/full_graph.pt` is absent, so this validates PyG feasibility without
materializing the full graph pickle:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root <worker-visible-path-to-staged-export> \
  --relation molecule_targets_gene \
  --epochs 2 \
  --hidden-channels 8 \
  --max-train-edges 4096 \
  --output-json <worker-visible-path-to-staged-export>/gnn_smoke_metrics.json
```

Remote acceptance gates:

- `validation_report.json` status is `pass` with zero errors;
- `sidecar_artifact.metadata.json` exists and records the sidecar artifact mode;
- forward relation-wise edge-index sidecars exist for the selected active
  relations, with inspectable `edge_row_map.parquet` row maps;
- reverse-edge sidecars exist for message passing and match the selected forward
  relations;
- `manage_db.run_pyg_gnn_smoke` reports `status: pass` on the produced artifact
  via its sidecar fallback when `heterodata/full_graph.pt` is absent;
- `heterodata/full_graph.pt` is treated as optional and may be absent for the
  no-edge-cap sidecar feasibility gate. It is only required for bounded pilots
  or explicit `--artifact-mode heterodata|both` runs;
- the report labels the output as staged production-scale, not canonical
  promotion.

## Metadata adjacency / provenance opt-in behavior

Dataset/paper provenance/catalog node types are retained as canonical metadata,
but they are excluded from default training adjacency. By default the exporter
removes requested `dataset` and `paper` node types and graph-disconnected
relations such as `dataset_contains_*`, `paper_cites_paper`, and
`paper_produced_dataset` from the training graph manifest. The default policy is
recorded in `build_config.json`, `production_plan_manifest.json`, and validation
reports as metadata-only/non-training.

Use `--include-provenance-node-types` only for explicit audit/debug exports that
need metadata adjacency included. Do not use it for default model-training PyG
exports.

## Remaining steps to reach production/full-KG

Production/full-KG remains pending until all of these gates pass:

1. Review the `t_c505a206` footer-only plan and confirm the selected node types,
   39 active relations, row counts, and memory/disk estimate are acceptable for
   the chosen GCP worker.
2. Run the no-edge-cap remote export on a bucket-local/GCP worker using
   `gs://jouvencekb/kg/v2` as `--kg-root` and a staging output root under
   `gs://jouvencekb/kg/staging/ml/pyg/...`; do not run this through Mac
   GCS-FUSE.
3. Confirm the remote sidecar export writes `sidecar_artifact.metadata.json`,
   relation-wise edge-index sidecars, row maps, reverse-edge sidecars, schema,
   and validation reports. Do not require `heterodata/full_graph.pt` for this
   no-edge-cap sidecar gate; it is optional for bounded pilots or explicit
   `--artifact-mode heterodata|both` runs only.
4. Run `manage_db.run_pyg_gnn_smoke` against the produced staged export and save
   metrics alongside it, relying on the sidecar fallback path when the full
   HeteroData pickle is absent.
5. Decide/promote the production node and edge feature policy: structural smoke
   tensors are acceptable for runtime validation, but production modeling should
   use reviewed numeric/learned embeddings plus model-side learned fallbacks for
   missing values.
6. Add chunked/streaming tensor and row-map writers before claiming arbitrary
   full-KG scalability beyond the validated worker sizing.
7. Request reviewer/tester acceptance before any canonical promotion. Until then
   the output is staged production-scale only, not production/full done.

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
