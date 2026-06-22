# TxGNN / Jouvence KG TODO

## Current baseline

Canonical KG root: `/mnt/gcs/jouvencekb/kg/v2`

- node files: `15 / 15`
- edge files: `36 / 67`
- nodes: `55,523,691`
- edges: `94,877,374`
- coverage report: `.omoc/reports/hermes-clean-schema-coverage-20260618.json`

No remaining `-> ...` user comments were found in `manage_db/kg_schema.py`; the cleanup decisions from the schema discussion are represented below as active tasks.

## User-requested next task set — 2026-06-20

### Block 1 — split source-native gene-level compendia and evidence

Execution plan and promotion criteria: `docs/block1_relation_source_split_plan.md`.

First local GCS-cache inspection is recorded in that plan; no FUSE mount was available, so files were copied via `gcloud storage cp` into `.omoc/gcs-cache/kg-v2/`.

- [x] Add active schema relations for the first split targets:
  - `tf_binds_enhancer`
  - `transcript_interacts_protein`
  - `transcript_interacts_gene`
- [ ] `gene_interacts_gene`: inspect evidence/source databases and split source-native subsets where justified:
  - keep broad gene/gene-product interaction assertions in `gene_interacts_gene` with detailed evidence;
  - create/populate `protein_interacts_protein` only for protein/isoform-native endpoints;
  - create/populate `tf_regulates_gene` for TF→gene regulatory assertions;
  - create/populate `tf_binds_enhancer` for TF/enhancer binding assertions;
  - create/populate `transcript_interacts_protein` for RNA/transcript–protein binding;
  - create/populate `transcript_interacts_gene` for transcript/RNA–gene regulatory assertions.
- [ ] `pathway_contains_gene`: inspect compendium/source datasets and split only source-native protein-level membership into `pathway_contains_protein`; preserve source database, membership type, evidence/predicate, score, release, and record IDs in evidence.
- [ ] `molecule_targets_gene`: inspect compendium/source datasets and split only source-native protein/isoform target assertions into `molecule_targets_protein`; preserve MoA/action type, target class, mechanism, source database, score, and record IDs in evidence.
- [ ] For every ingested relationship: if the source is a compendium, enumerate the subdatabases; load subdatabase-native detail separately when OpenTargets/TxData flattened it away; list as much row-level source detail as possible in `evidence/{relation}.parquet`.
- [ ] Do not subset source rows before ingestion except when the relation would be biologically meaningless or for the explicitly bounded mutation↔enhancer case; otherwise keep broad edges and preserve different sources/features in evidence.

### Later — new node and edge families

- [ ] Add node type: organelle / compartment, initially from HPA subcellular location.
- [ ] Add node type: protein complex; identify source(s).
- [ ] Add node type: miRNA; identify source(s).
- [ ] Add node type: lncRNA; identify source(s).
- [ ] Add `organelle_or_compartment -> cell_type` when a source supports the context.
- [ ] Add `organelle_or_compartment -> organelle_or_compartment` from HPA subcellular hierarchy: https://www.proteinatlas.org/humanproteome/subcellular
- [ ] Add `protein -> organelle_or_compartment` from HPA subcellular/organelle: https://www.proteinatlas.org/humanproteome/subcellular/organelle
- [ ] Add `protein -> ptm -> disease/phenotype` from neXtProt and UniProtKB.
- [ ] Add `lncRNA -> protein/disease/phenotype`.
- [ ] Add `miRNA -> protein/disease/phenotype`.
- [ ] Add `protein -> protein_complex`.
- [ ] Add `protein_complex -> protein_complex/disease/phenotype`.
- [ ] Add `gene_paralogs_gene`.

### Later — textual summaries/features

Staged feature-table pilot and source audit: `docs/textual_summary_features.md`.
Uploaded staging root: `gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_3834a45b/`.

- [x] Reject GeneCards scraping unless terms are explicitly acceptable; use source-audited alternatives instead.
- [x] Stage gene textual summaries from OpenTargets target node descriptions with upstream-source attribution caveat.
- [ ] Expand protein textual summaries from UniProt beyond the staged 100-accession pilot.
- [x] Stage disease textual summaries from OpenTargets/EFO/MONDO-derived node descriptions.
- [x] Stage tissue textual summaries from UBERON definitions.
- [x] Stage molecule textual summaries from ChEMBL/OpenTargets drug metadata; DrugBank text scraping remains rejected/deferred without separate license.
- [ ] Add Reactome pathway textual summaries when a Reactome description dump/API source is selected; GO pathway/process definitions are staged.

### Later — database gap analysis

Answer for each database: do we already have it, is it part of an ingested compendium, and does it contain useful information not present in the current ingestion/OpenTargets?

- [ ] CIViC
- [ ] Monarch
- [ ] ClinPGx
- [ ] OMIM
- [ ] HumanCyc
- [ ] BioGRID
- [ ] IID
- [ ] InnateDB
- [ ] IntAct
- [ ] MINT
- [ ] DGV and other structural-variation databases for mutation nodes/edges

## Immediate tasks

### 1. Full validation after cleanup ✅

- Completed with DuckDB on `/mnt/gcs/jouvencekb/kg/v2`.
- Report: `.omoc/reports/hermes-full-validate-clean-schema-20260618.txt`.
- Result: `36` edge files, `94,877,374` edges, `55,523,691` nodes, `total_dangling_edges=0`.

### 2. Evidence for `enhancer_regulates_gene` ✅

- Backfilled `/mnt/gcs/jouvencekb/kg/v2/evidence/enhancer_regulates_gene.parquet`.
- Rows: `48,810,390`; distinct supported edges: `48,808,144`.
- Source: OpenTargets ENCODE-rE2G raw `enhancer_to_gene` rows.
- Preserved biosample ID/name, study/file ID, DNase/Hi-C resource score JSON, distance-to-TSS, quality controls, PMID/source release.
- Build log: `.omoc/reports/hermes-build-enhancer-evidence-20260618.log`.
- Audit: `.omoc/reports/hermes-audit-enhancer-evidence-20260618.txt` → `edges_without_evidence=0`, `evidence_without_edge=0`.

### 3. OpenTargets molecular interaction evidence ✅

- Downloaded OpenTargets 26.03 `interaction` Parquet shards to `/mnt/gcs/jouvencekb/kg/scratch/opentargets-26.03/interaction`.
- Promoted OpenTargets-supported `gene_interacts_gene` edges after filtering both endpoints against `nodes/gene.parquet`.
- Updated `/mnt/gcs/jouvencekb/kg/v2/edges/gene_interacts_gene.parquet`: `7,424,037` deduplicated edges.
- Wrote `/mnt/gcs/jouvencekb/kg/v2/evidence/gene_interacts_gene.parquet`: `14,336,594` source evidence rows from IntAct/Reactome/SIGNOR/STRING.
- Build/audit log: `.omoc/reports/hermes-build-gene-interaction-ot-20260618.log`.
- Validation during build: `missing_x=0`, `missing_y=0`, `edges_without_evidence=0`, `evidence_without_edge=0` for OpenTargets-supported keys.

### 4. Direct HPA protein expression ✅ tissue-level / ⏳ cell-type-level

- Downloaded HPA 25.1 `proteinatlas.tsv.zip` to `/mnt/gcs/jouvencekb/kg/scratch/hpa-25.1/`.
- Built `/mnt/gcs/jouvencekb/kg/v2/edges/tissue_expresses_protein.parquet`: `137,351` tissue→protein edges.
- Built `/mnt/gcs/jouvencekb/kg/v2/evidence/tissue_expresses_protein.parquet`: `137,531` HPA evidence rows.
- Used UniProt→ENSP mapping from `nodes/protein.parquet`; no RNA/gene projection.
- Used exact tissue-name matching plus four explicit HPA aggregate aliases: heart muscle, skeletal muscle, salivary gland, skin.
- Build log: `.omoc/reports/hermes-build-hpa-protein-expression-20260618.log`.
- Validation: `.omoc/reports/hermes-full-validate-after-hpa-20260618.txt` → `37` edge files, `94,877,374` edges, `total_dangling_edges=0`.
- Remaining: decide whether HPA aggregate `Protein cell type specific Intensity` is sufficient for `cell_type_expresses_protein`, or whether we require a finer direct HPA cell-type/staining table.

### 5. Drug clinical/safety evidence

- Add positive indication/trial-stage evidence for `molecule_treats_disease`.
- Find a contraindication-specific source for `molecule_contraindicates_disease`; do not reuse positive indication rows as contraindication evidence.

### 6. Molecule pair evidence

- Backfill `molecule_synergizes_molecule` evidence with source descriptions, labels, and scores.
- Keep chemical hierarchy in `molecule_parent_of_molecule`.

### 7. Remaining source-backed relations

Only build these when a concrete source and endpoint policy are selected:

- `mutation_in_gene` — staged pilot exists at `docs/proposals/mutation_genomic_direct_edges_staged_pilot.md`; review bounding policy before canonical promotion.
- `mutation_affects_transcript` — staged pilot exists at `docs/proposals/mutation_genomic_direct_edges_staged_pilot.md`; review consequence/transcript filtering before canonical promotion.
- `mutation_overlaps_enhancer` — staged pilot exists at `docs/proposals/mutation_genomic_direct_edges_staged_pilot.md`; keep downstream-association gate before any canonical promotion.
- `enhancer_regulates_transcript`
- `cell_line_gene_essentiality`
- `cell_line_responds_to_molecule`
- `disease_manifests_in_tissue`
- `phenotype_observed_in_tissue`

## Promotion gates

Before any new canonical edge file is promoted:

1. Build in scratch/staging.
2. Validate endpoint anti-joins for x/y node IDs.
3. Write evidence rows when source provenance exists.
4. Audit evidence support with `manage_db.audit_edge_evidence`.
5. Update coverage report and docs.
6. Run targeted tests plus relation-specific validation.
