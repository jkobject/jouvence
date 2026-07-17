# Mutation genomic direct bounded staging report

Kanban task: `t_79f8684d`
Date: 2026-06-23
Local stage root: `artifacts/staged/mutation_genomic_direct_bounded_20260623_t_79f8684d`
Remote stage root: `gs://jouvencekb/kg/v2/staging/source-native-expansion/mutation-genomic-direct-bounded-20260623-t_79f8684d/`
Policy source: `docs/mutation_genomic_relations_promotion_policy.md` (`t_60b3e504`)

## Decision applied

The prior pilot was not promoted as-is. This staging run used a policy-bounded rebuild from OpenTargets Platform 26.03 variant rows with:

- allowed transcript/gene-local Sequence Ontology classes only;
- upstream/downstream/intergenic/regulatory-neighborhood SO classes excluded;
- canonical mutation/gene/transcript endpoint gates against `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`;
- `mutation_affects_transcript` restricted to `isEnsemblCanonical == true` consequence rows;
- `mutation_overlaps_enhancer` restricted to mutations with downstream support in `mutation_associated_disease`, `mutation_associated_phenotype`, `mutation_affects_molecule_response`, `mutation_associated_gene`, or `mutation_causes_protein_change`.

This is staged-only; no canonical KG files were written.

## Build totals

```json
{
  "canonical_mutation_matches": 11780,
  "edge_rows": {
    "mutation_affects_transcript": 11669,
    "mutation_in_gene": 11669,
    "mutation_overlaps_enhancer": 1670937
  },
  "enhancer_slice_rows": 115543,
  "evidence_rows": {
    "mutation_affects_transcript": 11669,
    "mutation_in_gene": 11669,
    "mutation_overlaps_enhancer": 1670937
  },
  "excluded_upstream_downstream_intergenic_or_regulatory_rows": 751072,
  "exploded_transcript_consequence_rows": 762741,
  "gene_endpoint_rejects": 0,
  "input_variants": 25000,
  "mutation_nodes": 11780,
  "rows_after_allowed_consequence_filter": 11669,
  "rows_after_canonical_transcript_filter": 11669,
  "transcript_endpoint_rejects": 0
}
```

## Validation

```json
{
  "passed": true,
  "relations": {
    "mutation_affects_transcript": {
      "edges": 11669,
      "edges_without_evidence": 0,
      "evidence": 11669,
      "evidence_without_edge": 0,
      "missing_x_count": 0,
      "missing_x_examples": [],
      "missing_y_count": 0,
      "missing_y_examples": [],
      "passed": true
    },
    "mutation_in_gene": {
      "edges": 11669,
      "edges_without_evidence": 0,
      "evidence": 11669,
      "evidence_without_edge": 0,
      "missing_x_count": 0,
      "missing_x_examples": [],
      "missing_y_count": 0,
      "missing_y_examples": [],
      "passed": true
    },
    "mutation_overlaps_enhancer": {
      "edges": 1670937,
      "edges_without_evidence": 0,
      "evidence": 1670937,
      "evidence_without_edge": 0,
      "missing_x_count": 0,
      "missing_x_examples": [],
      "missing_y_count": 0,
      "missing_y_examples": [],
      "passed": true
    }
  }
}
```

## Notes / residual risks

- This run used the first 25,000 OpenTargets variant rows from part-00000 as a bounded staged rebuild/artifact validation tranche, not a canonical full promotion.
- `mutation_in_gene` remains staged pending an independent trusted gene-coordinate containment source, per policy.
- Full all-part rebuild is now implemented by passing all 25 OpenTargets variant part URLs to `manage_db.build_staged_mutation_genomic_edges`; validate uses DuckDB anti-joins to avoid materializing 48.8M enhancer IDs in Python.
