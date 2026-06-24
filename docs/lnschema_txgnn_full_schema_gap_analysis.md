# lnschema_txgnn full schema gap analysis

Kanban task: `t_3d4fa114`

Status: design/audit done. This document does not implement migrations or sync code.

Sources audited:

- `manage_db/lnschema_txgnn/models.py`
- `manage_db/kg_schema.py`
- canonical KG FUSE mirror of `gs://jouvencekb/kg/v2`: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`
- `docs/relation_coverage_current.md`
- `docs/kg_schema_overview.md`
- generated metadata snapshot: `artifacts/reports/t_3d4fa114_lnschema_canonical_metadata.json`

## Executive summary

`lnschema_txgnn` currently covers only exact-ID node registries. It has no first-class edge, evidence, feature, embedding, or query-helper model. As a result, Lamin users can register nodes but cannot answer KG questions such as “all diseases associated with a gene” without reading Parquet or writing raw SQL against non-schema tables.

Current canonical KG scale verified from Parquet metadata:

- node tables: `15` files / `55,523,691` rows
- active schema relations: `67`
- canonical edge tables: `37` files / `94,880,924` rows
- canonical evidence tables: `15` files
- feature tables: `12` files

Primary recommendation: add a generic, typed KG edge registry plus a generic edge evidence registry and optional feature registry in `lnschema_txgnn`, then provide ergonomic query helpers in Python. Do not create 67 separate Django models in the first migration. Preserve canonical KG IDs as strings and use indexed `x_id`, `y_id`, `x_type`, `y_type`, `relation` fields for all graph assertions.

## Required product behavior

A Lamin/Jouvence user should be able to:

```python
import lnschema_txgnn as txs

# exact canonical-ID query
txs.diseases_for_gene(gene_id="ENSG00000139618")

# convenience resolver, still preserving exact canonical KG IDs internally
txs.diseases_for_gene_name("BRCA2")

# lower-level relation query
txs.edges(source_id="ENSG00000139618", relation="disease_associated_gene")

txs.evidence_for_edge(
    x_id="ENSG00000139618",
    y_id="EFO:0000305",
    relation="disease_associated_gene",
)
```

This requires queryable edge/evidence rows in LaminDB or a documented helper that reads the canonical Parquet snapshot through DuckDB/Arrow. A pure node-registry schema is insufficient.

## Node model audit

`manage_db/kg_schema.py` declares 15 node types. Canonical GCS has all 15 node parquet files. `lnschema_txgnn.models.py` has concrete custom models for 12/15 node types; `phenotype`, `cell_line`, and `organism` are still represented only by xref mixins / expected bionty coverage, not by exact-ID custom registries. Because this project explicitly wants exact canonical KG IDs and not forced public equivalence, those three need exact-ID models too.

| Node type | Canonical rows | lnschema model | Model status | Canonical ontology | Expected canonical columns | Missing in canonical file | Current model fields |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| `gene` | 267830 | `Gene` | present | Ensembl | `id, ncbi_gene_id, hgnc_id, uniprot_id, gene_name` | none | `uid, ensembl_gene_id, symbol, name, ncbi_gene_id, hgnc_id, uniprot_id` |
| `transcript` | 507365 | `Transcript` | present | Ensembl | `id, ensembl_gene_id, protein_id, refseq_mrna, ccds_id` | none | `uid, ensembl_transcript_id, refseq_mrna, ccds_id, ensembl_gene_id, biotype, is_canonical` |
| `protein` | 233995 | `Protein` | present | Ensembl Protein | `id, ensembl_gene_id, uniprot_id, refseq_protein, pdb_ids` | none | `uid, ensembl_protein_id, ensembl_gene_id, uniprot_id, refseq_protein, pdb_ids` |
| `disease` | 41859 | `Disease` | present | EFO | `id, mondo_id, omim_id, doid_id, icd10_code, mesh_id, hp_id` | none | `uid, ontology_id, source_ontology, name, mondo_id, omim_id, doid_id, icd10_code, mesh_id, hp_id` |
| `cell_type` | 3513 | `CellType` | present | CL | `id, uberon_id, mesh_id` | none | `uid, ontology_id, name` |
| `tissue` | 16061 | `Tissue` | present | UBERON | `id, bto_id, mesh_id, fma_id` | none | `uid, ontology_id, name` |
| `molecule` | 31007 | `Molecule` | present | ChEMBL | `id, drugbank_id, pubchem_cid, cas_rn, inchikey, smiles` | none | `uid, chembl_id, ontology_id, name, inchikey` |
| `phenotype` | 16449 | `—` | missing | HP | `id, mondo_id, efo_id, mp_id, mesh_id` | none | `—` |
| `pathway` | 48575 | `Pathway` | present | Reactome | `id, go_id, kegg_id` | none | `uid, ontology_id, name` |
| `mutation` | 2589509 | `Mutation` | present | dbSNP | `id, hgvs, clinvar_id, gnomad_id` | none | `uid, rsid, hgvs, clinvar_id, gnomad_id, chromosome, position, ref_allele, alt_allele, consequence` |
| `organism` | 1 | `—` | missing | NCBI Taxonomy | `id, gbif_id` | none | `—` |
| `cell_line` | 1183 | `—` | missing | Cellosaurus | `id, ccle_name, cosmic_id, efo_id` | none | `—` |
| `paper` | 2958199 | `Paper` | present | PubMed | `id, doi, pmc_id, arxiv_id` | none | `uid, pmid, doi, pmc_id, arxiv_id, title, year, journal, abstract` |
| `dataset` | 1 | `Dataset` | present | DOI / UUID | `id` | none | `uid, name, doi, description, version, source_url` |
| `enhancer` | 48808144 | `Enhancer` | present | ENCODE | `id, ensembl_regulatory_id, encode_experiment_id` | ensembl_regulatory_id, encode_experiment_id | `uid, encode_id, ensembl_regulatory_id, encode_experiment_id, chromosome, start_pos, end_pos` |

### Node field gaps and misalignments

- `Phenotype`, `CellLine`, and `Organism` concrete exact-ID models are missing. Add them because exact KG parity should not depend on bionty/pertdb equivalence behavior.
- `Gene` model uses `ensembl_gene_id`, `symbol`, `name`; canonical node file uses `id`, `gene_name`, `name`, plus broader legacy/xref columns. The sync layer must map `id -> ensembl_gene_id` and `gene_name -> symbol` without dropping the exact `id`.
- `Molecule` model keeps only `chembl_id`, `ontology_id`, `name`, `inchikey`; canonical has `drugbank_id`, `pubchem_cid`, `cas_rn`, `smiles`, `drug_type`, approval/clinical flags. Add xref/metadata fields if molecule queries should work inside Lamin.
- `Pathway` model is missing `go_id`, `kegg_id`, `reactome_id`, and `aspect` even though canonical pathway nodes include them.
- `Tissue` model is missing `bto_id`, `mesh_id`, `fma_id` even though canonical tissue nodes include xref columns.
- `CellType` model has only `ontology_id`, `name`; canonical includes `uberon_id`, `mesh_id`.
- `Transcript` model is missing `protein_id`; canonical transcript has `protein_id`, not only `ensembl_gene_id`, `refseq_mrna`, `ccds_id`.
- `Enhancer` model names coordinate fields `start_pos`/`end_pos`; canonical columns are `start`/`end`. Either sync maps names explicitly or migration should align aliases/fields.
- `Mutation` model includes coordinate allele fields that are not in the current canonical node file; canonical mutation nodes currently contain only `id`, `hgvs`, `clinvar_id`, `gnomad_id`, `name`, `source`.
- `Paper` model stores `pmid`; canonical paper file uses `id` plus `doi`, `pmc_id`, `arxiv_id`, `year`, `source`; sync must map `id -> pmid` and handle `PMID:` prefix policy consistently.
- `Dataset` model has richer fields than canonical (`doi`, `description`, `version`, `source_url`), but canonical currently has only one row with `id`, `name`, `source`.

## Edge/relation model audit

No relation model exists in `lnschema_txgnn.models.py`. All 67 active KG relations are therefore missing as queryable Lamin schema rows, including the 37 canonical relations already present in `v2/edges`.

| Relation | X→Y | Kind | Direct | Canonical/staging status | Canonical edge rows | Evidence rows | lnschema model status |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| `gene_has_transcript` | `gene→transcript` | `central_dogma` | yes | `canonical+validated` | 507365 | — | missing relation model |
| `transcript_encodes_protein` | `transcript→protein` | `central_dogma` | yes | `canonical+validated` | 233995 | — | missing relation model |
| `mutation_in_gene` | `mutation→gene` | `genetic` | yes | `staged-only/deferred` | — | — | missing relation model |
| `mutation_associated_gene` | `mutation→gene` | `genetic` | no | `canonical+validated` | 535093 | 535093 | missing relation model |
| `mutation_affects_transcript` | `mutation→transcript` | `genetic` | yes | `staged-only/deferred` | — | — | missing relation model |
| `mutation_causes_protein_change` | `mutation→protein` | `genetic` | yes | `canonical+validated` | 177735 | 177735 | missing relation model |
| `mutation_overlaps_enhancer` | `mutation→enhancer` | `genetic` | no | `staged-only/deferred` | — | — | missing relation model |
| `mutation_associated_disease` | `mutation→disease` | `genetic` | no | `canonical+validated` | 4656171 | 4656171 | missing relation model |
| `mutation_associated_phenotype` | `mutation→phenotype` | `genetic` | no | `canonical+validated` | 164406 | 169005 | missing relation model |
| `gene_associated_phenotype` | `gene→phenotype` | `phenotype_assoc` | no | `canonical+validated` | 3330 | — | missing relation model |
| `mutation_affects_molecule_response` | `mutation→molecule` | `pharmacological` | no | `canonical+validated` | 4866 | 18595 | missing relation model |
| `gene_ortholog_gene` | `gene→gene` | `genetic` | yes | `canonical+validated` | 161675 | 161675 | missing relation model |
| `enhancer_regulates_gene` | `enhancer→gene` | `regulatory` | no | `canonical+validated` | 48808144 | 48810390 | missing relation model |
| `enhancer_regulates_transcript` | `enhancer→transcript` | `regulatory` | yes | `source-audit-only/deferred` | — | — | missing relation model |
| `gene_coexpressed_gene` | `gene→gene` | `expression` | no | `feature-context-not-edge` | — | — | missing relation model |
| `tissue_expresses_gene` | `tissue→gene` | `expression` | yes | `canonical+validated` | 5338736 | — | missing relation model |
| `tissue_expresses_protein` | `tissue→protein` | `expression` | yes | `canonical+validated` | 137351 | 137531 | missing relation model |
| `cell_type_expresses_gene` | `cell_type→gene` | `expression` | yes | `canonical+validated` | 1561873 | — | missing relation model |
| `cell_type_expresses_protein` | `cell_type→protein` | `expression` | yes | `schema-only/missing` | — | — | missing relation model |
| `cell_line_expresses_gene` | `cell_line→gene` | `experimental` | yes | `canonical+validated` | 20928056 | — | missing relation model |
| `cell_line_expresses_protein` | `cell_line→protein` | `experimental` | yes | `staged-only/deferred` | — | — | missing relation model |
| `cell_line_gene_essentiality` | `cell_line→gene` | `experimental` | no | `staged-only/deferred` | — | — | missing relation model |
| `gene_interacts_gene` | `gene→gene` | `physical` | no | `canonical+validated` | 7424037 | 14336594 | missing relation model |
| `tf_regulates_gene` | `gene→gene` | `regulatory` | yes | `schema-only/missing` | — | — | missing relation model |
| `tf_binds_enhancer` | `gene→enhancer` | `regulatory` | yes | `staged-only/deferred` | — | — | missing relation model |
| `transcript_interacts_protein` | `transcript→protein` | `physical` | yes | `staged-only/deferred` | — | — | missing relation model |
| `transcript_interacts_gene` | `transcript→gene` | `regulatory` | no | `schema-only/missing` | — | — | missing relation model |
| `protein_interacts_protein` | `protein→protein` | `physical` | yes | `canonical+validated` | 3550 | 12288 | missing relation model |
| `pathway_contains_gene` | `pathway→gene` | `pathway` | no | `canonical+validated` | 630932 | 630932 | missing relation model |
| `pathway_contains_protein` | `pathway→protein` | `pathway` | no | `staged-only/deferred` | — | — | missing relation model |
| `pathway_child_of_pathway` | `pathway→pathway` | `ontological` | yes | `canonical+validated` | 147680 | — | missing relation model |
| `molecule_in_pathway` | `molecule→pathway` | `pathway` | no | `canonical+validated` | 1680 | — | missing relation model |
| `molecule_targets_gene` | `molecule→gene` | `pharmacological` | yes | `canonical+validated` | 41239 | 41239 | missing relation model |
| `molecule_targets_protein` | `molecule→protein` | `pharmacological` | yes | `staged-only/deferred` | — | — | missing relation model |
| `molecule_treats_disease` | `molecule→disease` | `pharmacological` | no | `canonical+validated` | 14135 | — | missing relation model |
| `molecule_contraindicates_disease` | `molecule→disease` | `pharmacological` | no | `canonical+validated` | 30675 | — | missing relation model |
| `molecule_synergizes_molecule` | `molecule→molecule` | `pharmacological` | no | `canonical+validated` | 2672628 | — | missing relation model |
| `molecule_parent_of_molecule` | `molecule→molecule` | `ontological` | yes | `canonical+validated` | 4140 | — | missing relation model |
| `cell_type_responds_to_molecule` | `cell_type→molecule` | `pharmacological` | no | `schema-only/missing` | — | — | missing relation model |
| `cell_line_responds_to_molecule` | `cell_line→molecule` | `experimental` | yes | `staged-only/deferred` | — | — | missing relation model |
| `molecule_associated_phenotype` | `molecule→phenotype` | `pharmacological` | no | `canonical+validated` | 64784 | — | missing relation model |
| `disease_associated_gene` | `gene→disease` | `disease_assoc` | yes | `canonical+validated` | 83339 | 2928 | missing relation model |
| `disease_associated_protein` | `protein→disease` | `disease_assoc` | yes | `staged-only/deferred` | — | — | missing relation model |
| `disease_involves_pathway` | `pathway→disease` | `disease_assoc` | yes | `canonical+validated` | 2296 | 2296 | missing relation model |
| `disease_manifests_in_tissue` | `disease→tissue` | `disease_assoc` | no | `schema-only/missing` | — | — | missing relation model |
| `disease_subtype_of_disease` | `disease→disease` | `ontological` | yes | `canonical+validated` | 104809 | — | missing relation model |
| `disease_comorbid_disease` | `disease→disease` | `epidemiological` | no | `feature-context-not-edge` | — | — | missing relation model |
| `disease_has_phenotype` | `disease→phenotype` | `phenotype_assoc` | yes | `canonical+validated` | 241797 | — | missing relation model |
| `phenotype_observed_in_tissue` | `tissue→phenotype` | `phenotype_assoc` | yes | `schema-only/missing` | — | — | missing relation model |
| `phenotype_subtype_of_phenotype` | `phenotype→phenotype` | `ontological` | yes | `canonical+validated` | 37472 | — | missing relation model |
| `tissue_subtype_of_tissue` | `tissue→tissue` | `ontological` | yes | `canonical+validated` | 28064 | — | missing relation model |
| `cell_type_found_in_tissue` | `cell_type→tissue` | `ontological` | yes | `staged-only/deferred` | — | — | missing relation model |
| `cell_type_involved_in_disease` | `cell_type→disease` | `disease_assoc` | no | `source-audit-only/deferred` | — | — | missing relation model |
| `cell_type_subtype_of_cell_type` | `cell_type→cell_type` | `ontological` | yes | `staged-only/deferred` | — | — | missing relation model |
| `cell_line_models_disease` | `cell_line→disease` | `experimental` | no | `staged-only/deferred` | — | — | missing relation model |
| `cell_line_derived_from_cell_type` | `cell_line→cell_type` | `experimental` | yes | `staged-only/deferred` | — | — | missing relation model |
| `cell_line_derived_from_tissue` | `cell_line→tissue` | `experimental` | yes | `canonical+validated` | 1092 | — | missing relation model |
| `cell_line_from_organism` | `cell_line→organism` | `metadata` | yes | `canonical+validated` | 1183 | 1183 | missing relation model |
| `organism_has_gene` | `organism→gene` | `genetic` | yes | `canonical+validated` | 109325 | — | missing relation model |
| `organism_has_tissue` | `organism→tissue` | `ontological` | yes | `canonical+validated` | 16061 | — | missing relation model |
| `paper_produced_dataset` | `paper→dataset` | `metadata` | yes | `staged-only/deferred` | — | — | missing relation model |
| `paper_cites_paper` | `paper→paper` | `literature` | yes | `staged-only/deferred` | — | — | missing relation model |
| `dataset_contains_disease` | `dataset→disease` | `metadata` | yes | `staged-only/deferred` | — | — | missing relation model |
| `dataset_contains_molecule` | `dataset→molecule` | `metadata` | yes | `staged-only/deferred` | — | — | missing relation model |
| `dataset_contains_cell_type` | `dataset→cell_type` | `metadata` | yes | `staged-only/deferred` | — | — | missing relation model |
| `dataset_contains_cell_line` | `dataset→cell_line` | `metadata` | yes | `canonical+validated` | 1183 | — | missing relation model |
| `dataset_contains_tissue` | `dataset→tissue` | `metadata` | yes | `canonical+validated` | 27 | — | missing relation model |

### Edge column families in canonical Parquet

All canonical edge files have the base columns `x_id`, `x_type`, `y_id`, `y_type`, `relation`, `display_relation`, `source`, `credibility`. Some relations add source-specific value columns:

- `cell_line_derived_from_tissue`: tissue_name
- `cell_line_expresses_gene`: gene_effect, expression, is_essential
- `cell_line_from_organism`: base columns only
- `cell_type_expresses_gene`: tpm, expression_level
- `dataset_contains_cell_line`: base columns only
- `dataset_contains_tissue`: base columns only
- `disease_associated_gene`: score
- `disease_has_phenotype`: base columns only
- `disease_involves_pathway`: score, pathway_name
- `disease_subtype_of_disease`: base columns only
- `enhancer_regulates_gene`: e2g_score
- `gene_associated_phenotype`: base columns only
- `gene_has_transcript`: transcript_biotype
- `gene_interacts_gene`: base columns only
- `gene_ortholog_gene`: homology_type, species_id, species_name, is_high_confidence, query_percentage_identity, target_percentage_identity
- `molecule_associated_phenotype`: base columns only
- `molecule_contraindicates_disease`: base columns only
- `molecule_in_pathway`: base columns only
- `molecule_parent_of_molecule`: base columns only
- `molecule_synergizes_molecule`: base columns only
- `molecule_targets_gene`: action_type
- `molecule_treats_disease`: base columns only
- `mutation_affects_molecule_response`: pgx_category
- `mutation_associated_disease`: score, datatype, studyLocusId
- `mutation_associated_gene`: score, datatype, studyLocusId
- `mutation_associated_phenotype`: base columns only
- `mutation_causes_protein_change`: amino_acid_change, uniprot_id
- `organism_has_gene`: base columns only
- `organism_has_tissue`: base columns only
- `pathway_child_of_pathway`: base columns only
- `pathway_contains_gene`: go_evidence, go_aspect
- `phenotype_subtype_of_phenotype`: base columns only
- `protein_interacts_protein`: base columns only
- `tissue_expresses_gene`: tpm, expression_level
- `tissue_expresses_protein`: base columns only
- `tissue_subtype_of_tissue`: base columns only
- `transcript_encodes_protein`: base columns only

These source-specific fields should not become 67 bespoke model schemas in the first Lamin migration. Store them in a JSON metadata field on a generic edge row and promote only high-value repeated columns later if queries need them.

## Proposed schema design

### Preferred design: generic typed edge + evidence tables

Add these models to `lnschema_txgnn.models.py` in a future implementation task:

```python
class KGEdge(SQLRecord, TracksRun, TracksUpdates):
    uid = CharField(max_length=12, editable=False, unique=True, db_index=True, default=base62_12)
    edge_key = CharField(max_length=255, unique=True, db_index=True)
    x_id = CharField(max_length=128, db_index=True)
    x_type = CharField(max_length=32, db_index=True)
    y_id = CharField(max_length=128, db_index=True)
    y_type = CharField(max_length=32, db_index=True)
    relation = CharField(max_length=96, db_index=True)
    display_relation = CharField(max_length=128, null=True, db_index=True)
    source = CharField(max_length=128, null=True, db_index=True)
    credibility = IntegerField(null=True, db_index=True)
    metadata = JSONField(null=True)
```

`edge_key` should be deterministic and idempotent, for example:

```text
sha256(relation + "	" + x_type + "	" + x_id + "	" + y_type + "	" + y_id)
```

Add database indexes:

- unique: `edge_key`
- composite: `(relation, x_id)` for source-forward relation queries
- composite: `(relation, y_id)` for target-reverse relation queries
- composite: `(x_type, x_id)` and `(y_type, y_id)` for neighborhood queries
- composite: `(relation, x_type, y_type)` for relation browsing
- optional composite: `(source, relation)` for provenance filters

Evidence model:

```python
class KGEdgeEvidence(SQLRecord, TracksRun, TracksUpdates):
    uid = CharField(max_length=12, editable=False, unique=True, db_index=True, default=base62_12)
    evidence_key = CharField(max_length=255, unique=True, db_index=True)
    edge_key = CharField(max_length=255, db_index=True)
    relation = CharField(max_length=96, db_index=True)
    x_id = CharField(max_length=128, db_index=True)
    x_type = CharField(max_length=32, db_index=True)
    y_id = CharField(max_length=128, db_index=True)
    y_type = CharField(max_length=32, db_index=True)
    evidence_type = CharField(max_length=96, null=True, db_index=True)
    source = CharField(max_length=128, null=True, db_index=True)
    source_dataset = CharField(max_length=128, null=True, db_index=True)
    source_record_id = CharField(max_length=255, null=True, db_index=True)
    paper_id = CharField(max_length=64, null=True, db_index=True)
    dataset_id = CharField(max_length=128, null=True, db_index=True)
    study_id = CharField(max_length=255, null=True, db_index=True)
    evidence_score = FloatField(null=True, db_index=True)
    predicate = CharField(max_length=128, null=True, db_index=True)
    direction = CharField(max_length=64, null=True, db_index=True)
    metadata = JSONField(null=True)
```

Why generic is preferred:

- 67 active relations already exist, with 30 not canonical yet and multiple staged-only families. One table can absorb new relations without a migration per relation.
- Canonical Parquet already uses generic edge/evidence columns.
- Query helpers can enforce relation semantics while storage stays compact.
- Idempotent sync is straightforward with deterministic keys.

### Alternative design: one model/table per relation

A per-relation class such as `DiseaseAssociatedGeneEdge` would expose typed field names and strict endpoint semantics, but it is not recommended as the first migration because it means at least 67 models now and one migration every time a relation changes. It also makes cross-relation neighborhood queries awkward.

A hybrid can be added later: keep `KGEdge` as source of truth and expose lightweight Python managers or proxy classes for common relation families.

## Evidence model strategy

Use `KGEdgeEvidence` as a generic support table. Preserve raw source-specific evidence details in `metadata`, not lossy normalized fields. The common indexed fields should mirror `manage_db/kg_evidence.py` / current evidence Parquet conventions:

- edge identity: `edge_key`, `relation`, `x_id`, `x_type`, `y_id`, `y_type`
- source identity: `source`, `source_dataset`, `source_record_id`, `release`, `license`
- provenance: `paper_id`, `dataset_id`, `study_id`, `created_at`
- statistics/effect: `evidence_score`, `effect_size`, `p_value`, `confidence_interval`, `direction`, `predicate`
- extraction context: `text_span`, `section`, `extraction_method`

`protein_interacts_protein` currently has a richer evidence schema with BioGRID/IntAct-like fields. Keep those fields in `metadata` unless a concrete query requires promotion.

Do not require every edge to have evidence rows before sync. Current canonical KG has 37 edge files and 15 evidence files; 22 canonical edge relations have no evidence file yet.

## Feature and embedding strategy

Canonical feature tables verified:

| Feature table | Rows | Leading columns |
| --- | ---: | --- |
| `cell_line_textual_summary` | 1140 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `cell_type_textual_summary` | 3135 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `disease_textual_summary` | 26395 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `gene_textual_summary` | 212029 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `molecule_fingerprint` | 18614 | `feature_key, feature_table, node_id, node_type, fingerprint_kind, fingerprint_format, on_bits, n_bits…` |
| `molecule_textual_summary` | 22230 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `pathway_textual_summary` | 37492 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `phenotype_textual_summary` | 13810 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `protein_sequence` | 112051 | `feature_key, feature_table, node_id, node_type, sequence_kind, sequence, length, alphabet…` |
| `protein_textual_summary` | 162163 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `tissue_textual_summary` | 11942 | `feature_key, feature_table, node_id, node_type, summary_kind, summary_text, source, source_dataset…` |
| `transcript_sequence` | 187268 | `feature_key, feature_table, node_id, node_type, sequence_kind, sequence, length, alphabet…` |

Add a generic feature registry only if users need feature lookup from LaminDB:

```python
class KGFeature(SQLRecord, TracksRun, TracksUpdates):
    feature_key = CharField(max_length=255, unique=True, db_index=True)
    feature_table = CharField(max_length=128, db_index=True)
    node_id = CharField(max_length=128, db_index=True)
    node_type = CharField(max_length=32, db_index=True)
    feature_kind = CharField(max_length=96, null=True, db_index=True)
    value_ref = CharField(max_length=2048, null=True)  # artifact/path/chunk pointer
    metadata = JSONField(null=True)
```

Do not store large sequence text, summary text, fingerprints, or embedding vectors directly in the relational registry by default. Keep heavy feature payloads in canonical Parquet/Artifacts and store pointers plus searchable metadata. For embeddings, use a dedicated table or artifact pointer shape:

```python
class KGEmbedding(SQLRecord, TracksRun, TracksUpdates):
    embedding_key = CharField(max_length=255, unique=True, db_index=True)
    subject_id = CharField(max_length=128, db_index=True)
    subject_type = CharField(max_length=32, db_index=True)  # node, edge, evidence
    embedding_model = CharField(max_length=128, db_index=True)
    dimension = IntegerField(db_index=True)
    vector_ref = CharField(max_length=2048)  # Parquet/AnnData/Artifact path
    metadata = JSONField(null=True)
```

This keeps LaminDB as the catalog/query surface while vector search stays in a vector/Arrow/AnnData artifact layer.

## Query-helper requirements

Minimum helpers should live in `lnschema_txgnn` or a sibling `manage_db/lamin_query.py` module and should avoid raw SQL for common tasks.

Required low-level helpers:

```python
def edges(
    *,
    source_id: str | None = None,
    target_id: str | None = None,
    relation: str | list[str] | None = None,
    source_type: str | None = None,
    target_type: str | None = None,
    source: str | None = None,
    min_credibility: int | None = None,
    limit: int | None = None,
): ...

def evidence_for_edge(*, edge_key: str | None = None, relation: str | None = None, x_id: str | None = None, y_id: str | None = None): ...

def neighbors(node_id: str, *, node_type: str | None = None, relations: list[str] | None = None, direction: str = "both"): ...
```

Disease/gene convenience API:

```python
def diseases_for_gene(gene_id: str, *, include_evidence: bool = False, min_score: float | None = None):
    # relation is named disease_associated_gene, but canonical direction is gene -> disease
    return edges(source_id=gene_id, source_type="gene", target_type="disease", relation="disease_associated_gene")


def diseases_for_gene_name(gene_name: str, *, include_evidence: bool = False):
    gene = Gene.filter(symbol=gene_name).one_or_none() or Gene.filter(name=gene_name).one_or_none()
    if gene is None:
        gene = Gene.filter(gene_name=gene_name).one_or_none()  # if migrated as canonical column
    return diseases_for_gene(gene_id=gene.ensembl_gene_id, include_evidence=include_evidence)
```

Also provide reverse helpers:

```python
def genes_for_disease(disease_id: str):
    return edges(target_id=disease_id, target_type="disease", source_type="gene", relation="disease_associated_gene")
```

### Feasibility of `bt.disease(associated_with_gene_id=...)`

A `bt.disease(associated_with_gene_id=...)` style is not a good first-class Lamin/bionty API target:

- bionty registries model ontology entities, not arbitrary graph traversals.
- Jouvence disease IDs deliberately preserve EFO/OBA/HP/MONDO-like source IDs without forcing MONDO equivalence.
- `disease_associated_gene` has KG-specific direction/provenance and should not be hidden as a bionty disease field.

A feasible ergonomic equivalent is:

```python
txs.Disease.associated_with_gene_id("ENSG00000139618")
# or
txs.query.diseases_for_gene(gene_id="ENSG00000139618")
```

If Lamin managers support custom classmethods cleanly, add classmethod wrappers on `Disease`, but have them query `KGEdge` under the hood.

## Sync and migration plan

### Phase 0: design approval

- Review this document.
- Decide whether to add missing exact-ID node models (`Phenotype`, `CellLine`, `Organism`) in the same implementation card as edge/evidence tables or as a preparatory migration.
- Decide whether edge/evidence rows should be fully synced into LaminDB immediately or lazily queried from Parquet via helpers.

### Phase 1: node schema parity migration

Next migration after current `0006_custom_exact_id_gap_registries.py` should:

- add `Phenotype`, `CellLine`, `Organism` exact-ID models;
- add missing xref fields to `Molecule`, `Pathway`, `Tissue`, `CellType`, `Transcript` as needed;
- add explicit canonical-id mapping comments/docstrings for fields whose model name differs from canonical column name (`id -> ensembl_gene_id`, `id -> ontology_id`, `start/end -> start_pos/end_pos`, etc.);
- generate and commit a Django migration with `uv run lamin migration makemigrations lnschema_txgnn` or the repo’s documented Lamin migration command.

Expected node rows to sync after parity: `55,523,691` total, dominated by `enhancer` `48,808,144` rows and `paper` `2,958,199` rows. Full node sync may be too large for a local SQLite-style Lamin instance unless batched and reviewed.

### Phase 2: add generic `KGEdge` and `KGEdgeEvidence`

- Add models and migration.
- Add indexes listed above. For Django, use `models.Index(fields=[...])` in `Meta.indexes`; keep deterministic unique `edge_key` / `evidence_key`.
- Do not make DB foreign keys to every node table in v1 because endpoints span 15 node types and some exact-ID models may be optional. Use string IDs/types for stable KG parity.
- Add validators that ensure `relation` is in `RELATION_BY_NAME` and endpoint types match the declared relation.

Expected canonical edge rows if fully synced today: `94,880,924`. This is large; plan for chunked bulk upsert and consider relation-scoped sync rather than one all-at-once migration.

### Phase 3: idempotent sync

Implement a command such as:

```bash
uv run python -m manage_db.sync_lnschema_txgnn   --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2   --relations disease_associated_gene,molecule_targets_gene   --batch-size 10000   --dry-run
```

Idempotency rules:

- node key: canonical `node_type + id` mapped to model primary ID field;
- edge key: deterministic hash of relation/endpoints;
- evidence key: deterministic hash of edge key + source/source_record_id + evidence_type + stable row discriminator;
- upsert by key, update mutable metadata fields, never duplicate rows;
- preserve raw canonical IDs exactly; no forced bionty/pertdb equivalence.

### Phase 4: query helpers and smoke tests

Add tests that prove the requested behavior without loading the full KG:

- fixture with one gene, one disease, one `disease_associated_gene` edge, two evidence rows;
- `diseases_for_gene(gene_id=...)` returns disease IDs/names;
- `diseases_for_gene_name(...)` resolves exact gene ID and returns same result;
- `genes_for_disease(...)` reverse traversal works;
- `evidence_for_edge(...)` returns support rows;
- invalid relation endpoint types fail validation.

### Phase 5: optional full-scale sync gates

Before syncing tens of millions of rows into a live Lamin instance:

- benchmark row insertion/upsert for one small relation and one large relation;
- record SQLite/Postgres DB size growth;
- ensure indexes do not make ingestion impossible;
- run relation-scoped counts against Parquet metadata;
- require review before full sync of `enhancer_regulates_gene` (`48,808,144` rows), `cell_line_expresses_gene` (`20,928,056` rows), and `gene_interacts_gene` (`7,424,037` rows).

## Rollback risk

Low-risk pieces:

- adding nullable fields to node models;
- adding empty `KGEdge` / `KGEdgeEvidence` tables;
- adding Python query helpers that can use fixtures or Parquet.

Medium-risk pieces:

- adding unique constraints to existing partially-synced node tables if duplicates exist;
- syncing millions of rows into local LaminDB storage;
- adding too many composite indexes before measuring ingestion speed.

High-risk pieces:

- full sync of all `94,880,924` canonical edge rows without batch/restart logic;
- full sync of 48M enhancer nodes plus 48M enhancer→gene edges into a small local database;
- any migration that renames existing fields instead of adding nullable aliases and backfilling.

Rollback approach:

- Migrations should be additive first. Avoid destructive renames/drops until a later cleanup card.
- For sync, write relation-scoped checkpoints and allow `--delete-relation relation_name` cleanup of only rows from the failed sync run.
- Keep canonical Parquet/GCS as source of truth. LaminDB can be rebuilt from canonical artifacts if sync state is bad.

## Implementation acceptance criteria for follow-up card

A future implementation task should be accepted only when:

- migrations create missing node models plus `KGEdge` and `KGEdgeEvidence`;
- sync dry-run reports expected row counts from canonical Parquet;
- a bounded sync fixture or small relation actually populates Lamin tables;
- query helpers answer `diseases_for_gene(gene_id=...)` and `diseases_for_gene_name(...)` without raw SQL by the caller;
- tests cover forward/reverse edge traversal and evidence lookup;
- no public bionty/pertdb equivalence is forced for exact KG IDs.
