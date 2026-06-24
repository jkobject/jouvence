# 01 — LaminDB

## Current state

- `t_a41bde99` — `LAMIN-DESIGN`: `design done`. Design exists in `docs/lamindb_kg_export_design.md`.
- `t_471cfae2` — `LAMIN-BUILD`: `validated`/reviewed for artifact registry only.
  - 79 canonical KG v2 artifacts registered/handled.
  - Covers nodes/edges/evidence/features as LaminDB artifacts/metadata.
  - Artifact registry sync alone did **not** make `lnschema_txgnn` complete/queryable.

## Open work

- `t_c51d9a5b` — `LAMIN-SCHEMA`: local self-managed config activation performed by updating `~/.lamin/instance--jkobject--jouvencekb.env` and `~/.lamin/current_instance.env` so `lamindb_instance_schema_str=bionty,pertdb,lnschema_txgnn`; status is `review-required`, not production/full done.
- `t_edb59ab8` — validate activation/exact-ID registry.
- `t_59139647` — review activation/exact-ID registry.
- `t_3d4fa114` — audit/design full `lnschema_txgnn` node/edge/evidence schema and query API; activation alone is not schema completeness.
- `t_ad32fe14` — implement first ergonomic KG query helpers, starting with diseases associated with a gene.
- `t_7120233a` — validate KG query helpers.
- `t_3a388f93` — review full schema/query API plan.

## Definition of done

`lnschema_txgnn` is actually configured/usable for `jkobject/jouvencekb`, exact-ID sync probes pass, and validator/reviewer accept. Artifact registry alone is not enough.

1. Canonical artifact registry sync is idempotent and reviewed. ✅
2. `lnschema_txgnn` is locally configured/activated. ✅ review-required
3. Exact-ID node registry pilot works for canonical IDs. ⏳
4. Edge/evidence/feature schema coverage and query helpers pass validation/review. ⏳
5. N11/Lamin diagnostics no longer misleadingly show unexplained `ModuleWasntConfigured`. ⏳
