# Source-native expansion staged-output validation report

Kanban QA card: `t_9d495e51`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Original validation date: 2026-06-22  
Re-run/update date: 2026-06-23  
Canonical promotion: **not performed from this QA card**

## Verdict

**PASS for status/validation closure under the updated routing, with promotion constraints.**

This re-run preserves the original validation results for IntAct, BioGRID, miRNA, and the accepted ReMap chr22 compact prototype, and adds validation of the newly accepted bounded ReMap CRM support/QA pilot (`t_3b8a2c4d`). Jérémie explicitly stopped/deferred the all-peak ReMap finalization (`t_8bc6dacf`), so this card is no longer blocked waiting for an all-chromosome all-peak ReMap prefix. The ReMap-family status is now: all-peak observed-binding staging is deferred/stopped; the accepted current artifact is the bounded chr1 first10k CRM support/QA pilot only, with `crm_aggregated_support` semantics and no canonical promotion authority.

Promotion recommendation:

- Non-ReMap Part 2/source-native artifacts should continue through their separate promotion pipeline (`t_61fabcf3` -> `t_ce6e158c` -> `t_17cfc462`), not this full/all-source card.
- Do **not** promote all-peak ReMap from this card: no accepted all-chromosome all-peak prefix exists and the user stopped that path.
- Do **not** promote CRM as primary `observed_binding`: the accepted CRM artifact is bounded support/QA/triage only.

## Inputs and stale/final artifact selection

| Area | Cards / handoffs read | Artifact used by this QA | Status |
|---|---|---|---|
| IntAct PPI | `t_100231b1`, reviewer `t_0964be36`; stale `t_6ca72196` noted | `gs://jouvencekb/kg/staging/source-native-expansion/intact-protein-interactions-policy-fixed/runs/20260622T122314Z-bounded100k/` | Accepted bounded recovery staging; not canonical-ready because bounded and no node-root anti-join. Stale `.omoc/staging/intact-protein-interactions-20260621` was not used. |
| BioGRID physical/PTM/complex policy | `t_28f83a7b`, accepted PTM review `t_d64b99c0` | `gs://jouvencekb/kg/staging/source-native-expansion/biogrid-ptm-xref/` | Accepted staged PTM + physical PPI; complex outputs intentionally zero without source-native complex-member source. |
| miRNA miRBase/miRTarBase | `t_1734823c` -> fix `t_95bbd18c` -> accepted review `t_08770b04` | `gs://jouvencekb/kg/staging/source-native-expansion/mirna-targets-real/` | Accepted staged miRTarBase gene-target tranche after processing-edge/source-gate fix. |
| ReMap all-peak compact prototype | old `t_8ca02356` superseded; chunked chr22 `t_faa4cd26`/`t_d273b058`; compact prototype `t_4f108a31`/`t_6ae721d2` | `gs://jouvencekb/kg/staging/source-native-expansion/remap-tf-binds-enhancer-compact/chr22-20k-compact-t_4f108a31/` | Prototype validates, but it remains chr22-only and is not an all-chromosome promotion artifact. |
| ReMap all-peak full run | `t_5738004a`, `t_8fff8356`, `t_17f2b3d5`, `t_3479936e`, `t_8bc6dacf` | none accepted as final | Stopped/deferred by user decision; do not wait for it or promote it unless explicitly reauthorized. |
| ReMap CRM support/QA pilot | `t_206c9a35` -> `t_3b8a2c4d`, reviewer `t_281f188d` | `.omoc/staging/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/` | Accepted bounded chr1 first10k staged-only support/QA pilot; not primary observed-binding evidence and not canonical promotion material. |

## Commands run

Original 2026-06-22 QA pass, from `/Users/jkobject/.openclaw/workspace/work/txgnn`:

```bash
uv run python -m py_compile \
  manage_db/build_intact_protein_interactions.py \
  manage_db/prepare_real_mirna_sources.py \
  manage_db/build_staged_mirna_targets.py \
  .omoc/scripts/stage_biogrid_categorized.py \
  .omoc/scripts/stage_remap_tf_binds_enhancer.py \
  .omoc/scripts/stage_remap_tf_binds_enhancer_compact.py

uv run --group dev pytest \
  tests/test_build_intact_protein_interactions.py \
  tests/test_biogrid_categorized_stage.py \
  tests/test_prepare_real_mirna_sources.py \
  tests/test_build_staged_mirna_targets.py \
  tests/test_stage_remap_tf_binds_enhancer.py -q
# 33 passed in 1.18s
```

2026-06-23 re-run/update after CRM support/QA acceptance:

```bash
uv run python -m py_compile \
  manage_db/build_intact_protein_interactions.py \
  manage_db/prepare_real_mirna_sources.py \
  manage_db/build_staged_mirna_targets.py \
  .omoc/scripts/stage_biogrid_categorized.py \
  .omoc/scripts/stage_remap_tf_binds_enhancer.py \
  .omoc/scripts/stage_remap_tf_binds_enhancer_compact.py \
  .omoc/scripts/stage_remap_crm_tf_binds_enhancer_support.py

uv run --group dev pytest \
  tests/test_build_intact_protein_interactions.py \
  tests/test_biogrid_categorized_stage.py \
  tests/test_prepare_real_mirna_sources.py \
  tests/test_build_staged_mirna_targets.py \
  tests/test_stage_remap_tf_binds_enhancer.py -q
# 38 passed in 1.87s
```

Machine-readable validation outputs:

- Original independent DuckDB checks: `.omoc/reports/source_native_expansion_validation_t_9d495e51.json`
- 2026-06-23 CRM rerun checks: `.omoc/reports/source_native_expansion_validation_t_9d495e51_rerun_20260623.json`

## Validation results

### IntAct `protein_interacts_protein`

Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/intact-protein-interactions-policy-fixed/runs/20260622T122314Z-bounded100k/`

Remote listing from original QA: 9 objects, 291,143,217 bytes / 277.66 MiB.

| Check | Result |
|---|---:|
| edge rows | 34,515 |
| evidence rows | 46,425 |
| distinct edge keys | 34,515 |
| rejected rows | 53,575 |
| edges without evidence | 0 |
| evidence without edge | 0 |
| active evidence with any MI:0914 | 0 |
| active MI:0914-only evidence | 0 |
| rejected MI:0914-only rows | 28,198 |
| unsupported self-loop rejects | 19 |
| rejected source payload missing raw MITAB | 0 |

Caveat: this is the reviewer-accepted bounded recovery artifact (`--max-rows 100000`, `--negative-max-rows 10000`) and was built without `--node-root`; endpoint anti-join is therefore not canonical-grade. It is acceptable as staged recovery evidence only, not as a standalone canonical-promotion basis.

### BioGRID category separation / PTM / physical PPI

Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/biogrid-ptm-xref/`

Remote listing from original QA: 13 objects, 18,510,623 bytes / 17.65 MiB.

| Check | Result |
|---|---:|
| `protein_interacts_protein` edges | 3,550 |
| `protein_interacts_protein` evidence rows | 12,288 |
| `protein_has_ptm_site` edges | 28,169 |
| `protein_has_ptm_site` evidence rows | 62,096 |
| `ptm_site` nodes | 28,169 |
| PTM site endpoint misses (`edge.y_id` -> staged `ptm_site.id`) | 0 |
| PTM edges without evidence | 0 |
| PTM evidence without edge | 0 |
| PPI edges without evidence | 0 |
| PPI evidence without edge | 0 |
| PPI x protein anti-join against canonical `protein.id`/`protein.uniprot_id` | 0 |
| PPI y protein anti-join against canonical `protein.id`/`protein.uniprot_id` | 0 |
| PTM x protein anti-join against canonical `protein.id`/`protein.uniprot_id` | 0 |
| complex Parquet outputs non-empty | 0 |

Evidence class separation observed in BioGRID PPI evidence:

| Evidence class | Rows |
|---|---:|
| `complex_or_cofractionation_association` | 10,301 |
| `binary_physical` | 1,615 |
| `biochemical_or_ptm_like_activity` | 372 |

Interpretation: BioGRID physical/PTM separation validates. Complex outputs remain intentionally empty because no explicit complex-member source was approved; they must not be fabricated. Genetic interactions were not emitted into this physical/PTM staged tranche.

### miRNA miRBase / miRTarBase

Remote prefix: `gs://jouvencekb/kg/staging/source-native-expansion/mirna-targets-real/`

Remote listing from original QA: 15 objects, 100,649,833 bytes / 95.99 MiB.

| Check | Result |
|---|---:|
| `mirna` nodes | 3,929 |
| `mirna_targets_gene` edges | 351,958 |
| `mirna_targets_gene` evidence rows | 868,896 |
| `mirna_targets_transcript` edges | 0 |
| `mirna_precursor_produces_mature_mirna` processing edges | 1,707 |
| target-edge miRNA source misses | 0 |
| processing-edge x misses | 0 |
| processing-edge y misses | 0 |
| gene edges without evidence | 0 |
| gene evidence without edge | 0 |
| gene endpoint anti-join against canonical `nodes/gene.id` | 0 |
| transcript target endpoint anti-join | 0 (empty transcript edge set) |
| source gate | `approved` |
| source gate approved for staged-source-backed sample | `true` |
| DIANA-TarBase | deferred separately |
| canonical writes | `false` |

Policy checks:

- miRTarBase 9.0 target endpoint is gene-level only, so only `mirna_targets_gene` is populated.
- `mirna_targets_transcript` is correctly empty; no main transcript was chosen and no gene-to-transcript forcing occurred.
- Alias-resolved ENST precursor processing rows are explicitly omitted pending an approved cross-layer relation; remaining processing edges have clean staged miRNA endpoints.
- DIANA-TarBase is deferred separately and no longer poisons the miRTarBase-only source gate.

### ReMap all-peak `tf_binds_enhancer` chr22 compact prototype

Accepted compact prototype prefix checked in original QA: `gs://jouvencekb/kg/staging/source-native-expansion/remap-tf-binds-enhancer-compact/chr22-20k-compact-t_4f108a31/`

Remote listing from original QA: 6 objects, 221,220,677 bytes / 210.97 MiB.

| Check | Result |
|---|---:|
| `tf_binds_enhancer` edges | 1,657,030 |
| evidence rows | 1,657,030 |
| duplicate active edges | 0 |
| edges without observed binding evidence | 0 |
| evidence without edge | 0 |
| `tf_regulates_gene` edge rows | 0 |
| `tf_regulates_gene` evidence rows | 0 |
| TF x endpoint anti-join against canonical `nodes/gene.id` | 0 |
| enhancer y endpoint anti-join against canonical `nodes/enhancer.id` | 0 |
| evidence type | `observed_binding` only |
| chromosome | `22` only |

This confirms the accepted compact prototype semantics, including no forbidden `tf_regulates_gene` output. It is not all-chromosome final staging.

### ReMap all-peak full-run status

The prior blocking condition is now resolved by product/routing decision, not by all-peak completion:

- Old raw/chunked all-chromosome card `t_8ca02356` is superseded and must not be resumed.
- `t_5738004a`, `t_8fff8356`, `t_17f2b3d5`, and `t_3479936e` are diagnostics/superseded attempts, not accepted all-chromosome final outputs.
- `t_8bc6dacf` was stopped by user decision; all-peak ReMap finalization should not auto-resume.
- Therefore no all-peak ReMap canonical-promotion recommendation is made here.

### ReMap CRM `tf_binds_enhancer` support/QA pilot

Accepted local staged root: `.omoc/staging/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`

Reviewed/accepted by `t_281f188d` as bounded staged-only support/QA, not canonical promotion.

Independent 2026-06-23 DuckDB checks against the local Parquets and `.omoc/gcs-cache/kg-v2` endpoint nodes:

| Check | Result |
|---|---:|
| CRM intervals | 10,000 |
| exploded regulator mentions | 331,399 |
| interval/enhancer overlap rows | 702,782 |
| accepted interval/enhancer overlap rows | 644,279 |
| detailed support sample rows materialized | 20,000 |
| compact support summary rows | 338,407 |
| distinct candidate TFs in summary | 1,110 |
| distinct candidate enhancers in summary | 337,297 |
| exact candidate support rows represented by TF summary | 138,048,185 |
| exact candidate support rows represented by enhancer summary | 138,048,185 |
| summary TF endpoint anti-join against `nodes/gene.id` | 0 |
| summary enhancer endpoint anti-join against `nodes/enhancer.id` | 0 |
| detailed sample TF endpoint anti-join | 0 |
| detailed sample enhancer endpoint anti-join | 0 |
| detailed sample relation rows | `tf_binds_enhancer`: 20,000 |
| detailed sample evidence type rows | `crm_aggregated_support`: 20,000 |
| detailed sample `observed_binding` rows | 0 |
| `tf_regulates_gene` relation/columns detected | 0 / false |
| canonical writes | false |
| independent rerun `ok` | true |

TF mapping status from independent rerun:

| Status | Mentions | Distinct symbols |
|---|---:|---:|
| accepted | 324,273 | 1,132 |
| ambiguous | 146 | 2 |
| rejected | 6,980 | 28 |

CRM caveats preserved:

- CRM rows do not preserve per-experiment source accession.
- CRM column 5 is an aggregated support/count score, not a raw per-experiment peak score.
- Sampled CRM rows lack cell/biotype context.
- CRM candidates are support/QA/triage only and must not replace primary `observed_binding` without explicit reviewer/user approval.
- This pilot does not infer or write `tf_regulates_gene`.

## Canonical promotion recommendation

Do **not** promote canonical KG/GCS directly from this validation card.

Recommended routing:

1. Treat this card as closed validation/status reconciliation for the full source-native wave after the ReMap all-peak stop decision.
2. Use `t_61fabcf3` / `t_ce6e158c` / `t_17cfc462` for the non-ReMap Part 2 canonical promotion path.
3. Keep all-peak ReMap deferred/stopped unless Jérémie explicitly reauthorizes it.
4. Keep CRM ReMap as bounded support/QA/triage only; it is not a primary `observed_binding` replacement and not an all-chromosome promotion artifact.
