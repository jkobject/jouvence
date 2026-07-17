# Mutation genomic direct staged validation — t_e10b11a2

Verdict: FAIL / tofix for `mutation_in_gene` and `mutation_affects_transcript`; PASS for endpoint/evidence wiring and `mutation_overlaps_enhancer` downstream gate.

This validates the staged MUT-BUILD tranche only. It does not approve canonical promotion.

## Inputs

- Local staging root: `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d`
- Remote staging prefix: `gs://jouvencekb/kg/v2/staging/source-native-expansion/mutation-genomic-direct-bounded-20260623-t_79f8684d/`
- Canonical KG root used for anti-joins: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`
- Build manifest: `artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d/manifest.json`
- Source audit/policy: `artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d/source_audit.json`, `docs/mutation_genomic_relations_promotion_policy.md`
- Machine-readable QA counts: `artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d/qa_validation_counts_t_e10b11a2.json`

Remote prefix was listed with `gsutil ls -r` and contains manifest/report/source_audit/validation plus staged edges/evidence/nodes Parquet files.

## Counts and wiring

| Relation | Edge rows | Evidence rows | Unique x | Unique y | Missing x canonical or staged | Missing y canonical | Edges without evidence | Evidence without edge | Duplicate edge pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `mutation_in_gene` | 11669 | 11669 | 11460 | 170 | 0 | 0 | 0 | 0 | 0 |
| `mutation_affects_transcript` | 11669 | 11669 | 11460 | 170 | 0 | 0 | 0 | 0 | 0 |
| `mutation_overlaps_enhancer` | 1670937 | 1670937 | 5851 | 115543 | 0 | 0 | 0 | 0 | 0 |

All edge/evidence row counts match the manifest deltas (`manifest_edge_delta=0`, `manifest_evidence_delta=0`) for all three relations. Core type/relation/null/edge_key checks were zero-failure.

Enhancer canonical endpoint anti-join was run as an exhaustive PyArrow row-group scan over `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/enhancer.parquet` (48,808,144 rows / 118 row groups): 115,543 needed enhancer IDs, 115,543 found, 0 missing.

## Policy/semantic checks

### PASS: no L2G/GWAS leakage detected

For `mutation_in_gene` and `mutation_affects_transcript`, scanned `source_record_id`, `predicate`, `source_dataset`, and `text_span` for L2G/GWAS/credible-set/study-locus/p-value/beta/eaf tokens: 0 rows.

Predicates/source datasets are source-native VEP/OpenTargets variant rows:

- `mutation_in_gene`: `policy_filtered_variant_transcript_consequence_target_gene`, source_dataset `variant`.
- `mutation_affects_transcript`: `policy_filtered_canonical_variant_transcript_consequence`, source_dataset `variant`.
- `mutation_overlaps_enhancer`: `bounded_variant_overlaps_enhancer_interval`, source_dataset `variant+enhancer_interval`.

### FAIL: documented consequence allowlist mismatch

`source_audit.json` documents an exact `allowed_consequence_ids` list. My independent DuckDB check found accepted evidence rows with SO IDs not in that list:

| Relation | SO ID | Label | Rows | Unique mutations | Unique y endpoints |
| --- | --- | --- | ---: | ---: | ---: |
| `mutation_in_gene` | `SO_0002169` | splice_polypyrimidine_tract_variant | 651 | 651 | 58 |
| `mutation_in_gene` | `SO_0002170` | splice_donor_region_variant | 108 | 108 | 28 |
| `mutation_in_gene` | `SO_0001787` | splice_donor_5th_base_variant | 57 | 57 | 25 |
| `mutation_affects_transcript` | `SO_0002169` | splice_polypyrimidine_tract_variant | 651 | 651 | 58 |
| `mutation_affects_transcript` | `SO_0002170` | splice_donor_region_variant | 108 | 108 | 28 |
| `mutation_affects_transcript` | `SO_0001787` | splice_donor_5th_base_variant | 57 | 57 | 25 |

Total non-allowlisted SO occurrences: 816 in `mutation_in_gene` evidence and 816 in `mutation_affects_transcript` evidence. Example evidence rows include consequence arrays such as `["SO_0001630", "SO_0002169", "SO_0001627"]`, so rows can include both allowed and non-documented child splice terms.

These terms are splice-region/splicing child terms, not L2G/GWAS leakage. The tofix issue is that the build/report says it applied the documented allowlist while accepted rows contain additional SO terms not listed in `source_audit.json`. The builder should either:

1. explicitly add these child splice SO IDs to the approved allowlist and source audit/report, if policy accepts descendants of splice-region/splicing terms; or
2. filter out rows containing non-allowlisted consequence IDs and update counts/rejected rows.

Until that is resolved, the staged tranche should not be promoted.

### PASS: enhancer downstream association gate

- unique overlap mutations: 5851
- supported by current downstream union: 5851
- missing downstream support: 0
- evidence rows with missing/false `downstream_association_gate`: 0
- evidence rows with empty `support_relations`: 0
- evidence coordinate outside text interval: 0

Per current support relation, used mutations supported:

```json
{
  "mutation_associated_disease": 5814,
  "mutation_associated_phenotype": 56,
  "mutation_affects_molecule_response": 0,
  "mutation_associated_gene": 188,
  "mutation_causes_protein_change": 1300
}
```

## Density / rejected rows documented by build manifest

- input_variants: 25000
- canonical_mutation_matches: 11780
- mutation_nodes: 11780
- exploded_transcript_consequence_rows: 762741
- rows_after_allowed_consequence_filter: 11669
- rows_after_canonical_transcript_filter: 11669
- enhancer_slice_rows: 115543
- excluded_upstream_downstream_intergenic_or_regulatory_rows: 751072
- gene_endpoint_rejects: 0
- transcript_endpoint_rejects: 0

| Relation | Unique x | Unique y | Avg edges/x | Max edges/x |
| --- | ---: | ---: | ---: | ---: |
| `mutation_in_gene` | 11460 | 170 | 1.018 | 4 |
| `mutation_affects_transcript` | 11460 | 170 | 1.018 | 4 |
| `mutation_overlaps_enhancer` | 5851 | 115543 | 285.581 | 4733 |

## Reproduction evidence commands

- `gsutil ls -r gs://jouvencekb/kg/v2/staging/source-native-expansion/mutation-genomic-direct-bounded-20260623-t_79f8684d/`
- `uv run python /tmp/validate_mutation_core.py`
- exhaustive enhancer endpoint scan wrote `qa_enhancer_endpoint_scan_t_e10b11a2.json`
- downstream gate check wrote `qa_enhancer_downstream_gate_t_e10b11a2.json`

## Suggested owner

Assign to dev/builder: fix or document the SO child-term allowlist behavior, regenerate staged artifacts/counts, then rerun tester validation. Reviewer/CTO may need to decide whether child splice descendants are policy-accepted.
