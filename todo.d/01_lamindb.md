# 01 — LaminDB

_Status snapshot: 2026-07-22 15:18 CEST._

Kanban board `txgnn` remains the live source of truth. Counter evidence below is explicitly dated; this mirror does not imply a fresh database read.

Heavy-job guardrail: full/bulk LaminDB syncs or registry scans must run on `txgnn-worker` or another explicitly approved in-region worker with source `gs://jouvencekb/kg/v2`. Do not run heavy LaminDB reads/writes from the Mac through `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE.

## Canonical source denominator

Canonical Parquet inventory currently contains:

- **15/15 node files**;
- **55,523,691 physical node rows** total;
- **52,565,491 model/biomedical node rows** when graph-disconnected `paper` (2,958,199) and `dataset` (1) metadata nodes are excluded;
- **100,083,633 canonical edge rows** across **41/67 declared relations**, after the independently accepted marker-last `disease_associated_protein` promotion;
- **76,601,052 canonical evidence rows**, including the accepted 35,839-row `disease_associated_protein` evidence object;
- **230,874,162 rows** in the current Lamin ingestion denominator: 52,565,491 nodes + 101,743,458 edge target rows + 76,565,213 evidence target rows.

The dated Lamin edge-ingestion denominator is larger than the current 100,083,633-row canonical inventory because its accepted target contract already included other later relation material, while its 76,565,213-row evidence target is now smaller than the 76,601,052-row canonical evidence inventory because it predates the accepted `disease_associated_protein` evidence object. That promotion updates the canonical KG inventory only: it does **not** change the separately dated Lamin denominator, accepted numerator, or physical readback. Do not silently mix these inventories.

## Live `jkobject/jouvencekb` ingestion

Latest durable accepted ledger, sealed in 2026-07-18 task evidence:

| Layer | Accepted | Denominator | Status |
| --- | ---: | ---: | --- |
| nodes | 3,771,054 | 52,565,491 | partial |
| edges | 3,971,264 | 101,743,458 | partial |
| evidence | 3,929,167 | 76,565,213 | partial |
| **total** | **11,671,485** | **230,874,162** | **partial** |

The latest sealed physical readback is also from 2026-07-18: 3,771,054 nodes + 4,141,291 edges + 4,099,167 evidence = **12,011,512 physical rows**. The +170,027 edge and +170,000 evidence difference is physical but uncredited. No newer mismatch-0 database readback is claimed here.

## Human ENSG-only implementation accepted; data migration outstanding

PR #12 merged at `2786d847` on 2026-07-21. The corrected implementation head `7f300b8` was independently accepted by `t_0b806c0e`, and producer `t_5c938f23` closed `validated`. The earlier `t_8b9cdabc` production candidate is rejected historical evidence. The production-scale staged rebuild and canonical node migration were not executed:

- current canonical Gene source: 267,830 IDs = 81,715 human ENSG + 27,610 human NCBI + 158,505 non-human Ensembl homologues;
- target canonical Gene identity: 81,715 human ENSG only;
- NCBI IDs are aliases/provenance, with authoritative endpoint remap or explicit quarantine required before removal;
- non-human homologue nodes and `gene_ortholog_gene` are excluded from the human canonical candidate;
- live `nodes/gene.parquet` remains the old generation `1781617033173178`; no canonical Gene-node or LaminDB migration is claimed.

`t_ce839966` and `t_075f5353` are superseded historical +158,505 Lamin Gene plans. They remain inert and must not run. Their 2026-07-18 readbacks remain useful as dated counter evidence only.

## Current boundary

Do not schedule a new bulk Lamin Gene wave against the old 267,830-row denominator. First run and review a fresh production-scale ENSG rebuild and explicit canonical promotion, then produce a fresh source↔Lamin denominator and mismatch-0 readback. Keep accepted and physical counters separate until data migration acceptance closes.

## What is and is not complete

- Canonical Parquet node inventory: **complete for the 15 active node types**.
- Canonical relation inventory: **41/67 declared relations physically canonical** in the accepted current overlay; relation review/backlog is separate from Lamin ingestion and PR #43's corrected 67-relation ledger remains changes-requested/pending.
- LaminDB artifact catalog/schema activation: implemented and reviewed in bounded form.
- Full row-level Lamin node/edge/evidence ingestion: **not complete** (11,671,485/230,874,162 accepted as of the dated 2026-07-18 evidence).
- Query helpers and full exact-ID coverage: not a completed global acceptance gate.

## Definition of done

1. Exact `jkobject/jouvencekb` identity and `lnschema_txgnn` activation verified.
2. The target denominator is rebased after the reviewed ENSG-only decision, then every included row is durably ingested or explicitly excluded.
3. Every credited wave has `rc=0`, hash-bound acknowledgements, selected-live edge/evidence equality and mismatch 0.
4. Exact-ID node/edge/evidence/feature query probes pass.
5. Independent review accepts the final ledger, query surface and evidence packet.
