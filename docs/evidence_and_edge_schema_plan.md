# Evidence and edge schema plan

This document defines the active edge/evidence policy after the 2026-06-18 schema cleanup.

## Current canonical coverage

Canonical KG root: `/mnt/gcs/jouvencekb/kg/v2`

- node files: `15 / 15`
- edge files: `36 / 67`
- nodes: `55,523,691`
- edges: `94,877,374`
- latest coverage report: `.omoc/reports/schema-direction-update-coverage-20260619.json`
- Block 1 validation report: `docs/block1_validation_report.md`; D1 validated `.omoc/gcs-cache/kg-v2` for Block 1 relation/evidence integrity, not whole-KG coverage.

## Edge/evidence separation

Edges are deduplicated graph assertions:

```text
x_id, x_type, y_id, y_type, relation, display_relation, source, credibility, ...
```

Evidence rows explain why an edge exists:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
evidence_type, source, source_dataset, source_record_id,
paper_id, dataset_id, study_id, evidence_score,
effect_size, p_value, direction, predicate,
text_span, section, extraction_method, license, release, created_at
```

One edge may have many evidence rows. Source-specific predicates and scores belong in evidence, not in relation-name proliferation.

## Cleaned active relation policy

- Gene-level drug targets use `molecule_targets_gene`.
- Protein-level drug targets use `molecule_targets_protein` only when the source directly identifies a protein/isoform endpoint.
- Gene/gene-product interaction rows use `gene_interacts_gene` with detailed source evidence.
- Direct protein/isoform interactions use `protein_interacts_protein`.
- Gene pathway membership uses `pathway_contains_gene`.
- Protein-native pathway/complex membership uses `pathway_contains_protein`.
- Disease→gene associations use `disease_associated_gene`.
- Disease→protein associations use `disease_associated_protein` only for protein-native evidence.
- Drug-combination effect rows use `molecule_synergizes_molecule`.
- Chemical hierarchy rows use `molecule_parent_of_molecule`.
- Entity→phenotype direction is canonical: `gene_associated_phenotype`, `molecule_associated_phenotype`.

## Current evidence files

- `evidence/cell_line_from_organism.parquet`
- `evidence/disease_associated_gene.parquet`
- `evidence/disease_involves_pathway.parquet`
- `evidence/enhancer_regulates_gene.parquet`
- `evidence/gene_interacts_gene.parquet` — OpenTargets/interaction evidence subset; accepted TxGNN legacy broad edges remain without fabricated evidence.
- `evidence/gene_ortholog_gene.parquet`
- `evidence/molecule_targets_gene.parquet`
- `evidence/mutation_affects_molecule_response.parquet`
- `evidence/mutation_associated_disease.parquet`
- `evidence/mutation_associated_gene.parquet`
- `evidence/mutation_associated_phenotype.parquet`
- `evidence/mutation_causes_protein_change.parquet`
- `evidence/pathway_contains_gene.parquet`
- `evidence/tissue_expresses_protein.parquet`

Block 1 complete-evidence gate is intentionally scoped to `pathway_contains_gene`
and `molecule_targets_gene`: both are `edges_without_evidence=0` and
`evidence_without_edge=0` in
`.omoc/reports/block1-validation-corrected-evidence-audit-20260622-tester-rerun.json`.
The transparency audit that includes `gene_interacts_gene` is expected to fail
only on `642,150` accepted TxGNN legacy broad edges without evidence; do not
invent support rows or split those gene endpoints into protein/TF/transcript
relations.

## Priority evidence backfills

1. `enhancer_regulates_gene`: preserve ENCODE-rE2G biosample, study/file ID, DNase score, Hi-C/contact score, distance-to-TSS, model score, and QC flags.
2. `gene_interacts_gene`: OpenTargets interaction / interaction-evidence is ingested for the OpenTargets-supported subset; keep the TxGNN legacy broad subset as an explicit policy exception unless a source-native replacement is approved.
3. `molecule_synergizes_molecule`: recover DrugBank/source interaction descriptions and distinguish synergy/effect from chemical hierarchy.
4. `molecule_treats_disease` / `molecule_contraindicates_disease`: add clinical indication/contraindication evidence with explicit polarity.
5. Direct protein-expression tranches: ingest HPA protein-level data directly for `tissue_expresses_protein` / `cell_type_expresses_protein`; do not project RNA expression.

## Validation gates

Before promotion:

1. Build in a local/scratch KG root.
2. Validate endpoint anti-joins for both node types.
3. Write evidence rows for every promoted sourced edge when source provenance exists.
4. Audit edge/evidence support with `manage_db.audit_edge_evidence`.
5. Update `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, and the coverage report.
