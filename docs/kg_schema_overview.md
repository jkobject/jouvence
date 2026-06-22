# TxGNN / Jouvence KG Schema Overview

This file holds the detailed schema description that used to live in
`CLAUDE.md`. Keep `CLAUDE.md` as boot context only; update this document when
node types, relation lifecycle statuses, evidence layout, or graph export
interfaces change.

### Node Schema & GCS Coverage

| Node type    | Primary ontology / ID namespace               | GCS? |       Rows | Comment                                                                                               |
| ------------ | --------------------------------------------- | ---- | ---------: | ----------------------------------------------------------------------------------------------------- |
| `paper`      | PubMed (`PMID:12345678`)                      | yes  |  2,958,199 | Europe PMC PMIDs; live `lnschema_txgnn.Paper` parity passes                                           |
| `gene`       | Ensembl (`ENSG00000139618`)                   | yes  |    267,830 | OpenTargets 26.03 target IDs; expression/evidence + orthology stubs added                    |
| `transcript` | Ensembl (`ENST00000380152`)                   | yes  |    507,365 | OpenTargets 26.03 target transcripts                                                                  |
| `protein`    | Ensembl Protein (`ENSP00000369497`)           | yes  |    233,995 | OpenTargets 26.03 target translations; UniProt is an xref                                             |
| `pathway`    | Reactome / GO (`R-HSA-5633007`, `GO:0008150`) | yes  |     48,575 | OpenTargets Reactome evidence stubs + GO terms                                               |
| `molecule`   | ChEMBL (`CHEMBL941`)                          | yes  |     31,007 | OpenTargets `drug_molecule` xrefs/properties; pharmacogenomics stubs added                   |
| `mutation`   | dbSNP (`rs7412`) / gnomAD-style variant IDs   | yes  |  2,589,509 | pharmacogenomics stubs + promoted protein-change/GWAS mutation union                                  |
| `disease`    | EFO (`EFO:0000305`)                           | yes  |     41,859 | OpenTargets disease IDs; normalized CURIE IDs with duplicate underscore/colon rows collapsed |
| `cell_type`  | CL (`CL:0000576`)                             | yes  |      3,513 | OpenTargets biosample CL IDs                                                                          |
| `tissue`     | UBERON (`UBERON:0002107`)                     | yes  |     16,061 | UBERON-derived + OpenTargets biosample                                                                |
| `phenotype`  | HP (`HP:0000118`)                             | yes  |     16,449 | HP-derived + OpenTargets HPO stubs                                                                    |
| `cell_line`  | Cellosaurus (`CVCL_0023`)                     | yes  |      1,183 | OpenTargets DepMap/essentiality cell model IDs; source-backed remaining slice                         |
| `organism`   | NCBI Taxonomy (`NCBITaxon:9606`)              | yes  |          1 | human organism node; LaminDB/bionty parity passes                                                     |
| `dataset`    | DOI / UUID (`DOI:10.1038/s41586-023-06221-2`) | yes  |          1 | OpenTargets DepMap/essentiality dataset provenance node                                               |
| `enhancer`   | ENCODE/OpenTargets interval ID                | yes  | 48,808,144 | OpenTargets enhancer interval IDs from enhancer-to-gene evidence                                      |

Planned source-native node families from S1 policy (`docs/source_native_expansion_policy.md`):

- `protein_complex`: should be a node type for named source-native protein complexes; do not flatten complexes into generic pairwise PPIs or evidence-only fields when the source has a complex identity.
- `ptm_site` / structured PTM event: site-level PTM evidence should become a structured site/event representation once the schema is finalized; vague PTM mentions remain evidence metadata.
- `mature_mirna` / `mirna_precursor` candidate labels: create miR-primary nodes only when a mature/precursor miRNA entity is distinct from an existing ENST `transcript` node. True 1:1 miRBase/hsa-miR mappings should be aliases/xrefs on existing transcript nodes.

### Edge Schema & GCS Coverage

All edges stored as Parquet with at minimum:

```
x_id, x_type, y_id, y_type, relation, display_relation,
source, credibility, [additional metadata columns...]
```

**Kind legend:**

- `central_dogma` — molecular biology sequence/expression flow
- `regulatory` — transcriptional / epigenetic control
- `physical` — direct molecular binding or complex membership
- `genetic` — genomic position or variant association
- `pathway` — functional pathway membership
- `pharmacological` — drug action on target or disease
- `expression` — quantitative abundance in context
- `disease_assoc` — statistical or causal disease link
- `phenotype_assoc` — phenotypic consequence
- `ontological` — IS-A / part-of hierarchy
- `experimental` — derived from cell line / in-vitro assay
- `epidemiological` — population-level co-occurrence
- `literature` — NLP / co-mention in text
- `metadata` — dataset provenance

**Direct flag:**

- yes = direct biological interaction (physical, mechanistic, sequence-derived)
- maybe = sometimes direct depending on source
- no = associative / statistical / indirect

Schema-cleanup and evidence doctrine live in
`docs/evidence_and_edge_schema_plan.md`. New imports should treat papers and
source records primarily as evidence/support metadata for biological edges, not
as the primary biological assertion.

| Relation | Source | Target | Kind | Direct? | GCS? | Rows | Comment |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| `gene_has_transcript` | `gene` | `transcript` | `central_dogma` | yes | yes | 507,365 | Transcription |
| `transcript_encodes_protein` | `transcript` | `protein` | `central_dogma` | yes | yes | 233,995 | Translation |
| `mutation_in_gene` | `mutation` | `gene` | `genetic` | yes | no | - | Physical/genomic containment only; do not use for L2G/GWAS association or OpenTargets L2G targetId smoke output |
| `mutation_associated_gene` | `mutation` | `gene` | `genetic` | no | yes | 535,093 | Statistical/functional locus-to-gene prediction (for example OpenTargets L2G/GWAS); canonical promoted GWAS/L2G relation with evidence support |
| `mutation_affects_transcript` | `mutation` | `transcript` | `genetic` | yes | no | - | Transcript-level consequence such as splicing/UTR/coding-transcript effect; active schema relation but not canonical until bounded source-specific evidence and endpoint policy are selected |
| `mutation_causes_protein_change` | `mutation` | `protein` | `genetic` | yes | yes | 177,735 | Amino acid change with ENSP protein endpoint; canonical OpenTargets protein-change edge and evidence files exist |
| `mutation_overlaps_enhancer` | `mutation` | `enhancer` | `genetic` | no | no | - | Retain only variants that also have disease, phenotype, drug-response, or equivalent downstream association evidence; overlap itself is contextual evidence, not a standalone causal edge. |
| `mutation_associated_disease` | `mutation` | `disease` | `genetic` | no | yes | 4,656,171 | GWAS / ClinVar / OpenTargets known-variant disease association; canonical edge exists, evidence backfill remains next tranche |
| `mutation_associated_phenotype` | `mutation` | `phenotype` | `genetic` | no | yes | 164,406 | OpenTargets EVA/ClinVar HP-only mutation→phenotype association across all clinical-significance classes; exact assertion class is preserved in evidence predicate metadata. |
| `gene_associated_phenotype` | `gene` | `phenotype` | `phenotype_assoc` | no | yes | 3,330 | Non-causal HPO gene-to-phenotype association; direction is gene→phenotype |
| `mutation_affects_molecule_response` | `mutation` | `molecule` | `pharmacological` | no | yes | 4,866 | Pharmacogenomics |
| `gene_ortholog_gene` | `gene` | `gene` | `genetic` | yes | yes | 161,675 | Cross-species orthology |
| `enhancer_regulates_gene` | `enhancer` | `gene` | `regulatory` | no | yes | 48,808,144 | ENCODE-rE2G composite enhancer-to-gene prediction; preserve biosample, assay feature scores, distance, study, and model score in edge/evidence metadata. |
| `enhancer_regulates_transcript` | `enhancer` | `transcript` | `regulatory` | yes | no | - | transcript-specific/TSS-specific regulation; require a source that directly names ENST/TSS endpoints and is not inferred by expanding enhancer→gene to all transcripts |
| `gene_coexpressed_gene` | `gene` | `gene` | `expression` | no | no | - | Co-expression network |
| `tissue_expresses_gene` | `tissue` | `gene` | `expression` | no | yes | 5,338,736 | GTEx / HPA bulk RNA |
| `tissue_expresses_protein` | `tissue` | `protein` | `expression` | no | yes | 137,351 | Direct Human Protein Atlas 25.1 tissue protein expression/intensity with UniProt→ENSP endpoint mapping and evidence metadata; not populated from RNA projection. |
| `cell_type_expresses_gene` | `cell_type` | `gene` | `expression` | no | yes | 1,561,873 | scRNA-seq (CellxGene) |
| `cell_type_expresses_protein` | `cell_type` | `protein` | `expression` | no | no | - | Direct cell-type protein abundance/staining source only; do not populate from RNA projection. |
| `cell_line_expresses_gene` | `cell_line` | `gene` | `experimental` | no | yes | 20,928,056 | RNA-seq (CCLE…) |
| `cell_line_expresses_protein` | `cell_line` | `protein` | `experimental` | no | no | - | Direct cell-line proteomics source only; do not populate from mRNA projection. |
| `cell_line_gene_essentiality` | `cell_line` | `gene` | `experimental` | no | no | - | DepMap/Project Score/CRISPR gene essentiality or dependency measurement; preserve score/effect/study fields in evidence or feature tables and do not model as protein expression. |
| `gene_interacts_gene` | `gene` | `gene` | `physical` | no | yes | 7,424,037 | Broad gene/gene-product interaction assertion with source-specific evidence metadata; split source-native TF/protein/transcript subsets into the relations below when endpoints/assertions justify it. |
| `tf_regulates_gene` | `gene` | `gene` | `regulatory` | yes | no | - | Schema-valid but do not populate for now; future use requires a stricter human-approved TF regulation source policy. |
| `tf_binds_enhancer` | `gene` | `enhancer` | `regulatory` | yes | no | - | TF gene product binds enhancer/regulatory interval; ReMap/ChIP-like observed binding can combine with motif support, with evidence type distinguishing observed vs motif-predicted. |
| `transcript_interacts_protein` | `transcript` | `protein` | `physical` | yes | no | - | RNA/transcript–protein interaction with transcript/protein-native endpoints; preserve assay, source database, score, and record IDs in evidence. |
| `transcript_interacts_gene` | `transcript` | `gene` | `regulatory` | no | no | - | Transcript/RNA to gene regulatory or interaction assertion; preserve mechanism, direction, sign/effect, source database, and record IDs in evidence. |
| `protein_interacts_protein` | `protein` | `protein` | `physical` | yes | no | - | Direct protein/isoform interaction only, with protein-native endpoints and evidence metadata. |
| `protein_part_of_complex` | `protein` | `protein_complex` | `physical` | yes | no | - | Planned relation for source-native complex membership once `protein_complex` nodes are added; preserve complex source ID, stoichiometry/expansion method, and membership evidence. |
| `pathway_contains_gene` | `pathway` | `gene` | `pathway` | no | yes | 630,932 | Reactome / GO; staged evidence backfill covers 630,932/630,932 edges with OpenTargets `go`, TxGNN `txgnn_legacy_go`, and TxGNN `txgnn_legacy_reactome` support rows. |
| `pathway_contains_protein` | `pathway` | `protein` | `pathway` | no | no | staged: 15,436 | Protein-native pathway or complex membership source only, with protein endpoints. Reactome `UniProt2Reactome_All_Levels` staged pilot has 15,436 edges / 18,068 evidence rows, endpoint anti-joins clean; keep staged-only pending review of all-level Reactome semantics. See `docs/reactome_pathway_contains_protein_staged_pilot.md`. |
| `pathway_child_of_pathway` | `pathway` | `pathway` | `ontological` | yes | yes | 147,680 | Reactome hierarchy |
| `molecule_in_pathway` | `molecule` | `pathway` | `pathway` | no | yes | 1,680 | Metabolic pathway |
| `molecule_targets_gene` | `molecule` | `gene` | `pharmacological` | no | yes | 41,239 | Drug/compound target relation for sources whose native target endpoint is a gene or OpenTargets Ensembl target ID; preserve source MoA/action metadata in evidence. |
| `molecule_targets_protein` | `molecule` | `protein` | `pharmacological` | no | no | - | Drug/compound target relation for sources that directly identify a protein or isoform endpoint. |
| `molecule_treats_disease` | `molecule` | `disease` | `pharmacological` | no | yes | 14,135 | Indication (clinical) |
| `molecule_contraindicates_disease` | `molecule` | `disease` | `pharmacological` | no | yes | 30,675 | Contraindication |
| `molecule_synergizes_molecule` | `molecule` | `molecule` | `pharmacological` | no | yes | 2,672,628 | Drug combination synergy or interaction-effect relation; not a physical molecular interaction. |
| `molecule_parent_of_molecule` | `molecule` | `molecule` | `ontological` | yes | yes | 4,140 | Chemical/drug parent-child hierarchy relation. |
| `cell_type_responds_to_molecule` | `cell_type` | `molecule` | `pharmacological` | no | no | - | Drug screen / perturbation |
| `cell_line_responds_to_molecule` | `cell_line` | `molecule` | `experimental` | yes | no | - | GDSC / PRISM viability |
| `molecule_associated_phenotype` | `molecule` | `phenotype` | `pharmacological` | yes | yes | 64,784 | Non-causal molecule-to-phenotype side-effect/rescue association; direction is molecule→phenotype |
| `disease_associated_gene` | `gene` | `disease` | `disease_assoc` | yes | yes | 83,339 | Gene→disease direction for causal/directed disease association; evidence preserves source predicate/score/provenance. |
| `disease_associated_protein` | `protein` | `disease` | `disease_assoc` | yes | no | - | Protein→disease direction for protein-native causal/directed disease association. |
| `disease_involves_pathway` | `pathway` | `disease` | `disease_assoc` | yes | yes | 2,296 | Pathway→disease direction for causal/directed pathway involvement; evidence preserves enrichment/provenance. |
| `disease_manifests_in_tissue` | `disease` | `tissue` | `disease_assoc` | no | no | - | Pathology annotation |
| `disease_subtype_of_disease` | `disease` | `disease` | `ontological` | yes | yes | 104,809 | EFO / MONDO hierarchy |
| `disease_comorbid_disease` | `disease` | `disease` | `epidemiological` | no | no | - | Co-occurrence in EHR |
| `disease_has_phenotype` | `disease` | `phenotype` | `phenotype_assoc` | yes | yes | 241,797 | HPO annotation |
| `phenotype_observed_in_tissue` | `tissue` | `phenotype` | `phenotype_assoc` | yes | no | - | Tissue→phenotype direction for directed tissue manifestation context. |
| `phenotype_subtype_of_phenotype` | `phenotype` | `phenotype` | `ontological` | yes | yes | 37,472 | HPO hierarchy |
| `tissue_subtype_of_tissue` | `tissue` | `tissue` | `ontological` | yes | yes | 28,064 | UBERON parent-child hierarchy |
| `cell_type_found_in_tissue` | `cell_type` | `tissue` | `ontological` | yes | no | - | Cell Ontology / UBERON |
| `cell_type_involved_in_disease` | `cell_type` | `disease` | `disease_assoc` | yes | no | - | scRNA disease enrichment |
| `cell_type_subtype_of_cell_type` | `cell_type` | `cell_type` | `ontological` | yes | no | - | Cell Ontology IS-A |
| `cell_line_models_disease` | `cell_line` | `disease` | `experimental` | no | no | - | Curated annotation |
| `cell_line_derived_from_cell_type` | `cell_line` | `cell_type` | `experimental` | yes | no | - | Cellosaurus |
| `cell_line_derived_from_tissue` | `cell_line` | `tissue` | `experimental` | yes | yes | 1,092 | Cellosaurus origin |
| `cell_line_from_organism` | `cell_line` | `organism` | `metadata` | no | yes | 1,183 | Donor species |
| `organism_has_gene` | `organism` | `gene` | `genetic` | no | yes | 109,325 | Ensembl species |
| `organism_has_tissue` | `organism` | `tissue` | `ontological` | no | yes | 16,061 | Anatomy ontology |
| `paper_produced_dataset` | `paper` | `dataset` | `metadata` | yes | no | - | Provenance |
| `paper_cites_paper` | `paper` | `paper` | `literature` | yes | no | - | Citation graph |
| `dataset_contains_disease` | `dataset` | `disease` | `metadata` | no | no | - | Measured entity |
| `dataset_contains_molecule` | `dataset` | `molecule` | `metadata` | no | no | - | Measured entity |
| `dataset_contains_cell_type` | `dataset` | `cell_type` | `metadata` | no | no | - | Measured entity |
| `dataset_contains_cell_line` | `dataset` | `cell_line` | `metadata` | no | yes | 1,183 | Measured entity |
| `dataset_contains_tissue` | `dataset` | `tissue` | `metadata` | no | yes | 27 | Measured entity |

## Schema cleanup / modeling decisions

- Relation names describe the biological assertion and endpoint type in the active KG.
- Gene-level sources stay in gene-level relations (`molecule_targets_gene`, `gene_interacts_gene`, `pathway_contains_gene`); split to protein/TF/transcript-specific relations only when the source is native to those endpoints/assertions. Directed disease associations use source/cause → disease direction (`disease_associated_gene` is gene→disease).
- Protein-level relations are used only for direct protein/isoform evidence (`molecule_targets_protein`, `protein_interacts_protein`, `pathway_contains_protein`, `disease_associated_protein`, `tissue_expresses_protein`).
- Protein complexes are planned as nodes, not just evidence fields. PTMs with site-level support should use `ptm_site` / structured event modeling; vague PTM support remains evidence metadata.
- Existing ENST transcript nodes remain the transcript layer. Do not choose a main transcript for genes; preserve many transcript isoforms and isoform→protein mappings.
- miRBase/hsa-miR IDs should be aliases/xrefs on existing ENST transcript nodes when there is a true 1:1 mapping; create miR-primary nodes only for distinct mature/precursor miRNA entities.
- Non-causal exceptions such as ABC/rE2G predictions, motifs, coexpression/correlation, and disease-association-only modules are allowed when useful, but evidence must mark them as predictive, correlative, association, candidate, or context-specific rather than causal/mechanistic.
- Molecule–molecule drug-effect rows use `molecule_synergizes_molecule`; chemical hierarchy rows use `molecule_parent_of_molecule`. `interacts` is reserved for physical molecular interactions.
- Phenotype relations use entity→phenotype direction (`gene_associated_phenotype`, `molecule_associated_phenotype`).
- Evidence rows carry source-specific predicates, scores, study IDs, paper IDs, assay details, and provenance; edge rows stay deduplicated graph assertions.

### Credibility Score

| Score | Meaning                                                            |
| ----- | ------------------------------------------------------------------ |
| `3`   | Established fact (curated DB, no ambiguity)                        |
| `2`   | Multiple independent evidence (papers from distinct author groups) |
| `1`   | Single evidence (one paper, possibly same authors)                 |

### Evidence Layer

Evidence/source records are support metadata for edge assertions, not primarily
standalone biological edges. Storage shape is `evidence/{relation}.parquet`,
keyed by `(relation, x_id, y_id)` / `edge_key`, with support fields such as
`evidence_type`, `source`, `source_dataset`, `source_record_id`, `paper_id`,
`dataset_id`, `study_id`, `evidence_score`, effect-size/statistical fields,
direction/predicate fields, and extraction provenance.

`paper` remains a node type for bibliographic provenance, features, and optional
literature graph tasks. Biological/pharmacological/disease-association imports
should prefer evidence records that support existing edge relations. A paper is
usually metadata/support for an edge or node claim; it should not become a
biological edge unless the task is explicitly a literature-index graph.

Canonical evidence files currently exist at:

- `evidence/cell_line_from_organism.parquet` — `1,183` human cell-line metadata support records.
- `evidence/disease_associated_gene.parquet` — gene→disease support records for the evidence-backed subset; the full edge file includes historical associations without complete evidence support.
- `evidence/disease_involves_pathway.parquet` — `2,296` pathway→disease Reactome support records.
- `evidence/gene_ortholog_gene.parquet` — `161,675` OpenTargets target.homologues support records.
- `evidence/molecule_targets_gene.parquet` — `41,239` molecule→gene target support records preserving OpenTargets MoA action metadata and source predicates.
- `evidence/mutation_affects_molecule_response.parquet` — `18,595` pharmacogenomics support records.
- `evidence/mutation_associated_disease.parquet` — `4,656,171` OpenTargets disease-facing variant support records across `eva`, `gwas_credible_sets`, `uniprot_variants`, and `eva_somatic`.
- `evidence/mutation_associated_gene.parquet` — `535,093` OpenTargets L2G support records preserving `studyLocusId` row-level support.
- `evidence/mutation_associated_phenotype.parquet` — `169,005` EVA/ClinVar-style support records for `164,406` HP-only mutation→phenotype association edges across all clinical-significance classes.
- `evidence/mutation_causes_protein_change.parquet` — `177,735` OpenTargets variant/protein-change support records.

Latest coverage audit after schema cleanup:
`.omoc/reports/schema-direction-update-coverage-20260619.json`.

### Storage Layer

- **LaminDB**: node registry, ontology resolution, artifact versioning
- **Parquet**: one file (or directory) per edge type; node feature tables
- **bionty**: ontology resolution for Gene, Disease, Pathway, CellType, etc.
- **pertdb**: management of perturbations, and molecules

### Graph Export

Target: **PyTorch Geometric `HeteroData`** (preferred over DGL for new work —
more actively maintained, better heterogeneous graph API, richer ecosystem). DGL
`DGLHeteroGraph` kept as fallback for backward compatibility with existing TxGNN
training code.

```python
# Desired API
from txgnn import KGLoader
kg = KGLoader(data_dir='./data')
hetero_data = kg.to_pyg()   # PyG HeteroData
hetero_dgl  = kg.to_dgl()   # DGL HeteroGraph fallback
```

---
