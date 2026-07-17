# LaminDB KGEdge/KGEdgeEvidence bounded Wave-4 sync

Task: `t_b788d863`
Status: `review-required` producer handoff; this is not accepted yet and not production/full KG sync.

## Window

- Relation: `enhancer_regulates_gene`
- Edge window: offset `65,000`, limit `250,000`
- Evidence window: offset `65,000`, limit `250,000`
- Chunk size: `5,000`
- Loader: reviewed streaming/row-batch `manage_db/sync_parquet_edges_to_lamindb.py` path with Django `bulk_create(update_conflicts=True)` upserts.

## Preflight

Fresh-process preflight connected to `jkobject/jouvencekb`, confirmed modules include `lnschema_txgnn`, migration `lnschema_txgnn.0007_generic_kg_edge_evidence`, live `KGEdge`/`KGEdgeEvidence` tables, and baseline distinct keys matching rows.

Baseline totals before Wave-4:

- `KGEdge`: `151,291`
- `KGEdgeEvidence`: `109,167`

Backup before write:

- `artifacts/reports/t_b788d863/lamin.db.before_wave4_20260625_023230.bak`
- size bytes: `3387420672`
- SHA256 source/backup: `586949d1ba256886bb5aa156aeaaa7e3470a07ef2029d0f21737d0ca87e08058` / `586949d1ba256886bb5aa156aeaaa7e3470a07ef2029d0f21737d0ca87e08058`

Restore note: Stop live writers; copy the backup over the local cache DB path; reconnect jkobject/jouvencekb; rerun selected-window verification before resuming writes.

## Write + idempotence

Live write command used `--write --idempotence-passes 2 --verify-selected-live --chunk-size 5000`.

Observed write artifact: `artifacts/reports/t_b788d863/write_enhancer_regulates_gene_250k.json`.
Timing artifact: `artifacts/reports/t_b788d863/write_enhancer_regulates_gene_250k.stderr.txt` (`908.00 real`, max RSS `1531035648`).

The second idempotence pass reported chunk before/after relation counts staying at `315,000`, selected live edges/evidence found `250,000`/`250,000`, and source/live mismatch count `0`.

## Post-write verification

Independent fresh-process post probe artifact: `artifacts/reports/t_b788d863/post_wave4_live_counts_selected_window_manifest.json`.

Post totals:

- `KGEdge`: `401,291`
- `KGEdgeEvidence`: `359,167`
- distinct edge keys: `401,291`
- distinct evidence keys: `359,167`

Duplicate key groups:

- edges: `0`
- evidence: `0`

Selected source/live comparison:

- missing selected live edges: `0`
- missing selected live evidence: `0`
- edge mismatches: `0`
- evidence mismatches: `0`

## Cleanup / non-goals

- No canonical KG Parquets were written.
- No `.omoc` path was used.
- `uv run lamin disconnect` exited 0 and reported cloud SQLite update/unlock; see `artifacts/reports/t_b788d863/lamin_disconnect_after_wave4.txt`.
- No skipped/failed chunks were observed.
- Local DB backup is retained under the task report directory for reviewer rollback evidence; do not commit it.
- This remains a bounded Wave-4 sync only. It does not claim full 94M-edge production sync or full schema/query completion.

## Tests

- `uv run python -m py_compile manage_db/sync_parquet_edges_to_lamindb.py manage_db/kg_edge_pilot.py manage_db/sync_parquet_nodes_to_lamindb.py artifacts/reports/t_b788d863/lamin_wave4_preflight_inventory.py artifacts/reports/t_b788d863/lamin_wave4_post_probe.py`
- `uv run --group dev pytest tests/test_sync_parquet_edges_to_lamindb.py -q` -> `7 passed in 0.55s`
