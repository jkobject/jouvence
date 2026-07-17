# Live LaminDB KGEdge/KGEdgeEvidence promotion + bounded sync

Date: 2026-06-24
Task: `t_581617c7`
Status vocabulary: `live schema promoted`; `bounded live sync accepted`

## Scope

This is a real live LaminDB update for active instance `jkobject/jouvencekb`, not a local SQLite pilot.

This is **not** a full 94M-edge sync. The accepted live data write is bounded to:

- `disease_associated_gene`: first 25 canonical edge rows + first 25 canonical evidence rows from `gs://jouvencekb/kg/v2`
- `dataset_contains_tissue`: first 25 canonical edge rows + 0 evidence rows because no canonical evidence Parquet exists for that relation

## Root cause fixed

The live instance had `lnschema_txgnn` configured but had only applied migrations through `lnschema_txgnn.0006_custom_exact_id_gap_registries`. The code already contained `lnschema_txgnn.0007_generic_kg_edge_evidence`, so `txs.KGEdge.objects.count()` failed because `lnschema_txgnn_kgedge` and `lnschema_txgnn_kgedgeevidence` had not been created in the live SQLite DB.

## Schema promotion performed

Before migration, a local DB backup was written under:

```text
artifacts/reports/t_581617c7/lamin.db.before_0007_20260624_125323.bak
```

Command:

```bash
uv run lamin migrate deploy
```

Observed:

```text
Applying lnschema_txgnn.0007_generic_kg_edge_evidence... OK (12.151s)
! updating cloud SQLite 'gs://jouvencekb/lamin/.lamindb/lamin.db' of instance 'jkobject/jouvencekb'
```

Post-migration probe:

```text
slug jkobject/jouvencekb
modules ['bionty', 'lnschema_txgnn', 'pertdb']
new_tables ['lnschema_txgnn_kgedge', 'lnschema_txgnn_kgedgeevidence']
last_migration ('lnschema_txgnn', '0007_generic_kg_edge_evidence')
KGEdge_count 0
KGEdgeEvidence_count 0
```

## Live sync path implemented

New module:

```text
manage_db/sync_parquet_edges_to_lamindb.py
```

Properties:

- dry-run by default;
- `--write` required for live ORM writes;
- reads local paths or `gs://` canonical KG roots via `kg_storage`/fsspec;
- derives deterministic exact-ID `edge_key` and `evidence_key` with the same key functions as the accepted pilot;
- writes through `lnschema_txgnn.KGEdge.objects.update_or_create(edge_key=...)` and `lnschema_txgnn.KGEdgeEvidence.objects.update_or_create(evidence_key=...)`;
- preserves exact canonical endpoints (`x_id`, `x_type`, `y_id`, `y_type`), `relation`, source/evidence fields, score/predicate/direction, and extra columns as JSON `metadata`;
- avoids duplicating `edge_key`/`evidence_key` inside `metadata`.

The initial attempt to read `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` failed with `OSError: [Errno 6] Device not configured`, so the live sync path was updated and validated against the source-of-truth GCS URI `gs://jouvencekb/kg/v2`.

## Dry-run evidence

Command:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb gs://jouvencekb/kg/v2 \
  --relation disease_associated_gene \
  --relation dataset_contains_tissue \
  --edge-limit 25 \
  --evidence-limit 25 \
  --json
```

Report saved:

```text
artifacts/reports/t_581617c7/live_edge_sync_dryrun.json
```

Observed row availability/selection:

```text
disease_associated_gene: edge_rows_available=83339, edge_rows_selected=25, evidence_rows_available=2928, evidence_rows_selected=25
dataset_contains_tissue: edge_rows_available=27, edge_rows_selected=25, evidence_rows_available=0, evidence_rows_selected=0
```

## Live bounded write + idempotence evidence

Write command was run twice with the same bounds:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb gs://jouvencekb/kg/v2 \
  --relation disease_associated_gene \
  --relation dataset_contains_tissue \
  --edge-limit 25 \
  --evidence-limit 25 \
  --write \
  --json
```

Reports saved:

```text
artifacts/reports/t_581617c7/live_edge_sync_write1.json
artifacts/reports/t_581617c7/live_edge_sync_write2_idempotence.json
```

First write observed:

```text
disease_associated_gene: edge_existing_before=0, edge_count_after=25, evidence_existing_before=0, evidence_count_after=25
dataset_contains_tissue: edge_existing_before=0, edge_count_after=25, evidence_existing_before=0, evidence_count_after=0
```

Second write observed:

```text
disease_associated_gene: edge_existing_before=25, edge_count_after=25, evidence_existing_before=25, evidence_count_after=25
dataset_contains_tissue: edge_existing_before=25, edge_count_after=25, evidence_existing_before=0, evidence_count_after=0
```

This proves rerun idempotence for the bounded live sync: repeated writes update the same deterministic keys and do not duplicate rows.

## Live validation evidence

Validation report saved:

```text
artifacts/reports/t_581617c7/live_validation_probe.txt
```

Live ORM counts:

```text
KGEdge_total 50
KGEdgeEvidence_total 25
relation_counts disease_associated_gene 25 25
relation_counts dataset_contains_tissue 25 0
```

Sampled edge row preservation (`disease_associated_gene`):

```json
{"edge_key":"b9ae550a3a4ed9d2096c903badea50a4b6f23b9b6b8c94a5bc34c1243351e3d0","source_edge_key":"b9ae550a3a4ed9d2096c903badea50a4b6f23b9b6b8c94a5bc34c1243351e3d0","x_id":"ENSG00000111790","source_x_id":"ENSG00000111790","x_type":"gene","source_x_type":"gene","y_id":"EFO:0000220","source_y_id":"EFO:0000220","y_type":"disease","source_y_type":"disease","relation":"disease_associated_gene","source_relation":"disease_associated_gene","source":"OpenTargets/reactome","credibility":1,"metadata":{"score":1.0}}
```

Sampled evidence row preservation (`disease_associated_gene`):

```json
{"evidence_key":"4be60eb0185ab4e18db90d37e1382784c32f11e5dd0b33cac0b3b04685128ebf","source_evidence_key":"4be60eb0185ab4e18db90d37e1382784c32f11e5dd0b33cac0b3b04685128ebf","edge_key":"b1165be314684195d1d5d131868abd051e8d75b818095116c4ad6cd0326149b7","source_edge_key":"b1165be314684195d1d5d131868abd051e8d75b818095116c4ad6cd0326149b7","x_id":"ENSG00000105928","source_x_id":"ENSG00000105928","y_id":"EFO:0000181","source_y_id":"EFO:0000181","relation":"disease_associated_gene","source_relation":"disease_associated_gene","source":"OpenTargets","source_dataset":"reactome","source_record_id":"OpenTargets/reactome:disease_associated_gene:EFO:0000181:ENSG00000105928","evidence_type":"database_record","evidence_score":1.0,"predicate":"disease_associated_gene","direction":"forward"}
```

## Tests

Command:

```bash
uv run python -m py_compile manage_db/sync_parquet_edges_to_lamindb.py manage_db/kg_edge_pilot.py manage_db/lnschema_txgnn/models.py
uv run --group dev pytest tests/test_sync_parquet_edges_to_lamindb.py tests/test_kg_edge_pilot.py tests/test_sync_parquet_nodes_to_lamindb.py -q
```

Observed:

```text
22 passed in 0.40s
```

Test output saved:

```text
artifacts/reports/t_581617c7/targeted_tests.txt
```

## Changed files

```text
manage_db/sync_parquet_edges_to_lamindb.py
tests/test_sync_parquet_edges_to_lamindb.py
docs/lamindb_kgedge_live_sync_t_581617c7.md
```

## Residual risks / non-goals

- This is `bounded live sync accepted`, not `full sync accepted`.
- The live DB now has real KGEdge/KGEdgeEvidence schema and bounded rows, but the full 94,880,924-edge canonical KG has not been synced into LaminDB.
- The shared workspace is still not an independent git checkout; no PR/branch was created from this directory.
- FUSE path `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` was not usable in this run (`Device not configured`); use `gs://jouvencekb/kg/v2` for reproducibility unless FUSE is remounted.
