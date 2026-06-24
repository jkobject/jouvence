# Mutation genomic direct staged tranche tofix

Kanban task: `t_590a4bb7`
Date: 2026-06-23
Local stage root: `artifacts/staged/t_590a4bb7`
Input tranche: same one-part/25k OpenTargets Platform 26.03 bounded input used by `t_79f8684d`
Canonical writes: none

## Fix applied

The direct consequence builder now treats `source_audit.json.allowed_consequence_ids` as a strict approval surface: every SO id carried by an accepted direct `mutation_in_gene` or `mutation_affects_transcript` evidence row must be allowlisted. Rows with a mix of an allowed parent term plus unreviewed child splice terms are rejected instead of accepted.

Patched code/test files:

- `manage_db/build_staged_mutation_genomic_edges.py`
- `tests/test_build_staged_mutation_genomic_edges.py`

Generated staged artifacts:

- `artifacts/staged/t_590a4bb7/manifest.json`
- `artifacts/staged/t_590a4bb7/source_audit.json`
- `artifacts/staged/t_590a4bb7/validation.json`
- `artifacts/staged/t_590a4bb7/qa_validation_counts_t_590a4bb7.json`
- staged edges/evidence/nodes under `artifacts/staged/t_590a4bb7/{edges,evidence,nodes}/`

## Updated staged counts

```json
{
  "input_variants": 25000,
  "canonical_mutation_matches": 11780,
  "exploded_transcript_consequence_rows": 762741,
  "rows_after_allowed_consequence_filter": 10853,
  "rows_after_canonical_transcript_filter": 10853,
  "excluded_upstream_downstream_intergenic_or_regulatory_rows": 751072,
  "rejected_non_allowlisted_consequence_rows": 751888,
  "edge_rows": {
    "mutation_in_gene": 10853,
    "mutation_affects_transcript": 10853,
    "mutation_overlaps_enhancer": 1670937
  },
  "evidence_rows": {
    "mutation_in_gene": 10853,
    "mutation_affects_transcript": 10853,
    "mutation_overlaps_enhancer": 1670937
  }
}
```

Compared with the reviewed staged tranche, direct gene/transcript rows dropped from 11,669 to 10,853. The 816 previously accepted rows containing non-allowlisted child splice SO IDs are now filtered out for both direct relations. The specific blocked child terms reported by review (`SO_0002169`, `SO_0002170`, `SO_0001787`) have zero occurrences in accepted direct evidence.

## QA summary

Machine-readable QA: `artifacts/staged/t_590a4bb7/qa_validation_counts_t_590a4bb7.json`

Key pass checks:

- `mutation_in_gene`: 10,853 edges / 10,853 evidence; no duplicate edge pairs; no edges without evidence; no evidence without edges; canonical mutation/gene endpoint anti-joins are zero; non-allowlisted SO rows are zero.
- `mutation_affects_transcript`: 10,853 edges / 10,853 evidence; no duplicate edge pairs; no edges without evidence; no evidence without edges; canonical mutation/transcript endpoint anti-joins are zero; non-allowlisted SO rows are zero; noncanonical transcript evidence rows are zero.
- `mutation_overlaps_enhancer`: unchanged 1,670,937 edges / 1,670,937 evidence; no duplicate edge pairs; no edge/evidence support gaps; all evidence rows have downstream gate true, non-empty support relations, and mutation position inside the recorded enhancer interval.

Validation file: `artifacts/staged/t_590a4bb7/validation.json` reports `passed: true`.

## Important limitations / review notes

- `mutation_in_gene` is still staged VEP transcript/gene-local context. This tofix did not select or add an independent Ensembl/GTF gene-coordinate containment table. Therefore it must not be canonically promoted as strict physical gene containment without a later coordinate-containment review.
- `mutation_overlaps_enhancer` remains the same one-part/25k bounded staged tranche. This task did not rebuild full all-part scope and does not authorize partial canonical promotion.
- A fresh full enhancer endpoint anti-join against all 48,808,144 canonical enhancer nodes timed out in this run. Because the enhancer tranche is unchanged by the SO allowlist repair, `qa_validation_counts_t_590a4bb7.json` carries forward the accepted `t_e10b11a2` enhancer endpoint scan result (115,543/115,543 unique enhancer endpoints found) and explicitly labels that basis.

## Commands run

```bash
uv run python -m py_compile manage_db/build_staged_mutation_genomic_edges.py
uv run --group dev pytest tests/test_build_staged_mutation_genomic_edges.py -q
# result: 3 passed in 0.92s

uv run python -m manage_db.build_staged_mutation_genomic_edges \
  --variant-file https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/variant/part-00000-489af5f8-1f32-49c6-88b5-2f5c71927329-c000.snappy.parquet \
  --kg-cache-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --stage-root artifacts/staged/t_590a4bb7 \
  --max-variants 25000 \
  --download-cache .omoc/source-cache/opentargets-26.03/variant
# artifact writes completed; command timed out before validation.json, so validation was run with targeted scripts below.

uv run python artifacts/staged/t_590a4bb7/write_final_qa.py
# result: passed true; wrote validation.json and qa_validation_counts_t_590a4bb7.json
```

Canonical absence check after the run:

```text
absent edges/mutation_in_gene.parquet
absent evidence/mutation_in_gene.parquet
absent edges/mutation_affects_transcript.parquet
absent evidence/mutation_affects_transcript.parquet
absent edges/mutation_overlaps_enhancer.parquet
absent evidence/mutation_overlaps_enhancer.parquet
```
