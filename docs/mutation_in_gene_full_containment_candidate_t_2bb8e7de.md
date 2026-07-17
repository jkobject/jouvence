# Full all-part `mutation_in_gene` containment-gated staged candidate

Kanban task: `t_2bb8e7de`  
Date: 2026-06-24  
Status label: `full staged candidate` / `review-required`; not canonical and not promotion-ready until independent review accepts this artifact and a separate promotion card is created.

## Artifact roots

- Stage root: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624`
- Edges: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/edges/mutation_in_gene.parquet`
- Evidence: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/evidence/mutation_in_gene.parquet`
- Containment proof: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/proof/mutation_in_gene_containment_proof.parquet`
- Mutation node sidecar: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/nodes/mutation.parquet`
- Manifest: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/manifest.json`
- Validation: `artifacts/staged/t_2bb8e7de/mutation-in-gene-full-contained-20260624/validation.json`
- Report copy: `artifacts/reports/t_2bb8e7de_mutation_in_gene_full_candidate_report.json`
- Builder: `artifacts/reports/t_2bb8e7de_build_full_mutation_in_gene.py`
- Progress log: `artifacts/reports/t_2bb8e7de_mutation_in_gene_full_progress.jsonl`

No canonical KG write was performed.

## Source and policy

- OpenTargets Platform release: 26.03.
- Variant scope: all 25 OpenTargets `variant` parquet parts.
- Trusted gene interval source: all 10 OpenTargets `target` parquet parts, field `target.genomicLocation`.
- Endpoint gate: `x_id` must exist in canonical KG `nodes/mutation.parquet`; `y_id` must exist in canonical KG `nodes/gene.parquet`.
- Containment gate: mutation chromosome/position must satisfy `chromosome == target.genomicLocation.chromosome` and `gene_start <= position <= gene_end`.
- Broad VEP `targetId` alone is not sufficient; a point-in-gene containment proof row is required for every staged edge.
- Evidence predicate: `policy_filtered_variant_transcript_consequence_target_gene_with_target_genomic_location_containment`.
- Evidence source dataset: `variant+target`; containment proof source dataset: `OpenTargets/target.genomicLocation`.
- Association/L2G/GWAS sources were not used.

## Counts

| Metric | Count |
| --- | ---: |
| OpenTargets variant parts processed | 25 |
| OpenTargets target parts processed | 10 |
| Input variants | 7,432,549 |
| Canonical mutation matches | 2,589,092 |
| Exploded transcript consequence rows | 104,873,079 |
| Rows after allowed consequence filter | 2,599,922 |
| Gene coordinate containment passes before dedupe | 2,599,525 |
| Gene coordinate containment rejects | 397 |
| Gene interval missing/unproven rejects | 0 |
| Gene endpoint rejects | 0 |
| Merged `mutation_in_gene` edge rows | 2,599,525 |
| Merged evidence rows | 2,599,525 |
| Merged containment proof rows | 2,599,525 |
| Merged mutation node sidecar rows | 2,589,092 |

## Validation results

All validation gates in `validation.json` passed:

| Gate | Count |
| --- | ---: |
| Duplicate edge keys | 0 |
| Duplicate evidence keys | 0 |
| Duplicate proof keys | 0 |
| Edges without evidence | 0 |
| Evidence without edge | 0 |
| Edges without containment proof | 0 |
| Proof without edge | 0 |
| Missing mutation x endpoints | 0 |
| Missing gene y endpoints | 0 |
| Containment failures | 0 |
| Disallowed SO evidence rows | 0 |
| L2G/GWAS/credible-set/study-locus leakage rows | 0 |

Distribution checks:

- Predicate counts: `policy_filtered_variant_transcript_consequence_target_gene_with_target_genomic_location_containment`: 2,599,525.
- Evidence source dataset counts: `variant+target`: 2,599,525.
- Proof source counts: `OpenTargets/target.genomicLocation`: 2,599,525.

## Comparison to bounded candidate

Previous bounded candidate root: `artifacts/staged/t_5120f845/mutation-genomic-direct-contained-20260623-smoke`.

| Metric | Bounded candidate | Full candidate |
| --- | ---: | ---: |
| Input variants | 25,000 | 7,432,549 |
| `mutation_in_gene` edges | 10,852 | 2,599,525 |
| Containment passes | 10,852 | 2,599,525 |

The full candidate has about 239.54x as many edges as the bounded first-part/25k smoke. This material increase is expected because the full run processes all 25 OpenTargets variant parts and all canonical mutation matches under the same `target.genomicLocation` containment gate. The semantic gate is the same; the scope is no longer bounded to the first-part smoke.

## Recommendation

Treat `mutation_in_gene` as a `full staged candidate` and send it to independent review. The artifact is mechanically coherent under the accepted containment policy and passes endpoint/evidence/proof/leakage validation, but this card should not canonical-write it. If the reviewer accepts the full counts, density, containment proof, and leakage policy, create a separate relation-specific promotion card for canonical write/review.

Residual risks:

- The staged candidate is dense at 2.6M edges; reviewer should decide whether this density is acceptable as canonical graph structure versus feature/context sidecar.
- The builder/report live in the shared artifact workspace, not an independent TxGNN PR-ready checkout.
- Validation used cached canonical node parquet files under `artifacts/cache/t_2bb8e7de/kg-v2`; a promotion card should rerun final endpoint anti-joins against the live canonical GCS/FUSE root before writing canonical KG.
