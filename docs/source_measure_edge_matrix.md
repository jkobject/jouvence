# Source → measurement → edge policy

This document defines how source assertions map to active KG relations. Relation names follow the native endpoint and biological assertion. Evidence-specific nuance stays in `evidence/{relation}.parquet`.

## Core rules

1. Do not project RNA/gene-level rows into protein relations.
2. Use protein relations only when the source directly identifies protein/isoform endpoints or direct protein measurements.
3. Use broad graph relations with rich evidence metadata instead of splitting relation names by every predicate.
4. Keep molecule “interaction” wording for physical molecular interactions; drug-combination effect rows use synergy/effect wording.
5. Do not create placeholder Parquets for relations without source-backed rows.
6. For complexes, PTMs, TF binding, miRNA IDs, and transcript isoforms, follow `docs/source_native_expansion_policy.md` before any source ingestion.
7. Expression coexpression/correlation and disease-association-only scores are non-causal feature/context records by default (`features/*.parquet` via `manage_db.kg_feature_context`), not canonical KG mechanism edges; see `docs/proposals/expression_correlation_feature_context_policy.md`.

## OpenTargets / external source mapping

| Source dataset | Native assertion | Native endpoints | Active relation(s) | Required evidence metadata |
| --- | --- | --- | --- | --- |
| `drug_mechanism_of_action` | molecule has target/mechanism/action against a target | ChEMBL molecule; OpenTargets/Ensembl target gene unless a protein endpoint is explicitly provided | `molecule_targets_gene`; `molecule_targets_protein` only for direct protein/isoform endpoints | action type, mechanism label, source record, target ID namespace |
| `interaction`, `interaction_evidence` | target/gene-product molecular or functional interaction | Ensembl/NCBI gene targets for gene-level rows; UniProt/protein rows only when retained as typed protein endpoints | `gene_interacts_gene`; no Block 1 split from current canonical OpenTargets gene endpoints; `protein_interacts_protein` only for future source-native protein endpoints | source database/channel, interaction type, direction/sign if present, score, detection method, PMID/source IDs; product IDs in metadata are not sufficient to project gene rows into protein relations |
| `expression` RNA fields | baseline RNA expression in tissue/cell type | ENSG gene; UBERON/CL context | `tissue_expresses_gene`, `cell_type_expresses_gene` | TPM/value, expression level, source tissue/cell type |
| Human Protein Atlas direct protein files | tissue/cell protein staining or abundance | protein/antibody/gene-product target; tissue/cell context | `tissue_expresses_protein`, `cell_type_expresses_protein` when endpoint policy is explicit | protein level, reliability, antibody/protein target, cell-type staining, tissue |
| DepMap / Project Score / target essentiality | gene expression, dependency, or perturbation in cell lines | ENSG gene; Cellosaurus/model ID | `cell_line_expresses_gene`, `cell_line_gene_essentiality`; `cell_line_expresses_protein` only for direct proteomics | expression/dependency/effect score, screen/study, cell line, threshold |
| Reactome / GO gene membership | pathway contains or annotates a gene | pathway/GO/Reactome; ENSG/NCBI gene | `pathway_contains_gene` | evidence code/aspect/source, source subdatabase (`go`, `txgnn_legacy_go`, `txgnn_legacy_reactome`), pathway ID, gene ID, source record ID; staged backfill covers 630,932/630,932 current edges |
| Protein-native pathway/complex source | pathway/complex contains a protein | pathway/complex; protein/isoform | `pathway_contains_protein` | source complex/pathway record, protein ID, membership evidence. Reactome `UniProt2Reactome_All_Levels` staged pilot: 15,436 edges / 18,068 evidence rows, release `2026-03-23`, accepts only direct UniProt endpoints mapped unambiguously to KG protein nodes; see `docs/reactome_pathway_contains_protein_staged_pilot.md`. |
| ENCODE-rE2G `enhancer_to_gene` | composite model prediction enhancer→gene in biosample context | enhancer interval; ENSG gene; biosample/tissue/cell type | `enhancer_regulates_gene` | rE2G score, biosample ID/name, DNase score, Hi-C/contact score, distance-to-TSS, study/file ID, QC flags |
| EVA/ClinVar HPO rows | variant has clinical-significance assertion for an HPO abnormality | mutation; HP phenotype | `mutation_associated_phenotype` | clinical significance predicate, source row, score, allele origin, PMIDs, release |
| GWAS/L2G/variant disease evidence | mutation associated with disease/trait | mutation; disease/EFO/MONDO/etc. | `mutation_associated_disease`, `mutation_associated_gene` | predicate, study locus, score, p-value/effect if available, source dataset |
| Pharmacogenomics | mutation affects molecule response | mutation; molecule | `mutation_affects_molecule_response` | drug response predicate, source record, score/effect |
| OpenTargets `clinical_indication` | positive drug clinical indication / trial stage for a disease | ChEMBL molecule; EFO/MONDO disease | evidence for existing `molecule_treats_disease` only; do not reuse for `molecule_contraindicates_disease` | clinical indication ID, max clinical stage/status, clinical report IDs, NCT IDs, source release, mapping provenance |
| OpenTargets `drug_warning` | safety warning / withdrawal / toxicity class, not a clean contraindication assertion | ChEMBL molecule; EFO warning/adverse-effect class when present | candidate source for safety phenotype/warning modeling only; no evidence for `molecule_contraindicates_disease` without a contraindication-specific predicate | warning ID/type, toxicity class, country/year, DailyMed/FDA references, EFO warning class |
| SIDER / adverse-effect source | molecule associated with phenotype/adverse effect | molecule; phenotype/MedDRA/HPO/UMLS mapping | `molecule_associated_phenotype` | predicate, side-effect term/source ID, mapping provenance |
| Drug-combination effect source | molecule pair has synergy/interaction-effect evidence | molecule; molecule | `molecule_synergizes_molecule` | interaction/effect label, score if present, source record |
| Chemical hierarchy source | parent-child molecule relation | molecule; molecule | `molecule_parent_of_molecule` | source hierarchy record, predicate |
| Disease-gene source | gene associated/directed toward disease | gene; disease | `disease_associated_gene` | predicate, score, source database, PMIDs/study IDs |
| Protein-native disease source | protein associated/directed toward disease from protein-specific evidence | protein; disease | `disease_associated_protein` | protein endpoint, measurement/predicate, score, source record |
| HPO / gene phenotype source | gene associated with phenotype | gene; phenotype | `gene_associated_phenotype` | predicate, evidence source, PMIDs/curation IDs |

## Active cleanup result

The active KG has normalized existing wrong-endpoint or reverse-direction rows into their target relations:

- `gene_interacts_gene`
- `pathway_contains_gene`
- `molecule_targets_gene`
- `disease_associated_gene`
- `molecule_associated_phenotype`
- `gene_associated_phenotype`
- `tissue_expresses_gene`
- `molecule_synergizes_molecule`
- `molecule_parent_of_molecule`

Protein relations remain in the schema for future direct protein evidence, but the current active KG no longer uses protein relation names for gene-endpoint rows.

### Block 1 split policy additions — 2026-06-20

| Source/native assertion | Endpoint policy | Canonical relation | Evidence detail to preserve |
| --- | --- | --- | --- |
| TF regulates target gene expression | TF as gene/gene product, target as gene | `tf_regulates_gene` | source database, regulator/target roles, sign/effect, direction, assay, score, PMID/source record, release |
| TF binds enhancer/regulatory interval | TF as gene/gene product, regulatory interval as enhancer | `tf_binds_enhancer` | assay/cell context, interval coordinates, peak/QC fields, source database, score, PMID/source record, release |
| RNA/transcript binds protein | transcript/RNA endpoint and protein/isoform endpoint | `transcript_interacts_protein` | assay/method, molecule roles, source database, score, PMID/source record, release |
| transcript/RNA regulates or interacts with gene | transcript/RNA endpoint and gene endpoint | `transcript_interacts_gene` | mechanism, direction, sign/effect, source database, score, PMID/source record, release |
| protein-native pathway membership | pathway and protein/isoform endpoints | `pathway_contains_protein` | source subdatabase, membership type, pathway version, evidence code, PMID/source record, release |
| protein-native drug target | molecule and protein/isoform endpoints | `molecule_targets_protein` | mechanism/action type, target class, source database, score/confidence, source record, release |

### Block 1 `gene_interacts_gene` audit outcome — 2026-06-21

The current canonical OpenTargets `gene_interacts_gene` relation remains broad. Its graph endpoints are gene-level (`ENSG`↔`ENSG`), while product identifiers and roles are evidence metadata inside `text_span`/`source_record_id`. Do not build `protein_interacts_protein`, `tf_regulates_gene`, `tf_binds_enhancer`, `transcript_interacts_protein`, or `transcript_interacts_gene` from this canonical relation. Those relations stay schema-valid for future source-native builders only, after raw endpoint policy, anti-join validation, and evidence support checks.

### Block 1 D1 validation outcome — 2026-06-22

Validation report: `docs/block1_validation_report.md`.

The accepted Block 1 compendium decisions are:

| Relation / source family | Decision | Validated evidence/source detail |
| --- | --- | --- |
| `gene_interacts_gene` from current canonical OpenTargets/TxGNN gene endpoints | Keep broad/no-split; no approved active `protein_interacts_protein`, `tf_regulates_gene`, `tf_binds_enhancer`, `transcript_interacts_protein`, or `transcript_interacts_gene` artifact from these rows. | `7,424,037` edges; `14,336,594` OpenTargets/interaction evidence rows; `642,150` TxGNN legacy broad edges remain a policy-accepted no-fabricated-evidence exception. |
| `pathway_contains_gene` from GO/Reactome/TxGNN legacy pathway membership | Keep current gene-level canonical relation; no `pathway_contains_protein` split promoted from current gene endpoints. | `630,932` edges / `630,932` evidence rows; source datasets `OpenTargets/go`, `TxGNN/txgnn_legacy_go`, `TxGNN/txgnn_legacy_reactome`; zero endpoint anti-join misses in D1 cache. |
| `molecule_targets_gene` from OpenTargets MoA and TxGNN DrugBank/CTD target rows | Keep current gene-level canonical relation; no `molecule_targets_protein` split promoted from these rows. | `41,239` edges / `41,239` evidence rows; source datasets `drug_protein`, `drug_mechanism_of_action`, `ctd_chemical_gene`; stale `molecule_targets_protein` predicate/direction/source-record tokens are zero. |

D1 used `.omoc/gcs-cache/kg-v2`, a partial local validation cache. The missing-file list in `.omoc/reports/block1-validation-coverage-20260622.json` is a cache-completeness limitation, not a canonical source-policy decision. Whole-KG coverage must be rerun against mounted `/mnt/gcs/jouvencekb/kg/v2` or a complete mirror.

### S1 source-native expansion policy additions — 2026-06-21

These policy decisions override earlier proposal-only wording until a later human-approved schema migration changes them:

| Source/native assertion | Endpoint policy | Canonical relation or node handling | Evidence detail to preserve |
| --- | --- | --- | --- |
| Source-native protein complex record or membership | protein/isoform endpoints plus named source complex identity | add planned `protein_complex` nodes; membership relation naming still pending (`protein_part_of_complex` / complex component relation) | source complex ID/name, protein IDs/namespaces, stoichiometry, expansion method, organism, assay/method, PMIDs, source dataset/release |
| Site-level PTM assertion | modified protein/isoform plus residue/site; enzyme/substrate roles only if source-native | planned `ptm_site` / structured PTM event modeling; may support `protein_regulates_protein` only when direction/roles/mechanism are explicit | modification type, residue, position, enzyme/regulator, substrate, direction/effect, method, context, PMID, source record/release |
| Vague PTM mention without site or role clarity | protein/gene/product as reported by source | evidence/edge-level metadata only; do not create PTM site nodes | PTM label, source predicate, endpoint namespace, confidence, PMID/source record |
| ReMap/ChIP-like TF binding peak overlapping enhancer | TF gene/gene-product and enhancer/regulatory interval | `tf_binds_enhancer`; ReMap preferred first source | evidence type (`observed_chip_like`), TF/antigen, coordinates, genome build, enhancer-overlap rule, biosample/context, peak/QC score, accession/PMID, source release |
| Motif support for TF binding | TF motif and enhancer/regulatory interval | supporting/candidate evidence for `tf_binds_enhancer`; motif-only is predicted support, not observed binding | evidence type (`motif_predicted`), motif database/model, score/threshold, strand, scan method, genome build, context if any |
| TF→target gene regulation | TF and target gene | do not populate `tf_regulates_gene` for now; wait for stricter future policy | if revisited later: source/subdataset identity, direction, sign/effect, assay, confidence, PMID/source record |
| Existing ENST transcript identity | existing `transcript` node | reuse existing transcript nodes; do not create or choose a “main transcript” | source transcript ID, isoform mapping, transcript biotype, source claim/release |
| miRBase/hsa-miR identity with true 1:1 ENST transcript mapping | existing transcript plus miRBase aliases/xrefs | add alias/xref or mapping table to existing `transcript` node | miRBase accession/name (`MI...`, `MIMAT...`, `hsa-miR-*`), mapping method, maturity, source/release |
| Distinct mature/precursor miRNA entity not identical to existing ENST transcript | miRBase mature/precursor entity | create future miR-primary nodes only after schema finalization (`mature_mirna`, `mirna_precursor` candidate labels) | maturity/processing level, precursor→mature relation evidence, source IDs/namespaces, release |
| miRNA target source with gene-level measurement | miRNA/miR entity and gene target | gene-level miRNA target relation once approved (`mirna_targets_gene` / `mirna_regulates_gene` naming); do not force transcript endpoints | assay/support class, target gene ID, effect/readout, context, PMID, source record/release |
| miRNA target source with transcript/UTR/site-level endpoint | miRNA/miR entity and transcript/UTR endpoint | `mirna_targets_transcript` when transcript endpoint is source-native or validated | transcript/UTR/site ID, binding site, assay/support class, context, score, PMID, source record/release |
| ABC/rE2G, motif scans, coexpression/correlation, disease-association-only modules | source-native endpoints and context | allowed non-causal exceptions only when explicitly typed as predictive/correlative/association/candidate/context-specific evidence | evidence type, score/effect size, model/features, tissue/cell/biosample/disease context, dataset, source record/release |
