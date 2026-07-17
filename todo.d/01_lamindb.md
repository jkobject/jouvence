# 01 — LaminDB

_Last verified: 2026-07-15 15:09 CEST. Kanban board `txgnn` remains the live source of truth._

Heavy-job guardrail: full/bulk LaminDB syncs or registry scans must run on `txgnn-worker` or another explicitly approved in-region worker with source `gs://jouvencekb/kg/v2`. Do not run heavy LaminDB reads/writes from the Mac through `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE.

## Canonical source denominator

Canonical Parquet inventory currently contains:

- **15/15 node files**;
- **55,523,691 physical node rows** total;
- **52,565,491 model/biomedical node rows** when graph-disconnected `paper` (2,958,199) and `dataset` (1) metadata nodes are excluded;
- **100,080,390 canonical edge rows**;
- **76,565,213 canonical evidence rows**;
- **230,874,162 rows** in the current Lamin ingestion denominator: 52,565,491 nodes + 101,743,458 edge target rows + 76,565,213 evidence target rows.

The edge ingestion denominator is larger than the older 100,080,390 snapshot because later reviewed/promoted relation material is included in the Lamin target contract. Do not silently mix these dated inventories.

## Live `jkobject/jouvencekb` ingestion

Strict accepted ledger at the current recovery boundary:

| Layer | Accepted | Denominator | Status |
| --- | ---: | ---: | --- |
| nodes | 3,771,054 | 52,565,491 | partial |
| edges | 3,956,264 | 101,743,458 | partial |
| evidence | 3,914,167 | 76,565,213 | partial |
| **total** | **11,641,485** | **230,874,162** | **5.04%** |

- Accepted checkpoint: **13,880,000** in `enhancer_regulates_gene`.
- Previously sealed physical baseline at that checkpoint: 3,771,054 nodes + 3,966,264 edges + 3,924,167 evidence = **11,661,485 physical rows**. The 20,000-row difference from the strict ledger consists of two prior 5k edge + 5k evidence prefixes not yet adopted into a conforming `product_delta`.
- One additional hash-bound candidate prefix `[13,880,000,13,885,000)` may add 5,000 edges + 5,000 evidence, but it is **not credited** until rollback recovery/parity establishes whether it survived.
- Current SQLite file is approximately **16.7 GB**. This is the database file size, not the RAM requirement.
- No product writer is active during recovery.

## Active recovery

`t_7c4c37b7` is running a copy-only rollback recovery/parity check. The accepted producer interpreter preflight passed (`pandas`, `pyarrow`, row-group reader and fixture). The live DB remains byte-read-only; only a task-local copy is opened by SQLite. At the latest verified heartbeat:

- copy hashes/drift checks passed far enough to open/recover the copy;
- copy-only SQLite rollback recovery/open sealed `rc=0` with `query_only` proof;
- exact selected-key parity for `[13,880,000,13,885,000)` and `[13,885,000,13,890,000)` is running;
- accepted ledger/checkpoint remain unchanged until classification.

Product-owner decision: keep the current SQLite/schema/index representation for now. Do not start an index/storage overhaul as part of this recovery. Historical warm-run throughput was genuinely better; retain cold-start/cache/index-growth latency as an unresolved performance issue.

## What is and is not complete

- Canonical Parquet node inventory: **complete for the 15 active node types**.
- Canonical relation inventory: **40/67 declared relations physically canonical** in the latest schema snapshot; relation review/backlog is separate from Lamin ingestion.
- LaminDB artifact catalog/schema activation: implemented and reviewed in bounded form.
- Full row-level Lamin node/edge/evidence ingestion: **not complete** (11,641,485/230,874,162 strictly accepted).
- Query helpers and full exact-ID coverage: not a completed global acceptance gate.

## Definition of done

1. Exact `jkobject/jouvencekb` identity and `lnschema_txgnn` activation verified.
2. All 230,874,162 target rows durably ingested or explicitly excluded by a reviewed denominator change.
3. Every credited wave has `rc=0`, hash-bound acknowledgements, selected-live edge/evidence equality and mismatch 0.
4. Exact-ID node/edge/evidence/feature query probes pass.
5. Independent review accepts the final ledger, query surface and evidence packet.
