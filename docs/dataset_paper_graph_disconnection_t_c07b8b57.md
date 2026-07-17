# Dataset/paper graph disconnection policy — t_c07b8b57

Status: `validated` graph-disconnection policy, extended by cleanup promotion `t_d97c4547`. No canonical node/edge Parquet files were deleted or rewritten; `t_d97c4547` retained the affected files in place with explicit metadata-only/non-training sidecars and exporter exclusions.

## User decision

`dataset` and `paper` entities are provenance/catalog metadata only. They must not participate as KG graph nodes or graph-adjacency edges for training/inference. Source dataset and paper information should be preserved in evidence/catalog fields such as `source_dataset`, `dataset_id`, `paper_id`, PMID/DOI fields, source record IDs, and LaminDB/artifact metadata.

## Canonical inventory from `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`

Canonical node files involving disconnected provenance node types:

| Node file | Rows | Training graph policy |
| --- | ---: | --- |
| `nodes/dataset.parquet` | 1 | Keep as catalog/provenance metadata only; exclude from PyG/HeteroData/training graph by default. |
| `nodes/paper.parquet` | 2,958,199 | Keep as literature/provenance metadata only; exclude from PyG/HeteroData/training graph by default. |

Declared relations touching `dataset` or `paper`:

| Relation | X→Y | Kind | Canonical edge file | Edge rows | Evidence file | Policy |
| --- | --- | --- | --- | ---: | --- | --- |
| `paper_produced_dataset` | `paper→dataset` | `metadata` | no | - | no | Do not promote as graph adjacency; preserve as dataset/paper provenance/catalog metadata. |
| `paper_cites_paper` | `paper→paper` | `literature` | no | - | no | Do not promote as graph adjacency; keep citation data outside training graph unless a separate literature-only analysis explicitly opts in. |
| `dataset_contains_disease` | `dataset→disease` | `metadata` | no | - | no | Do not promote as graph adjacency; preserve measured-entity membership in dataset catalog/evidence metadata. |
| `dataset_contains_molecule` | `dataset→molecule` | `metadata` | no | - | no | Do not promote as graph adjacency; preserve measured-entity membership in dataset catalog/evidence metadata. |
| `dataset_contains_cell_type` | `dataset→cell_type` | `metadata` | no | - | no | Do not promote as graph adjacency; preserve measured-entity membership in dataset catalog/evidence metadata. |
| `dataset_contains_cell_line` | `dataset→cell_line` | `metadata` | yes | 1,183 | no | Retained in place as canonical metadata-only/non-training inventory by `t_d97c4547`; excluded from default graph adjacency/export. |
| `dataset_contains_tissue` | `dataset→tissue` | `metadata` | yes | 27 | no | Retained in place as canonical metadata-only/non-training inventory by `t_d97c4547`; excluded from default graph adjacency/export. |

Observed scan of all canonical `edges/*.parquet` endpoint columns found only these dataset/paper endpoint files:

- `edges/dataset_contains_cell_line.parquet` — 1,183 rows, `x_type=['dataset']`, `y_type=['cell_line']`.
- `edges/dataset_contains_tissue.parquet` — 27 rows, `x_type=['dataset']`, `y_type=['tissue']`.

## Implemented safe guardrail in this card

`manage_db.build_pyg_export` now excludes `dataset` and `paper` node types, and any relation whose endpoint is `dataset` or `paper`, from PyG/HeteroData/training graph exports by default. The manifest records `training_graph_exclusion_policy` with requested node/relation exclusions.

There is an explicit `--include-provenance-node-types` opt-in for audit/debug exports only. The default path used by training/inference remains disconnected.

## Cleanup promotion — t_d97c4547

Reviewed cleanup action: retain the canonical dataset/paper metadata files in place with explicit policy labels and exporter exclusions, rather than deleting or moving them in this card. The byte-for-byte backup/checksum gate was validated by `t_9ad833bf` / reviewer `t_fa4e9f85` before this cleanup.

Canonical sidecars written by `t_d97c4547`:

- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/dataset_paper_graph_policy_t_d97c4547.json`
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/dataset_paper_graph_policy_t_d97c4547.md`

Staged copies / producer script:

- `artifacts/staged/t_d97c4547/dataset_paper_graph_policy_manifest.json`
- `artifacts/staged/t_d97c4547/dataset_paper_graph_policy_manifest.md`
- `artifacts/staged/t_d97c4547/promote_dataset_paper_metadata_policy.py`

Affected canonical files retained in place as metadata-only/non-training:

- `nodes/dataset.parquet` — 1 row, SHA256 `f299994f59f5a5dcc53b96336f237bff25dad17497525d93eac65dca850f22ab`.
- `nodes/paper.parquet` — 2,958,199 rows, SHA256 `75d6a89849dd8cda9f383d81ef2c67ef32e49b70a9f8cf7ec1ec7f6dab582bd3`.
- `edges/dataset_contains_cell_line.parquet` — 1,183 rows, SHA256 `843908dc2b26ff8266148ff4ac80026503cf7b6f63d872751302339023e060e9`.
- `edges/dataset_contains_tissue.parquet` — 27 rows, SHA256 `c443bbe90b73c0e499cfc90df255bac5d1f8a15e3e1018a650ff6343f5802157`.

Default PyG/HeteroData export still excludes `dataset`, `paper`, and all relations touching those endpoints. The manifest now records both requested exclusions and the full `GRAPH_DISCONNECTED_RELATIONS` policy set. `--include-provenance-node-types` remains audit/debug opt-in only.

## Staged removal/deprecation plan superseded by retain-with-labels cleanup

1. Review and accept this policy update. Completed by reviewer `t_c2b31eb5`.
2. Create a backup/manifest card before touching canonical files. Completed and reviewer-accepted by `t_9ad833bf` / `t_fa4e9f85`.
3. Move/label dataset membership and paper provenance as non-adjacency metadata surfaces:
   - LaminDB artifact/source registries for dataset records;
   - evidence columns (`source_dataset`, `dataset_id`, `paper_id`, PMID/DOI fields, `source_record_id`) for relation-specific provenance;
   - optional catalog sidecars under a reviewed metadata/catalog prefix, not `edges/` consumed by graph export.
4. Promote a canonical cleanup only after independent review. `t_d97c4547` selected the reversible retain-with-labels option: add canonical `metadata/dataset_paper_graph_policy_t_d97c4547.*` sidecars, keep the affected Parquets in place, and ensure exporters exclude them by default.
5. Add regression coverage for any future exporter/loader that supports all-node/all-relation export so `dataset`/`paper` cannot silently re-enter training graph adjacency.

## Safe follow-up cards to create after review

- `GRAPH-POLICY review dataset/paper disconnection docs/export guardrail` → reviewer.
- `GRAPH-POLICY backup and stage dataset/paper metadata-edge retirement manifest` → dev/tester, parented on reviewer acceptance.
- `GRAPH-POLICY promote reviewed dataset/paper metadata cleanup` → dev, only after backup manifest and reviewer approval.

## Literature scope follow-up

Kanban task `t_9c86ca89` refines the paper-specific scope in `docs/literature_metadata_policy_t_9c86ca89.md`: publication IDs stay as evidence metadata in the biomedical KG, while any Paper/Author/Citation graph belongs in a separate `literature_index` namespace/export and remains excluded from default training/inference adjacency.
