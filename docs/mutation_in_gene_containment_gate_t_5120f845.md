# REL-WAVE-A `mutation_in_gene` independent containment gate

Kanban task: `t_5120f845`
Date: 2026-06-23
Scope: staged smoke rebuild only; no canonical KG write.

## Decision

`mutation_in_gene` now requires independent physical containment before a staged edge is emitted.

Trusted source-native coordinate interval source:

- OpenTargets Platform 26.03 `target` dataset
- Field: `target.genomicLocation` (`chromosome`, `start`, `end`, `strand`)
- Join key: `target.id == transcriptConsequences[].targetId` (Ensembl gene id)
- Point test: OpenTargets `variant.chromosome`/`variant.position` must satisfy `chromosome == target.genomicLocation.chromosome` and `start <= position <= end`

The VEP `transcriptConsequences[].targetId` is still used to identify the gene candidate, but it is no longer sufficient for `mutation_in_gene`. Rows with missing target intervals, missing variant coordinates, or positions outside the target interval are rejected. Evidence rows carry a `containment_proof` object sourced from `OpenTargets/target.genomicLocation`.

This addresses the reviewer rejection that the previous artifact was only VEP gene-local/transcript-consequence context and did not independently prove physical gene containment.

## Code changes

- `manage_db/build_staged_mutation_genomic_edges.py`
  - Added `--target-file` / `--target-download-cache`.
  - Defaults to all official OpenTargets Platform 26.03 `target` Parquet parts.
  - Loads 78,691 target gene intervals from `target.genomicLocation` in the smoke run.
  - Gates `mutation_in_gene` on point-in-gene containment.
  - Adds manifest counters:
    - `gene_coordinate_containment_passes`
    - `gene_coordinate_containment_rejects`
    - `gene_interval_missing_or_unproven_rejects`
    - `gene_interval_rows`
  - Changes `mutation_in_gene` evidence predicate to `policy_filtered_variant_transcript_consequence_target_gene_with_target_genomic_location_containment` and source dataset to `variant+target`.
- `tests/test_build_staged_mutation_genomic_edges.py`
  - Adds a fixture where a VEP `targetId` row has an allowed SO class but variant position outside the independent gene interval.
  - Asserts the row is rejected from `mutation_in_gene` while contained rows are retained.
- `artifacts/reports/t_5120f845_mutation_in_gene_containment_audit.py`
  - Durable audit script for duplicate keys, leakage probes, and source-native containment proof validation.

## Staged artifacts

Stage root:

```text
artifacts/staged/t_5120f845/mutation-genomic-direct-contained-20260623-smoke
```

Reports:

```text
artifacts/reports/t_5120f845_build_output.json
artifacts/reports/t_5120f845_audit_edge_evidence.json
artifacts/reports/t_5120f845_mutation_in_gene_containment_audit.py
artifacts/reports/t_5120f845_mutation_in_gene_containment_audit.json
artifacts/reports/t_5120f845_mutation_in_gene_containment_audit.stdout.json
```

## Build command

```bash
STAGE=artifacts/staged/t_5120f845/mutation-genomic-direct-contained-20260623-smoke
uv run python -m manage_db.build_staged_mutation_genomic_edges \
  --variant-file "$(head -n 1 artifacts/reports/t_8eeb17bc_variant_urls.txt)" \
  --kg-cache-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --stage-root "$STAGE" \
  --max-variants 25000 \
  --skip-enhancer-overlap
```

`--skip-enhancer-overlap` was used intentionally because this tofix is scoped to the `mutation_in_gene` containment gate. The stage still writes empty `mutation_overlaps_enhancer` Parquets and validates them, but it is not a replacement for the prior enhancer-overlap smoke artifact.

## Build results

Input/rebuild scope:

| Metric | Count |
| --- | ---: |
| Input variants | 25,000 |
| Canonical mutation matches | 11,780 |
| Exploded transcript consequence rows | 762,741 |
| Excluded upstream/downstream/intergenic/regulatory rows | 751,072 |
| Rows after allowed consequence filter | 10,853 |
| Target gene intervals loaded | 78,691 |
| Gene containment passes | 10,852 |
| Gene coordinate containment rejects | 1 |
| Missing/unproven interval rejects | 0 |

Staged edge/evidence rows:

| Relation | Edges | Evidence |
| --- | ---: | ---: |
| `mutation_in_gene` | 10,852 | 10,852 |
| `mutation_affects_transcript` | 10,852 | 10,852 |
| `mutation_overlaps_enhancer` | 0 | 0 |

The previous VEP-only smoke had 11,669 `mutation_in_gene` rows. This stricter rebuild has 10,852 contained rows because the builder now rejects rows with unallowlisted SO combinations and rejects one otherwise-allowed row whose variant point is outside the independent gene interval.

## Validation and audits

Builder endpoint/evidence validation (`validation.json`): passed for all staged relations.

`manage_db.audit_edge_evidence`:

```bash
uv run python -m manage_db.audit_edge_evidence \
  artifacts/staged/t_5120f845/mutation-genomic-direct-contained-20260623-smoke \
  --relations mutation_in_gene mutation_affects_transcript mutation_overlaps_enhancer \
  --json --fail-on-missing > artifacts/reports/t_5120f845_audit_edge_evidence.json
```

Result: `ok: true`

| Relation | Edges without evidence | Evidence without edge |
| --- | ---: | ---: |
| `mutation_in_gene` | 0 | 0 |
| `mutation_affects_transcript` | 0 | 0 |
| `mutation_overlaps_enhancer` | 0 | 0 |

Independent containment/leakage audit:

```bash
uv run python artifacts/reports/t_5120f845_mutation_in_gene_containment_audit.py
```

Result: `passed: true`

Key checks:

- duplicate edge keys: 0 for all staged relations
- duplicate evidence keys: 0 for all staged relations
- leakage hits for `l2g`, `gwas`, `credible set`, `credible_set`, `association_score`, `study_locus`: none
- `mutation_in_gene` evidence rows checked: 10,852
- `containment_failures`: 0
- containment source counts: `OpenTargets/target.genomicLocation`: 10,852
- predicate count: `policy_filtered_variant_transcript_consequence_target_gene_with_target_genomic_location_containment`: 10,852

Targeted tests:

```bash
uv run python -m py_compile manage_db/build_staged_mutation_genomic_edges.py
uv run --group dev pytest tests/test_build_staged_mutation_genomic_edges.py tests/test_variant_enhancer_missing_edge_plan.py -q
# 6 passed in 1.10s
```

## Promotion stance

This task produces a corrected staged smoke candidate and report for `mutation_in_gene` containment semantics. It does not promote canonical KG files.

Canonical readiness still requires reviewer acceptance and, separately, a full all-part rebuild if REL-WAVE-A wants production/full scope. The current artifact is bounded to the first OpenTargets variant part with `--max-variants 25000`.
