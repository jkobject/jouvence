# Mutation remaining genomic-direct relations next-state decision

Kanban task: `t_8de911c0`  
Date: 2026-06-24  
Scope: `mutation_in_gene` and `mutation_overlaps_enhancer` only. No canonical KG writes.

Supersession note, 2026-06-24: the `mutation_in_gene` next-state in this historical decision doc was superseded after the full `t_2bb8e7de` all-part candidate was independently accepted and promotion card `t_1cfcd48f` completed a relation-specific canonical write/review handoff. Current `mutation_in_gene` status is `canonical promoted`/`review-required`; see `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`. The `mutation_overlaps_enhancer` coordinate-overlap-alone rejection remains current, but `t_0aa76f3b` adds the caveat that externally support-gated overlaps can be staged as evidence-backed edge candidates after support-source/density/leakage review.

## Bottom line

| Relation | Next state | Recommendation |
| --- | --- | --- |
| `mutation_in_gene` | `staged bounded containment candidate / not promotion-ready full scope` | Keep the corrected `t_5120f845` first-part containment-gated staged candidate as the reviewable bounded artifact. Do not promote yet; require reviewer acceptance plus a full all-25-part rebuild/validation before a promotion card. |
| `mutation_overlaps_enhancer` | `coordinate-only context/support feature; support-gated staged edge candidate possible / no canonical write` | Do not promote raw coordinate-overlap rows as canonical edges. If external support from eQTL, GWAS/L2G, ClinVar/OpenTargets variant disease/gene evidence, MPRA, allele-specific regulatory evidence, or similar regulatory/disease databases is present, a bounded evidence-backed edge candidate may be staged with explicit support evidence, density, and leakage policy; canonical write still requires tester/reviewer gate. |

No broad mutation promotion card was created. No relation-specific promotion card was created because neither remaining relation is review-ready for canonical promotion today.

## Audit artifacts produced by this card

- Script: `artifacts/reports/t_8de911c0_mutation_remaining_decision_audit.py`
- JSON report: `artifacts/reports/t_8de911c0_mutation_remaining_decision_audit.json`

The audit used existing `artifacts/` staged candidates and docs only. It did not create or use a new `.omoc` cache. Local FUSE probes for canonical files returned `Device not configured` during this run; `gsutil ls` was used as a fallback canonical existence check. `gsutil` listed canonical `mutation_affects_transcript` edge/evidence objects and matched no canonical `mutation_in_gene` or `mutation_overlaps_enhancer` edge/evidence objects.

## `mutation_in_gene`

### Trusted containment source/path

Trusted coordinate containment source identified and already implemented in the corrected staged builder:

- OpenTargets Platform 26.03 `target` dataset.
- Field: `target.genomicLocation` (`chromosome`, `start`, `end`, `strand`).
- Join key: `target.id == variant.transcriptConsequences[].targetId`.
- Point test: canonical mutation coordinate from OpenTargets `variant.chromosome`/`variant.position` must satisfy `chromosome == target.genomicLocation.chromosome` and `start <= position <= end`.
- Evidence source label: `OpenTargets/target.genomicLocation`, predicate `policy_filtered_variant_transcript_consequence_target_gene_with_target_genomic_location_containment`, source dataset `variant+target`.

This fixes the prior reviewer objection: broad VEP `targetId` semantics are not sufficient for physical gene containment.

### Current bounded candidate counts

Corrected containment-gated staged candidate:

`artifacts/staged/t_5120f845/mutation-genomic-direct-contained-20260623-smoke`

Audit highlights from `artifacts/reports/t_8de911c0_mutation_remaining_decision_audit.json` and `docs/mutation_in_gene_containment_gate_t_5120f845.md`:

| Metric | Count |
| --- | ---: |
| Input variants | 25,000 |
| Canonical mutation matches | 11,780 |
| Exploded transcript consequence rows | 762,741 |
| Rows after allowed consequence filter | 10,853 |
| Target gene intervals loaded | 78,691 |
| Gene containment passes | 10,852 |
| Gene coordinate containment rejects | 1 |
| Missing/unproven interval rejects | 0 |
| `mutation_in_gene` edge rows | 10,852 |
| `mutation_in_gene` evidence rows | 10,852 |
| Unique mutation endpoints | 10,660 |
| Unique gene endpoints | 169 |
| Duplicate edge keys | 0 |
| Duplicate evidence keys | 0 |
| Edges without evidence | 0 |
| Evidence without edge | 0 |
| Leakage hits for L2G/GWAS/credible-set/study-locus terms | 0 |
| Evidence rows with containment proof | 10,852 |

The bounded candidate is mechanically coherent and semantically improved versus the rejected broad VEP candidate. It is still first-part / `--max-variants 25000` scope, not full production scope.

### Decision

`mutation_in_gene` should not be canonical-promoted from the old dense VEP-only staging, and should not be promoted yet from the bounded first-part candidate. Its next state is:

```text
staged bounded containment candidate; review bounded semantics/counts; full all-part containment rebuild required before promotion
```

A future relation-specific promotion card becomes appropriate only after:

1. the reviewer/tester accepts the bounded containment semantics;
2. the builder runs the all-25-part OpenTargets variant rebuild with the same `target.genomicLocation` containment gate;
3. endpoint/evidence, duplicate-key, leakage, containment-proof, and count audits pass on the full candidate;
4. canonical FUSE/GCS availability is healthy enough for final anti-joins or equivalent GCS-backed validation.

## `mutation_overlaps_enhancer`

### What exists today

Current staged/context candidate:

`artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d`

Audit highlights:

| Metric | Count |
| --- | ---: |
| Input variants | 25,000 |
| Canonical mutation matches | 11,780 |
| Downstream/context-supported overlap mutations | 5,851 |
| Enhancer interval endpoints | 115,543 |
| `mutation_overlaps_enhancer` edge rows | 1,670,937 |
| `mutation_overlaps_enhancer` evidence rows | 1,670,937 |
| Duplicate edge keys | 0 |
| Duplicate evidence keys | 0 |
| Edges without evidence | 0 |
| Evidence without edge | 0 |
| Leakage hits for L2G/GWAS/credible-set/study-locus terms | 0 |
| Evidence rows with downstream gate/support metadata | 1,670,937 |

Earlier tester validation also found endpoint/evidence wiring passed and the downstream gate was present, but the artifact is extremely dense: about 285.6 enhancer-overlap edges per supported mutation on this bounded first-part smoke.

### Policy decision

The downstream association gate is useful only as a triage/context filter. It does not convert coordinate overlap into direct regulatory evidence. A canonical `mutation_overlaps_enhancer` edge would risk implying that the mutation perturbs enhancer activity or downstream expression, which is not supported by interval overlap alone.

Therefore raw `mutation_overlaps_enhancer` should be moved out of “maybe canonical” ambiguity and treated as:

```text
not canonical edge material from coordinate overlap alone; retain as staged/context/support feature sidecar unless external disease/regulatory support is used to build an explicit evidence-backed edge candidate, preferably with source-native regulatory or allele-specific evidence
```

### `t_0aa76f3b` support-gated caveat and bounded pilot

User correction accepted: future workers should not summarize the relation as plain “feature-only” without the support-gated caveat. The updated target is:

- Coordinate overlap alone: feature/context/support sidecar only; not canonical graph topology.
- Externally support-gated overlap: staged evidence-backed edge candidate is appropriate when every edge carries support-source context and leakage guardrails.
- Canonical write: still blocked until independent tester/reviewer acceptance; no canonical write was performed by `t_0aa76f3b`.

Support sources/fields selected for the bounded pilot:

- GWAS/L2G: canonical `mutation_associated_gene` evidence with `source_dataset=l2g`, plus `mutation_associated_disease` with `source_dataset=gwas_credible_sets`; preserve `study_id`, `source_record_id`, `evidence_score`, `p_value` when present, target gene/disease, and predicate.
- ClinVar/OpenTargets disease/phenotype support: canonical `mutation_associated_disease` with `source_dataset=eva`/`eva_somatic` and `mutation_associated_phenotype` with `source_dataset=evidence_eva`; preserve clinical predicate/significance, score, disease/phenotype endpoint, and source record.
- Other available current KG support: `mutation_causes_protein_change` and `mutation_affects_molecule_response` as supporting context, not enhancer-regulatory proof.
- Not found in the current KG support layer during this pilot: eQTL, caQTL/ATAC-QTL, MPRA, or allele-specific enhancer-activity tables. These remain preferred future support sources when available.

Bounded pilot artifacts:

- Stage root: `artifacts/staged/t_0aa76f3b/mutation-overlaps-enhancer-support-gated-20260624/`
- Report: `artifacts/reports/t_0aa76f3b_support_gated_mutation_enhancer_report.json`
- Build script: `artifacts/reports/t_0aa76f3b_build_support_gated_mutation_enhancer.py`

Density/results:

| Metric | Count |
| --- | ---: |
| Prior `t_79f8684d` overlap rows inspected | 1,670,937 |
| Prior overlap unique mutations | 5,851 |
| Prior overlap unique enhancers | 115,543 |
| Pilot support-gated mutations | 200 |
| Pilot support-gated edges | 149,107 |
| Pilot evidence rows | 149,107 |
| Pilot unique enhancers | 8,353 |
| Mean pilot edges per mutation | 745.535 |
| Edges without evidence / evidence without edge | 0 / 0 |

The prior `t_79f8684d` artifact was already downstream-support-gated, so the new pilot does not claim a row-count reduction against that artifact. Its added value is semantic: the staged edge/evidence rows now carry explicit support context (`GWAS/L2G`, `ClinVar/EVA`, OpenTargets disease/gene, protein-change context), score/study/source-record fields where available, and a leakage policy instead of implying raw coordinate overlap.

Recommended target if kept:

- Feature/support sidecar for coordinate-only overlap, e.g. `features/mutation_enhancer_overlap_context.parquet`, or a clearly named staged/support namespace.
- Evidence-backed staged edge candidate for externally support-gated overlap, e.g. the `t_0aa76f3b` stage root above, with one evidence row per edge and support summary sidecar.
- Do not write to `edges/mutation_overlaps_enhancer.parquet` in canonical KG from the current overlap artifact.
- Do not use as observed regulatory evidence in GNN labels or target leakage-sensitive training splits.

### Required policy for any future canonical candidate

A future canonical edge candidate must replace the downstream-association-only gate with source-native regulatory or allele-specific evidence, plus explicit density and leakage controls. Required evidence/policy elements:

1. Direct allele-specific regulatory/enhancer-activity evidence, for example MPRA/CRE perturbation, caQTL/ATAC-QTL/eQTL with clear regulatory semantics, fine-mapped causal credible set plus enhancer activity/target evidence, or a source-native variant-to-regulatory-feature assertion with calibrated score.
2. Evidence semantics must distinguish coordinate overlap, regulatory activity change, enhancer-target effect, and disease/gene association.
3. Density controls must report input variants, supported variants, raw overlaps, deduplicated edges, max/mean overlaps per mutation, and any score/association thresholds.
4. GNN leakage policy must keep overlap/context features out of target labels and leakage-sensitive train/test splits when downstream mutation associations are used as gates.
5. Endpoint anti-joins, duplicate-key checks, and edge/evidence support audits must pass before any canonical write.

## Status/docs updates made

- Added this decision doc: `docs/mutation_remaining_next_state_t_8de911c0.md`.
- Updated `docs/current_state_20260623.md`, `TODO.md`, `todo.d/04_relations.md`, `docs/relation_coverage_current.md`, and `docs/kg_schema_overview.md` to remove stale “maybe canonical” ambiguity for the two remaining relations.

## Residual risks

- The current workspace is a shared artifact workspace, not a TxGNN-scoped git checkout/PR. Treat these docs/artifacts as review-required shared-workspace changes.
- FUSE was not healthy in this run (`Device not configured`), so canonical existence was cross-checked with `gsutil ls`; a reviewer should rerun any full anti-joins with a healthy FUSE mount or a direct GCS/DuckDB path.
- The `mutation_in_gene` bounded candidate is not full scope; a full all-part build may change counts materially.
- The current `mutation_overlaps_enhancer` relation remains declared in schema; coordinate overlap alone remains context/support feature-only, while support-gated overlap is now an explicit staged edge-candidate lane requiring independent review before any canonical write.
