# LaminDB KGEdge/KGEdgeEvidence bulk edge sync scaling note

Task: `t_6317d405`
Date: 2026-06-24
Status vocabulary: `review-required`; this is not a production/full KG sync.

## Scope

This task updates the reviewed bounded live KGEdge/KGEdgeEvidence loader so larger bounded waves can select source windows without materializing entire source Parquets first. No canonical KG Parquets were written and no live LaminDB writes were performed for this task.

The code path is `manage_db/sync_parquet_edges_to_lamindb.py`.

## Wave-3 bottleneck found

The accepted Wave-3 report `docs/lamindb_kgedge_wave3_sync_t_a4fe05b4.md` records the scale blocker:

- Wave-3 live totals after bounded writes: `151,291` `KGEdge` rows and `109,167` `KGEdgeEvidence` rows.
- A broader source/live comparison for larger `enhancer_regulates_gene` / `tissue_expresses_gene` windows exceeded the 600s foreground cap.
- Root cause: `_read_limited_parquet()` called `pq.ParquetFile.read()` and only then sliced with `table.slice(offset, limit)`, so even a bounded window could materialize a whole source Parquet.

Large source files make that unsafe for Wave-4 planning:

| file | rows | row groups | size |
| --- | ---: | ---: | ---: |
| `edges/enhancer_regulates_gene.parquet` | `48,808,144` | `118` | `1,997,157,871` bytes |
| `evidence/enhancer_regulates_gene.parquet` | `48,810,390` | `398` | `4,788,517,448` bytes |
| `edges/tissue_expresses_gene.parquet` | `5,338,736` | `45` | `41,362,747` bytes |
| `edges/molecule_targets_gene.parquet` | `41,239` | `1` | `238,792` bytes |
| `evidence/molecule_targets_gene.parquet` | `41,239` | `1` | `1,028,430` bytes |
| `edges/disease_associated_gene.parquet` | `83,339` | `1` | `314,067` bytes |
| `evidence/disease_associated_gene.parquet` | `2,928` | `1` | `90,231` bytes |

Metadata command used:

```bash
uv run python - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq
root=Path('/Users/jkobject/mnt/gcs/jouvencekb-kg/v2')
for sub, rel in [('edges','enhancer_regulates_gene'),('evidence','enhancer_regulates_gene'),('edges','tissue_expresses_gene'),('edges','molecule_targets_gene'),('evidence','molecule_targets_gene'),('edges','disease_associated_gene'),('evidence','disease_associated_gene')]:
    p=root/sub/f'{rel}.parquet'
    pf=pq.ParquetFile(p)
    print(sub, rel, 'rows=', pf.metadata.num_rows, 'row_groups=', pf.metadata.num_row_groups, 'size=', p.stat().st_size)
PY
```

## Implemented scaling path

`_read_limited_parquet()` now uses `ParquetFile.iter_batches()` with a bounded default source batch size of `65,536` rows. It skips batches before `offset`, slices only overlapping batches, stops as soon as the bounded `limit` is satisfied, and returns the Parquet metadata row count separately.

Preserved semantics:

- `offset < 0`, `limit < 0`, and non-positive source batch size are rejected.
- `limit=0` still means all rows from `offset` and should therefore only be used intentionally.
- `edge_key` recomputation remains unchanged.
- `evidence_key` still uses the absolute source-row ordinal, `offset + i`, preserving resume/idempotence for evidence windows.
- Write chunks still use `_aligned_chunk_windows()`, `transaction.atomic()`, `bulk_create(update_conflicts=True)`, exact-key upserts, `--resume-chunk`, `--max-chunks`, and `--idempotence-passes` semantics.
- `--verify-selected-live` still builds the selected source window and compares exact selected keys against live rows; it now benefits from the same bounded source reader.

## Test coverage added

`tests/test_sync_parquet_edges_to_lamindb.py` now includes `test_limited_parquet_reader_streams_batches_before_bounded_window`, a ParquetFile double whose `read()` method fails if called. The test proves a bounded `offset=25`, `limit=7`, `batch_size=10` window is assembled from batches `0..9`, `10..19`, `20..29`, and `30..39`, then stops without scanning/materializing the remaining fixture batches.

Existing tests continue to cover dry-run no-write behavior, bulk upsert idempotence, resume/window selection, missing evidence files, selected live verification, and CLI arguments.

## Dry-run runtime/memory evidence

No live writes were performed. A read-only dry-run on the large enhancer relation selected `10,000` edge rows and `10,000` evidence rows starting at the post-Wave-2 enhancer offset.

Command:

```bash
mkdir -p artifacts/reports/t_6317d405
/usr/bin/time -l uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation enhancer_regulates_gene \
  --edge-offset 65000 --edge-limit 10000 \
  --evidence-offset 65000 --evidence-limit 10000 \
  --chunk-size 5000 \
  --json \
  > artifacts/reports/t_6317d405/dryrun_enhancer_regulates_gene_streaming_10k.json
```

Observed output:

- runtime: `23.45 real`, `2.67 user`, `0.58 sys`
- maximum resident set size from `/usr/bin/time -l`: `588,955,648` bytes
- source edge total/selected: `48,808,144` / `10,000`
- source evidence total/selected: `48,810,390` / `10,000`
- status: `dry_run`
- output path: `artifacts/reports/t_6317d405/dryrun_enhancer_regulates_gene_streaming_10k.json`

The reported maximum RSS includes Python/LaminDB import overhead and Parquet/Arrow buffers; the important behavior is that selected rows are bounded and `ParquetFile.read()` is no longer used.

## Expected Wave-4 candidate windows

Candidate windows only; these require operator approval and backup before `--write`.

1. Larger enhancer continuation smoke:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation enhancer_regulates_gene \
  --edge-offset 65000 --edge-limit 50000 \
  --evidence-offset 65000 --evidence-limit 50000 \
  --chunk-size 5000 \
  --idempotence-passes 2 \
  --verify-selected-live \
  --write --json
```

2. Bounded enhancer/tissue mixed planning dry-runs before any write:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --relation enhancer_regulates_gene \
  --edge-offset 115000 --edge-limit 100000 \
  --evidence-offset 115000 --evidence-limit 100000 \
  --chunk-size 5000 \
  --json

uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --relation tissue_expresses_gene \
  --edge-offset 35000 --edge-limit 100000 \
  --evidence-limit 0 \
  --chunk-size 5000 \
  --json
```

3. Interruption/resume smoke for any approved write window:

```bash
uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation enhancer_regulates_gene \
  --edge-offset 65000 --edge-limit 50000 \
  --evidence-offset 65000 --evidence-limit 50000 \
  --chunk-size 5000 \
  --max-chunks 2 \
  --write --json

uv run python -m manage_db.sync_parquet_edges_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --lamin-instance jkobject/jouvencekb \
  --relation enhancer_regulates_gene \
  --edge-offset 65000 --edge-limit 50000 \
  --evidence-offset 65000 --evidence-limit 50000 \
  --chunk-size 5000 \
  --resume-chunk 2 \
  --idempotence-passes 2 \
  --verify-selected-live \
  --write --json
```

## Backup, rollback, and supervision requirements before Wave-4 write

Before any approved `--write` wave:

1. Confirm the live LaminDB instance is `jkobject/jouvencekb`.
2. Stop/avoid concurrent live writers.
3. Create a restorable backup of the local LaminDB SQLite cache, record path, size, and checksum in `artifacts/reports/<wave-task>/`.
4. Record restore procedure: stop writers, copy backup over the local cache DB, reconnect/sync LaminDB cache as appropriate, then rerun selected-window verification.
5. Use explicit relation windows and keep `--chunk-size` bounded, initially `5000`.
6. Prefer `--max-chunks` smoke writes before larger windows.
7. Run `--idempotence-passes 2` and `--verify-selected-live` on approved live write windows.
8. Keep reports under `artifacts/reports/<task-id>/`; do not commit backup DB files and do not write canonical KG Parquets from this loader.

## Verification commands for this task

```bash
uv run python -m py_compile manage_db/sync_parquet_edges_to_lamindb.py
uv run --group dev pytest tests/test_sync_parquet_edges_to_lamindb.py -q
```

Observed result: `7 passed in 9.64s`.
