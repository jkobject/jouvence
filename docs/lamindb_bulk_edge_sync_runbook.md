# LaminDB KGEdge/KGEdgeEvidence bounded bulk sync runbook

This runbook covers the PR-ready loader in `manage_db/sync_parquet_edges_to_lamindb.py`.
It promotes the accepted Wave-2 loader proof into reviewable TxGNN code, but does not by itself make LaminDB sync production/full done.

## Status labels

- `bounded live sync bulk accepted`: an operator-approved row window was written to the live LaminDB instance with exact `edge_key` / `evidence_key` upserts and reviewer evidence.
- `pilot accepted`: a bounded loader/sync proof has been validated for the selected windows only.
- `production/full done`: all intended KG edge/evidence rows have been synced, validated, backed up, reviewed, and accepted. Do not use this label for Wave-1/Wave-2/Wave-3 bounded windows.

## Preconditions before `--write`

1. Confirm the intended LaminDB instance, usually `jkobject/jouvencekb`.
2. Take or verify a restorable backup of the live LaminDB SQLite cache before larger windows.
3. Verify `lnschema_txgnn` migrations include KGEdge/KGEdgeEvidence exact-key tables and unique constraints.
4. Use the canonical read-only KG root (`gs://jouvencekb/kg/v2` or the verified FUSE mirror). Do not write canonical KG Parquets from this loader.
5. Choose explicit relation windows (`--edge-offset`, `--edge-limit`, `--evidence-offset`, `--evidence-limit`) and a chunk size that fits the runtime/lock window.
6. Keep generated reports under `artifacts/reports/<task-id>/`; do not use `.omoc`.

## Dry-run examples

Inspect selected windows without touching live models:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  gs://jouvencekb/kg/v2 \
  --relation molecule_targets_gene \
  --edge-offset 10000 --edge-limit 20000 \
  --evidence-offset 10000 --evidence-limit 20000 \
  --chunk-size 5000 \
  --json
```

No-evidence relations are supported; the evidence file may be absent and the evidence selected/upserted counts should remain zero:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  gs://jouvencekb/kg/v2 \
  --relation tissue_expresses_gene \
  --edge-offset 5000 --edge-limit 30000 \
  --evidence-limit 0 \
  --json
```

## Bounded live write examples

Run only after backup/restore prerequisites and operator approval:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  gs://jouvencekb/kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation molecule_targets_gene \
  --edge-offset 10000 --edge-limit 20000 \
  --evidence-offset 10000 --evidence-limit 20000 \
  --chunk-size 5000 \
  --idempotence-passes 2 \
  --verify-selected-live \
  --write --json
```

Resume at a later chunk after a bounded interruption:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  gs://jouvencekb/kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation enhancer_regulates_gene \
  --edge-offset 15000 --edge-limit 50000 \
  --evidence-offset 15000 --evidence-limit 50000 \
  --chunk-size 5000 \
  --resume-chunk 4 \
  --write --json
```

Use `--max-chunks` for smoke windows when validating the larger plan without consuming the entire selected window.

## Semantics preserved from Wave-2

- Exact IDs and endpoints are derived from canonical source Parquets.
- `edge_key` and `evidence_key` are unique conflict targets.
- Writes use Django `bulk_create(update_conflicts=True)` with explicit `update_fields` and `unique_fields`.
- Each chunk runs inside `transaction.atomic()`.
- Reruns are idempotent by exact keys and should not create duplicates.
- `--verify-selected-live` compares selected live rows back to source fields after the write.
- The loader writes only to live LaminDB ORM models; it does not write canonical KG Parquets.

## Residual risks before larger/full sync

- The active LaminDB store is SQLite-backed; full-scale runs need lock/backoff monitoring, backup/restore rehearsal, and likely process supervision.
- Bounded row windows prove loader semantics and idempotence, not full 94M+ edge convergence.
- Relation-by-relation source/evidence policies remain governed by the canonical coverage docs; do not create placeholder evidence rows for no-evidence relations.
