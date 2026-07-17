# Full support-gated `mutation_overlaps_enhancer` staged candidate

Kanban task: `t_73c67c1b`  
Status: `staged-only` / `review-required`  
Canonical writes: none. Do not treat this as canonical promoted or production/full done.

## Bottom line

A full intended support-gated `mutation_overlaps_enhancer` candidate was built under:

`artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/`

This candidate preserves the policy that coordinate-only mutation→enhancer overlap remains context/support feature-only. Rows are staged as evidence-backed edge candidates only when the mutation has non-protein-change external support from current canonical KG mutation support relations. `mutation_causes_protein_change` rows are retained as context in support summaries but are not sufficient as the sole support gate.

## Inputs

- Raw prior overlap stage: `artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d/`
- Canonical KG root for live endpoint/support audit: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`
- Support relations scanned:
  - `mutation_associated_gene`
  - `mutation_associated_disease`
  - `mutation_associated_phenotype`
  - `mutation_affects_molecule_response`
  - `mutation_causes_protein_change` (context-only if sole support)

No `.omoc` path was used. No `gs://jouvencekb/kg/v2` or canonical FUSE output path was written.

## Outputs

- Edges: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/edges/mutation_overlaps_enhancer.parquet`
- Evidence: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/evidence/mutation_overlaps_enhancer.parquet`
- Support rows: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/support/mutation_support_rows_for_overlap_mutations.parquet`
- Support summary, all supported overlap mutations: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/support/mutation_support_summary_full.parquet`
- Support summary, non-context-gated mutations: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/support/mutation_support_summary_non_context_gated.parquet`
- Examples by support class: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/examples/support_gated_examples_by_class.jsonl`
- Validation summary: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/validation/validation_summary.json`
- Stage manifest: `artifacts/staged/t_73c67c1b/mutation-overlaps-enhancer-support-gated-full/manifest.json`
- JSON report: `artifacts/reports/t_73c67c1b_support_gated_mutation_enhancer_full_report.json`
- Build scripts:
  - `artifacts/reports/t_73c67c1b_build_support_gated_mutation_enhancer_full.py`
  - `artifacts/reports/t_73c67c1b_finalize_support_gated_mutation_enhancer_full.py`

The stage manifest lists 8 files and reports `manifest_clean: true`.

## Counts

| Metric | Count |
| --- | ---: |
| Input raw overlap rows | 1,670,937 |
| Input raw overlap evidence rows | 1,670,937 |
| Input raw overlap mutations | 5,851 |
| Input raw overlap enhancers | 115,543 |
| Support rows intersecting overlap mutations | 10,501 |
| Mutations with any support | 5,851 |
| Non-context-gated mutations emitted | 5,814 |
| Protein/context-only supported mutations excluded | 37 |
| Rows supported only by protein/context evidence in raw overlap | 6,659 |
| Rows supported only by protein/context evidence in output | 0 |
| Full staged edge rows | 1,664,278 |
| Full staged evidence rows | 1,664,278 |
| Unique staged enhancer endpoints | 114,191 |

## Support distribution

All support rows intersecting overlap mutations:

| Support class | Rows |
| --- | ---: |
| ClinVar/EVA disease support | 7,612 |
| protein-change context only | 1,300 |
| GWAS credible-set disease support | 844 |
| GWAS/L2G gene support | 623 |
| ClinVar/EVA phenotype support | 70 |
| UniProt variant disease support | 50 |
| ClinVar/EVA somatic disease support | 2 |

Non-context support classes used as gates:

| Support class | Rows |
| --- | ---: |
| ClinVar/EVA disease support | 7,612 |
| GWAS credible-set disease support | 844 |
| GWAS/L2G gene support | 623 |
| ClinVar/EVA phenotype support | 70 |
| UniProt variant disease support | 50 |
| ClinVar/EVA somatic disease support | 2 |

No canonical eQTL, MPRA, caQTL/ATAC-QTL, or allele-specific enhancer-activity support relation was found in current canonical KG support relations during this build. Those remain preferred future support classes before any canonical promotion decision.

## Fresh validation

Validation command:

```bash
uv run python -m py_compile artifacts/reports/t_73c67c1b_build_support_gated_mutation_enhancer_full.py artifacts/reports/t_73c67c1b_finalize_support_gated_mutation_enhancer_full.py
uv run python artifacts/reports/t_73c67c1b_build_support_gated_mutation_enhancer_full.py
uv run python artifacts/reports/t_73c67c1b_finalize_support_gated_mutation_enhancer_full.py
```

The first foreground full-build invocation timed out after writing edge/evidence artifacts while validating; the finalize script resumed from the existing task-scoped outputs and completed the live validation/report/manifest without rebuilding or writing canonical paths.

Validation results from `validation/validation_summary.json`:

| Check | Result |
| --- | ---: |
| Duplicate edge keys | 0 |
| Duplicate evidence keys | 0 |
| Edges without evidence | 0 |
| Evidence without edges | 0 |
| Live mutation endpoint anti-join missing count | 0 |
| Live enhancer endpoint anti-join missing count | 0 |
| Staged unique mutation endpoints checked | 5,814 |
| Staged unique enhancer endpoints checked | 114,191 |
| Matched mutation endpoints | 5,814 |
| Matched enhancer endpoints | 114,191 |
| Overall validation | passed |

Live endpoint anti-joins used canonical node files:

- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/mutation.parquet`
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/enhancer.parquet`

## Canonical-prefix guardrail

The JSON report records:

```json
{
  "canonical_prefix": "/Users/jkobject/mnt/gcs/jouvencekb-kg/v2",
  "canonical_write_attempted": false,
  "output_paths_under_canonical_prefix": []
}
```

This card intentionally stops at `review-required`. Any canonical write would need an independent tester/reviewer gate and a separate explicit promotion task.

## Residual risks

- The full candidate is still dense: 1,664,278 edges from 5,814 non-context-supported mutations, mean 286.25 enhancer overlaps per emitted mutation.
- Most available support is disease/gene/phenotype association support, not direct enhancer-activity perturbation evidence. Treat it as source-backed support context with leakage guardrails, not proof that the mutation perturbs enhancer activity.
- Stronger eQTL/caQTL/MPRA/allele-specific regulatory evidence was not available as current canonical KG support input for this build.
- The workspace remains a shared artifact directory, not a clean PR-ready TxGNN worktree.
