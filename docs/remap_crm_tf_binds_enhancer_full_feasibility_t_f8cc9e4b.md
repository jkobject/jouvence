# ReMap CRM/peak `tf_binds_enhancer` full-scale feasibility gate

Kanban task: `t_f8cc9e4b`  
Status: `blocked` / `review-required`; staged-only; no canonical writes.

## What I checked

- Accepted bounded pilot `t_a405fe3b`: 1,224,536 edges / 6,356,561 evidence rows from first80 chr1 CRM intervals and bounded all-peak overlap sample.
- Accepted full CRM sidecar `t_5968ce32`: 3,327,980 full CRM intervals, 48,768,788 compact sharded summary rows, and 24,453,482,386 TF × CRM × enhancer candidate support rows explicitly **not materialized**.
- Older bounded all-chromosome support lineage `t_b599d3bb` and current ReMap TODO/status docs.

## Feasibility result

I did **not** write new active `edges/tf_binds_enhancer.parquet` or `evidence/tf_binds_enhancer.parquet` for this card, because the available accepted full CRM artifact is intentionally compact and not a TF-enhancer edge table. Materializing the full product naively would require about 24,453,482,386 candidate rows before preserving the accepted pilot's observed-peak evidence multiplicity.

Using the accepted pilot parquet density as a rough lower-bound storage estimate:

- edge parquet lower-bound: ~1050.63 GiB
- one aggregate evidence row per candidate lower-bound: ~3802.70 GiB
- combined lower-bound: ~4853.33 GiB

This is still a lower bound: the accepted bounded model includes observed ReMap peak evidence plus CRM reconstructed support, while the local full source reviewed here is the CRM BED/compact sidecar, not a full local all-peak overlap table.

## Why this blocks acceptance as written

The card asks for a full/unbounded staged candidate with edge/evidence Parquets while preserving the accepted CRM/peak evidence semantics. The previously accepted full-scale CRM lineage explicitly avoided the full TF × CRM × enhancer product and stores compact per-enhancer/per-TF aggregates instead. Emitting active `tf_binds_enhancer` edges from those aggregates without a reviewed reduction policy would silently change semantics.

## Decision needed

1. Authorize a compact aggregate staged edge/evidence schema that changes the full artifact from per-observed-peak evidence to aggregate CRM support evidence; or
2. Provision/authorize external chunked compute/storage and full all-peak overlap source acquisition for a tens-of-billions-row materialization; or
3. Keep full ReMap CRM as a sharded support/QA sidecar only until a stricter reduction policy exists.

## Artifacts written

- `artifacts/staged/t_f8cc9e4b/manifest.json`
- `artifacts/reports/t_f8cc9e4b_feasibility_gate.json`
- `docs/remap_crm_tf_binds_enhancer_full_feasibility_t_f8cc9e4b.md`

No canonical GCS or local canonical KG writes were performed.
