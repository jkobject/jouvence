# PyG manifest metadata contract from embedding/feature audit

Task: `t_a3b15bc8`
Status: design done

This note defines the manifest fields that `manage_db.build_pyg_export` must expose so downstream PyG/GNN materialization can tell source-backed embeddings from learned fallbacks and intentionally deferred modalities without loading a full no-cap `HeteroData` object or full 100M-edge tensors.

## Source-of-truth audit fields

Use `artifacts/reports/t_e4f08d5a/kg_embedding_sidecar_audit.md` plus raw evidence `artifacts/reports/t_e4f08d5a/raw_audit.json` as the accepted audit input for current embedding/feature availability. The exporter may refine selected-export row counts and paths by Parquet footer/schema scan, but it must not silently contradict this audit without a new audit report.

Audit fields used by the manifest contract:

- `real_embedding_parquets[].path`: sidecar location to record in `node_embeddings` or `edge_embeddings`.
- `real_embedding_parquets[].rows`: sidecar row count; this is coverage metadata, not proof of full node/edge coverage.
- `real_embedding_parquets[].schema[].name`: required join/vector metadata columns. Node sidecars must expose `node_id`, `node_type`, `embedding`, and should expose `embedding_model`, `embedding_version`, `embedding_dim`, `embedding_dtype`. Edge sidecars must expose `relation`, `edge_key`, `embedding`, and should expose `embedding_model`, `embedding_version`, `embedding_dim`, `embedding_dtype`.
- `real_embedding_parquets[].sample[]`: representative values for `node_id`/`node_type` or `edge_key`/`relation`, used only to verify join semantics, not for hardcoded manifest content.
- Audit "Embeddings found" coverage lists: determine which node types/relations have visible source-backed embedding sidecars and which are absent.
- Audit "Canonical feature tables available for encoders": feature table names, row counts, columns, and sample fields used to classify non-embedding values as `text/raw`, `sequence/raw`, `sparse_vector`, `numeric`, `categorical`, or `mixed/raw`.
- Audit "Mapping scheme / representation": node maps use `node_maps/{node_type}.id_to_index.parquet` with `id -> node_index`; edge stores use `{x_type}__{relation}__{y_type}/edge_row_map.parquet` with `edge_key -> edge_pos`; reverse edge stores carry `forward_edge_pos` and reuse the forward edge embedding identity.
- Audit "Mismatches / blockers": defines absent or intentionally deferred production modalities: no production/full node embedding set, no all-relation edge embedding table, clinical-trials HashingVectorizer is fallback/scaffold, and protein/transcript sequence, molecule chemical, and gene/enhancer/mutation DNA embeddings remain future builds.

## Target manifest structure

`manifest.json` must include these top-level keys:

- `node_embeddings`: `{node_type: [node_embedding_descriptor, ...]}` for selected node types.
- `edge_embeddings`: `{relation: [edge_embedding_descriptor, ...]}` for selected relations.
- `missing_feature_policy`: a per-node/per-edge policy table with source/fallback/deferred decisions.

`node_embedding_descriptor` fields:

- `status`: `available`.
- `modality`: e.g. `text`.
- `embedding_model`, `embedding_version`, `embedding_dim`, `embedding_dtype`.
- `path`, `rows`, optional `schema_columns` and embedding metadata column names.
- `sidecar_node_id_mapping`: `{embedding_join_key: "node_id", node_map_join_key: "id", pyg_index_column: "node_index"}`.

`edge_embedding_descriptor` fields:

- `status`: `available`.
- `modality`: e.g. `edge_evidence`.
- `embedding_model`, `embedding_version`, `embedding_dim`, `embedding_dtype`.
- `path`, `rows`, optional `schema_columns` and embedding metadata column names.
- `sidecar_edge_id_mapping`: `{embedding_join_key: "edge_key", edge_row_map_join_key: "edge_key", pyg_index_column: "edge_pos"}`.

`missing_feature_policy` fields:

- `source_of_truth`: name the audit plus current exporter metadata scan.
- `materialization_policy`: state that manifest generation records footer/schema metadata and sidecar mapping only, and must not require full no-cap `HeteroData` or full edge tensor materialization.
- `node_types[{node_type}]`:
  - `node_count`.
  - `embedding_status`: `available` if at least one visible source-backed sidecar exists for this selected node type, otherwise `absent`.
  - `available_embeddings`: same descriptors as `node_embeddings[{node_type}]`.
  - `absent_embeddings`: empty when available; otherwise objects with `embedding_family`, `status: "absent"`, `reason`, and fallback `model-side learned torch.nn.Embedding rows`.
  - `available_feature_values`: non-embedding feature sidecars/fields with `feature_table` or `field`, `status`, `value_kind`, source path, mapped row count, and row map when applicable.
  - `intentionally_deferred`: objects `{field, status: "deferred", reason}` for known future modalities.
  - `fallback_policy`: explain use of real sidecar rows where present and learned fallback rows at model materialization time.
  - `sidecar_node_id_mapping`: `{node_map, join_key: "embedding.node_id == node_maps.id", pyg_index_column: "node_index"}`.
- `edge_types[{relation}]`:
  - `edge_count`.
  - `embedding_status`, `available_embeddings`, and `absent_embeddings` with the same semantics as node types.
  - `available_feature_values`: at minimum canonical sidecar fields such as `credibility` as `numeric` and `source` as `categorical` when available through `edge_attr.parquet` / `edge_row_map.parquet`.
  - `intentionally_deferred`: e.g. dense `all_evidence_payload_tensor` until rich evidence encoding is explicitly implemented.
  - `fallback_policy`: real edge embeddings by edge key where present, otherwise learned edge embeddings.
  - `sidecar_edge_id_mapping`: `{edge_row_map, join_key: "embedding.edge_key == edge_row_map.edge_key", pyg_index_column: "edge_pos", reverse_edge_mapping}`.

## Representative node example

For selected node type `gene` with staged text embeddings and a requested `gene_textual_summary` feature table:

```json
{
  "node_embeddings": {
    "gene": [
      {
        "status": "available",
        "modality": "text",
        "embedding_model": "sbiobert_snli_multinli_stsb",
        "embedding_version": "policy_v1",
        "path": "artifacts/staged/real_embeddings_20260623_t_f8bae791/features/embeddings/text/gene/sbiobert_snli_multinli_stsb/policy_v1/part-000.parquet",
        "rows": 16,
        "embedding_dim": 768,
        "embedding_dtype": "float32",
        "sidecar_node_id_mapping": {
          "embedding_join_key": "node_id",
          "node_map_join_key": "id",
          "pyg_index_column": "node_index"
        }
      }
    ]
  },
  "missing_feature_policy": {
    "node_types": {
      "gene": {
        "node_count": 267830,
        "embedding_status": "available",
        "available_embeddings": ["see node_embeddings.gene"],
        "absent_embeddings": [],
        "available_feature_values": [
          {
            "feature_table": "gene_textual_summary",
            "status": "available",
            "value_kind": "text/raw",
            "mapped_rows": 212029,
            "row_map": "node_features/gene/gene_textual_summary.row_map.parquet",
            "source_path": "gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet"
          }
        ],
        "intentionally_deferred": [
          {"field": "dna_sequence_embedding", "status": "deferred", "reason": "DNA/foundation sequence feature production build pending"}
        ],
        "fallback_policy": "use real sidecar rows when present; fill missing node rows with learned fallback embeddings at model materialization time",
        "sidecar_node_id_mapping": {
          "node_map": "node_maps/gene.id_to_index.parquet",
          "join_key": "embedding.node_id == node_maps.id",
          "pyg_index_column": "node_index"
        }
      }
    }
  }
}
```

Interpretation: `embedding_status: available` means a source-backed embedding sidecar exists for some rows. It does not imply full coverage. Any selected gene node without a joined sidecar row uses learned fallback rows at model materialization time.

## Representative edge example

For selected relation `molecule_targets_gene` with staged relation/evidence embeddings:

```json
{
  "edge_embeddings": {
    "molecule_targets_gene": [
      {
        "status": "available",
        "modality": "edge_evidence",
        "embedding_model": "local_pytorch_relation_value_evidence_mlp",
        "embedding_version": "edge_policy_v1",
        "path": "artifacts/staged/real_embeddings_20260623_t_f8bae791/features/edge_embeddings/by_relation/molecule_targets_gene/relation_value_evidence_mlp/edge_policy_v1/part-000.parquet",
        "rows": 16,
        "embedding_dim": 256,
        "embedding_dtype": "float32",
        "sidecar_edge_id_mapping": {
          "embedding_join_key": "edge_key",
          "edge_row_map_join_key": "edge_key",
          "pyg_index_column": "edge_pos"
        }
      }
    ]
  },
  "missing_feature_policy": {
    "edge_types": {
      "molecule_targets_gene": {
        "edge_count": 41239,
        "embedding_status": "available",
        "available_embeddings": ["see edge_embeddings.molecule_targets_gene"],
        "absent_embeddings": [],
        "available_feature_values": [
          {"field": "credibility", "status": "available", "value_kind": "numeric", "source": "edges/{relation}.parquet and edge_attr.parquet"},
          {"field": "source", "status": "available", "value_kind": "categorical", "source": "edge_row_map.parquet"}
        ],
        "intentionally_deferred": [
          {"field": "all_evidence_payload_tensor", "status": "deferred", "reason": "rich evidence remains sidecar/provenance, not dense tensor hot path"}
        ],
        "fallback_policy": "use real edge embedding rows where edge_key matches; fill missing edge rows with learned fallback embeddings at model materialization time",
        "sidecar_edge_id_mapping": {
          "edge_row_map": "edges/molecule__molecule_targets_gene__gene/edge_row_map.parquet",
          "join_key": "embedding.edge_key == edge_row_map.edge_key",
          "pyg_index_column": "edge_pos",
          "reverse_edge_mapping": "reverse_edges/*/edge_row_map.parquet carries forward_edge_pos for reverse stores"
        }
      }
    }
  }
}
```

For a selected relation with no visible sidecar, set `embedding_status: "absent"`, keep `available_embeddings: []`, and add `absent_embeddings: [{"embedding_family": "relation_value_evidence_mlp", "status": "absent", "reason": "no manifest-visible edge embedding sidecar found for selected relation", "fallback": "model-side learned torch.nn.Embedding rows"}]`.

## Missing-feature policy

Missing and deferred fields are distinct:

- Missing/absent: a current selected type/relation has no manifest-visible source-backed embedding sidecar. The manifest records why and names the learned fallback. It must not materialize fake zero vectors to hide absence.
- Deferred: the modality is known and intentionally not part of the current source-backed feature contract, such as `protein_sequence_embedding`, `transcript_sequence_embedding`, `chemical_encoder_embedding`, `dna_sequence_embedding`, or dense all-evidence payload tensors. Deferred fields remain explicit so downstream consumers do not treat them as accidental omissions.

This policy applies independently per selected node type and relation; do not infer all-KG feature availability from a bounded sidecar sample.
