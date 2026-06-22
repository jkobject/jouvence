# Later node/edge families plan: organelles, complexes, ncRNA, PTMs

Status: planning only. Do not treat this document as an ingestion report; no new data was ingested for this card.

This plan follows `docs/txgnn_access_runbook.md`: canonical KG data lives at `gs://jouvencekb/kg/v2`, targeted source/Parquet inspection should use `.omoc/gcs-cache/kg-v2/{nodes,edges,evidence,raw}`, and workers should not wait on a missing FUSE mount. For this planning pass, source facts were checked from public pages/APIs plus existing repo docs; any future implementation card must re-run source-specific row counts against the exact release being ingested.

## Design decisions

1. Use source-native measurements and endpoint namespaces. Do not create protein, PTM, ncRNA, or complex relations by projecting from gene-level rows.
2. Keep graph relations broad and stable; put source-specific predicates, assay classes, confidence, score, context, and record IDs in `evidence/{relation}.parquet`.
3. Add new node types before edge files. These families require schema extension; none should be silently squeezed into `pathway` or `gene` because that would lose endpoint semantics.
4. Prefer context/evidence tables for composite/statistical predictions. miRNA/lncRNA predictions, PTM-disease text mining, and cell-context organelle observations should not become global mechanistic truth edges unless the source assertion supports that.
5. Use the existing protein endpoint policy: `protein` means direct protein/isoform evidence, preferably canonical Ensembl Protein (`ENSP...`) with UniProt accession as an xref. UniProt/neXtProt accessions must be resolved to existing `nodes/protein.parquet` IDs before promotion.

## Proposed new node types

| Proposed node type | Why this name | Primary namespace | Xrefs / key columns | Candidate sources | Licensing notes | Expected scale | Implementation stance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cellular_component` | Better than `organelle`: HPA values include organelles, membranes, cytosol, nuclear bodies, focal adhesions, secreted locations, etc. Use `display_category` to distinguish organelle/compartment/secreted/membrane/structure. | GO Cellular Component (`GO:...`) when mappable; HPA local ID fallback `HPA_SL:<slug>` for HPA-only labels. | `hpa_label`, `hpa_category`, `go_id`, `uniprot_sl_id`, `parent_id`, `name`, `description`. | Human Protein Atlas subcellular section; GO cellular component; UniProt subcellular location controlled vocabulary. | HPA page reports CC BY 4.0 for copyrightable database parts, with third-party constraints; GO is open/CC BY style via OBO Foundry; UniProtKB is CC BY 4.0. Verify exact release terms in implementation. | HPA `proteinatlas.tsv.zip` sampled in this run: 20,162 protein atlas rows and 59 location-like values in subcellular/secretome columns. GO CC is larger but only a mapped subset should enter core KG. | Add first. Use an explicit HPA→GO/UniProt-SL mapping file and keep HPA raw labels in evidence. |
| `protein_complex` | Directly represents stable molecular complexes; do not model complexes as pathways. | Complex Portal accession (`CPX-...`) for primary human curated complexes. | `complex_portal_id`, `corum_id`, `reactome_id`, `go_id`, `name`, `stoichiometry_json`, `organism_id`. | Complex Portal first; CORUM as optional second source; Reactome complexes for crossrefs/hierarchy; Hu.MAP/BioPlex only after license/quality review. | Complex Portal is an EMBL-EBI open data resource under EMBL-EBI terms; verify redistribution/citation. CORUM licensing is less automation-friendly and should be checked manually before redistributing derived files. | Complex Portal current human complextab was checked at `https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/9606.tsv`: 2,498 human complex rows; member count range 1–54, avg ~4.04. CORUM human adds thousands more but requires license gate. | Add after `cellular_component`. Use Complex Portal as clean first release; later reconcile CORUM/Reactome duplicates. |
| `mirna` | miRNAs are mature/precursor ncRNA entities with source-native identifiers and target assertions; should not be represented as genes unless the edge is explicitly gene/transcript-level. | miRBase mature ID/accession for mature miRNA (`MIMAT...`) plus precursor (`MI...`) as xref, or RNAcentral URS as future unifying ID. | `mirbase_mature_accession`, `mirbase_name`, `mirbase_precursor_accession`, `rnacentral_id`, `ensembl_gene_id`, `sequence`, `species`. | miRBase / miRCarta for node catalog; RNAcentral for crossrefs and license-friendly consolidation; miRTarBase for validated miRNA-target edges; TarBase/miRecords as optional. | RNAcentral states CC0 for all RNAcentral data. miRBase download terms must be checked for the release used. miRTarBase terms should be checked manually; site TLS was brittle from this worker. | Human mature miRNA catalog is ~2k-scale; miRCarta page exposes miRBase+predicted/integrated human miRNA sets and target integrations. Validated target edges are typically 10^5-scale, predicted targets 10^6–10^7 and should not be promoted blindly. | Add node catalog before target/disease edges. Keep predicted-target sources in feature/context tables unless experimentally supported or scored enough for evidence-backed edges. |
| `lncrna` | lncRNAs have transcript/gene identifiers but distinct noncoding-RNA assertions and interaction/disease resources. Keep a node type so lncRNA→protein/phenotype/disease is not hidden as generic gene→*. | Ensembl transcript (`ENST...`) or RNAcentral URS as primary; recommend RNAcentral URS only if mapping coverage to Ensembl is sufficient. | `ensembl_gene_id`, `ensembl_transcript_id`, `rnacentral_id`, `lncbook_id`, `gencode_id`, `gene_symbol`, `biotype`, `sequence_length`. | GENCODE/Ensembl for node catalog; RNAcentral for crossrefs; LncBook for human catalog/omics/interactions; LncRNA2Target for lncRNA-target regulation; LncRNADisease for disease associations; NPInter/ENCORI/starBase as optional interaction sources. | RNAcentral CC0. LncBook and LncRNADisease require terms check/citation; avoid commercial/restricted redistribution until verified. | LncBook 2.0 page checked in this run: 95,243 human lncRNA genes, 323,950 transcripts, 772,745 lncRNA-protein interactions, 146,092,274 lncRNA-miRNA interactions. LncRNADisease v3 page: 6,066 lncRNAs, 566 diseases, 13,191 experimentally supported lncRNA-disease associations. | Add after miRNA if RNAcentral/GENCODE mapping is clean. Treat massive predicted or text-mined interaction sets as evidence/features until support predicates are audited. |
| `ptm_site` | PTMs are not ordinary nodes like proteins; model specific modified residues/sites when they connect proteins to disease/phenotype or mechanistic evidence. | Composite ID: `UniProtKB:<accession>:<mod_type>:<position>` or `PTM:<source>:<record_id>`; map parent protein to ENSP. | `protein_id`, `uniprot_accession`, `residue`, `position`, `modification_type`, `psi_mod_id`, `evidence_level`, `isoform`, `sequence_context`. | UniProtKB features (`MOD_RES`, glycosylation, lipidation, disulfide, etc.); neXtProt annotations; PhosphoSitePlus optional but license-gated; SIGNOR/Reactome for PTM-mediated mechanisms. | UniProtKB license is CC BY 4.0. neXtProt page checked in this run says neXtProt has reached end of life and no longer updates, so use as a historical supplemental source only. PhosphoSitePlus is not open enough for redistribution without license review. | UniProt REST checked in this run: 20,431 reviewed human proteins; 9,491 reviewed human proteins with PTM features; 5,330 with disease comments; 3,338 with both. PTM site rows will be larger than protein count because each protein has multiple features. | Add only when a concrete disease/phenotype linkage is available; otherwise PTM annotations are protein feature tables rather than graph nodes. |

## Proposed relation additions

### Cellular component / organelle relations

| Proposed relation | Source → target | Candidate sources | Evidence fields | Licensing | Expected scale | Edge vs evidence/feature decision |
| --- | --- | --- | --- | --- | --- | --- |
| `cellular_component_subtype_of_cellular_component` | `cellular_component` → `cellular_component` | GO cellular component `is_a`/`part_of`; HPA subcellular hierarchy from subcellular pages; UniProt SL hierarchy if used. | `source_dataset`, `predicate` (`is_a`, `part_of`, `located_in`, HPA grouping), `source_record_id`, `release`, `mapping_confidence`. | GO/UniProt/HPA terms as above. | Dozens for HPA-only labels; hundreds/thousands if full GO CC is loaded. | Active ontological edge. Keep HPA grouping as evidence/mapping metadata if not strict ontology. |
| `protein_located_in_cellular_component` | `protein` → `cellular_component` | HPA `proteinatlas.tsv.zip` subcellular and secretome fields; UniProt subcellular location comments as secondary; neXtProt historical. | HPA: `subcellular_location`, `main_location`, `additional_location`, `secretome_location`, reliability/support, antibody/IF metadata if available, source release. UniProt: location, UniProt SL term, isoform qualifier, evidence codes, ECO/PMIDs. | HPA CC BY 4.0 with third-party caveat; UniProt CC BY 4.0. | HPA sample: <=20,162 rows with 59 distinct location-like labels; edge count likely tens of thousands after splitting multi-location fields. UniProt will add broader coverage but more text/qualifier handling. | Active broad edge with detailed evidence. Do not infer from GO CC pathway membership or protein keywords alone. |
| `cell_type_has_cellular_component_activity` or `cellular_component_observed_in_cell_type` | `cell_type` → `cellular_component` or reverse | HPA single-cell/subcellular context only if a source directly says a component is observed/enriched in a cell type; Cell Ontology/GO annotations if explicitly cell-contextual. | `cell_type_id`, `component_id`, assay/staining/source table, enrichment/score, tissue context, source record/release. | HPA/GO terms. | Unknown; likely much smaller than protein-location. | Do not add until a direct cell-type-context source is inspected. HPA protein cell-type staining supports `cell_type_expresses_protein`, not automatically component→cell type. Default to context feature table. |

Note on requested direction: the TODO says `organelle/compartment -> cell type`. For consistency with existing schema, entity-in-context edges usually use context/source first (`cell_type_expresses_gene`, `tissue_expresses_protein`) when the context is the measured sample. If the biological assertion is “component is present/enriched in cell type”, prefer `cell_type_has_cellular_component_activity` or `cell_type_contains_cellular_component`, but only after source inspection. Do not create a relation solely from general cell biology facts that every cell has mitochondria, nucleus, etc.

### Protein complexes

| Proposed relation | Source → target | Candidate sources | Evidence fields | Licensing | Expected scale | Edge vs evidence/feature decision |
| --- | --- | --- | --- | --- | --- | --- |
| `protein_part_of_protein_complex` | `protein` → `protein_complex` | Complex Portal `complextab/9606.tsv`; CORUM; Reactome complex participants. | complex accession/name, participant UniProt, stoichiometry, role, evidence code, experimental evidence, PMIDs, crossrefs, assembly, release. | Complex Portal / EMBL-EBI terms; CORUM license gate. | Complex Portal human checked: 2,498 complexes, avg ~4 members => about 10k participant rows before xref losses. | Active physical/membership edge. Direction protein→complex matches requested `protein -> protein complex`; evidence stores stoichiometry/support. |
| `protein_complex_part_of_protein_complex` | `protein_complex` → `protein_complex` | Complex Portal expanded participants / component complexes; Reactome complex hierarchy. | parent/child complex IDs, stoichiometry if child is a participant, evidence code, source record, release. | Same as above. | Probably hundreds to low thousands, source-dependent. | Active ontological/physical assembly edge only for explicit nested complex membership; not inferred from overlapping members. |
| `protein_complex_associated_disease` | `protein_complex` → `disease` | Complex Portal disease column/crossrefs; Reactome disease pathways; DisGeNET/UniProt disease evidence projected only if complex-level assertion exists. | disease source ID, disease namespace, predicate (`associated_with`, `causal_role`, `disease_complex_annotation`), PMIDs, evidence code, source record, mapping provenance. | Complex Portal / Reactome open; other disease DBs require terms review. | Likely sparse in Complex Portal; Reactome disease pathway involvement may be low thousands but often pathway-level, not complex-specific. | Broad disease association edge with evidence. Do not project member protein diseases to complex diseases by default; that belongs in a derived feature. |
| `protein_complex_associated_phenotype` | `protein_complex` → `phenotype` | GO/HPO direct complex annotations if available; model organism phenotype extrapolations only as evidence/context. | phenotype ID, source organism, evidence code, PMID, mapping/projection details. | HPO/GO open; model organism licenses vary. | Unknown/sparse. | Candidate only. Prefer feature/evidence until direct human complex→phenotype assertions are found. |

### PTM relations

| Proposed relation | Source → target | Candidate sources | Evidence fields | Licensing | Expected scale | Edge vs evidence/feature decision |
| --- | --- | --- | --- | --- | --- | --- |
| `protein_has_ptm_site` | `protein` → `ptm_site` | UniProtKB feature annotations; neXtProt historical; dbPTM/PhosphoSitePlus optional after license review. | protein accession/ENSP, isoform, residue/position, modification type, PSI-MOD, feature range, evidence code, PMIDs, source record, release. | UniProt CC BY 4.0; neXtProt historical/EOL; PhosphoSitePlus license gate. | UniProt REST: 9,491 reviewed human proteins with PTM features; site rows likely tens of thousands. | Active edge only if `ptm_site` node is adopted. Otherwise keep as protein feature table. |
| `ptm_site_associated_disease` | `ptm_site` → `disease` | UniProt disease comments linked to variants/PTM features only when positional assertion exists; neXtProt disease/variant/PTM annotations; ClinVar variant consequence + PTM overlap as contextual evidence. | disease ID, disease comment/source, PTM feature ID, variant/site linkage, effect, evidence code, PMID, mapping confidence. | UniProt CC BY 4.0; neXtProt EOL; ClinVar public domain-ish NCBI terms, verify. | Much smaller than PTM site catalog; likely thousands at most after requiring site-level linkage. | Broad edge with detailed evidence, but only if source links the PTM/site to disease. Do not connect every PTM on disease-associated proteins to disease. |
| `ptm_site_associated_phenotype` | `ptm_site` → `phenotype` | HPO/ClinVar/UniProt variants with PTM-site consequences; curated literature/mining only with explicit site-level evidence. | phenotype ID, source predicate, clinical significance/effect, position/site, evidence code, PMID, source record. | Source-specific. | Unknown/sparse. | Candidate. Prefer feature/context table unless explicit site→phenotype evidence exists. |

Requested wording was `protein -> PTM -> disease/phenotype`; the concrete schema should be `protein_has_ptm_site`, `ptm_site_associated_disease`, and `ptm_site_associated_phenotype`. PTM type (`phosphorylation`, `glycosylation`, etc.) is a node property or optional controlled-vocabulary xref, not the only identity of the site.

### ncRNA relations: miRNA and lncRNA

| Proposed relation | Source → target | Candidate sources | Evidence fields | Licensing | Expected scale | Edge vs evidence/feature decision |
| --- | --- | --- | --- | --- | --- | --- |
| `mirna_regulates_gene` | `mirna` → `gene` | miRTarBase validated MTIs; TarBase; miRCarta integrations; ENCORI/starBase/TargetScan only as predicted/context sources. | miRNA ID, target gene/transcript/protein source ID, assay type, support type (`strong`, `weak`, reporter/CLIP/qPCR), direction/effect if present, cell/tissue/disease context, PMID, source record, score. | miRTarBase/TarBase terms check; predicted DB licenses vary. | Validated human MTIs likely 10^5-scale; predicted edges can be 10^6+ and should not be promoted as core truth. | Active broad regulatory edge only for validated or curated target evidence. Predictions should be feature/context tables or evidence with `prediction_only=true`, not merged with validated assertions. |
| `mirna_regulates_transcript` | `mirna` → `transcript` | Sources with transcript/3'UTR isoform endpoints, CLIP/target-site resources. | transcript ID, target site coordinates, seed match, assay, score, context, PMID. | Source-specific. | Smaller than gene-level unless using predicted target-site compendia. | Candidate split when transcript-native endpoints exist; do not expand gene targets to all transcripts. |
| `mirna_associated_disease` | `mirna` → `disease` | HMDD, miR2Disease, miRCarta disease annotations, literature-curated sources. | disease ID/source, predicate, expression direction/up-down if present, sample context, score/curation level, PMID, source record. | HMDD/miR2Disease terms check. | 10^4–10^5-scale depending source/release. | Broad association edge with detailed evidence. Keep expression differential direction in evidence. |
| `mirna_associated_phenotype` | `mirna` → `phenotype` | HPO/Monarch/experimental phenotype resources if direct; disease-to-phenotype expansion is not sufficient. | phenotype ID, source predicate, experimental context, organism, PMID, mapping provenance. | Source-specific. | Unknown/sparse. | Candidate; do not infer from miRNA→disease plus disease→phenotype. |
| `lncrna_interacts_protein` | `lncrna` → `protein` | LncBook protein interactions; NPInter; ENCORI/starBase; eCLIP/RBP resources if lncRNA transcript IDs are retained. | lncRNA ID/transcript, protein accession/ENSP, assay, interaction type, cell/tissue context, score/confidence, PMID, source record. | LncBook/NPInter/ENCORI terms check; ENCODE-derived eCLIP is generally open but requires release attribution. | LncBook page checked: 772,745 lncRNA-protein interactions. | Active physical/regulatory edge if interaction source is experimental/curated; predicted-only sets go to feature/context. |
| `lncrna_regulates_gene` | `lncrna` → `gene` | LncRNA2Target, LncBook, NPInter, literature-curated perturbation resources. | target gene, regulation direction/effect, assay/perturbation, cell/tissue context, PMID, score/source record. | Terms check; LncRNA2Target site was unreachable from this worker. | 10^4–10^5-scale depending source. | Broad regulatory edge with detailed evidence. Do not use coexpression alone as regulation. |
| `lncrna_associated_disease` | `lncrna` → `disease` | LncRNADisease v3; Lnc2Cancer; LncBook disease annotations. | disease ID/source, predicate, expression direction/effect, sample context, evidence type, PMID, source record. | Terms check/citation. | LncRNADisease v3 page checked: 13,191 experimentally supported lncRNA-disease associations across 6,066 lncRNAs and 566 diseases. | Broad disease association edge with evidence. |
| `lncrna_associated_phenotype` | `lncrna` → `phenotype` | HPO/Monarch/direct phenotype curation if present. | phenotype ID, predicate, organism/context, PMID/source record, mapping provenance. | Source-specific. | Unknown/sparse. | Candidate; do not infer from lncRNA→disease plus disease→phenotype. |

### Paralogy

| Proposed relation | Source → target | Candidate sources | Evidence fields | Licensing | Expected scale | Edge vs evidence/feature decision |
| --- | --- | --- | --- | --- | --- | --- |
| `gene_paralog_gene` | `gene` → `gene` | OpenTargets target `homologues` nested field; Ensembl Compara BioMart/homology dump. | `homology_type`, species IDs/names for both endpoints, percent identity for query/target, confidence, target gene symbol, method/source release, source record. | OpenTargets/Ensembl terms; already used in current KG for genes/proteins. | Existing `gene_ortholog_gene` has 161,675 rows. Human within-species paralogs should be much smaller than cross-species orthology, likely 10^4–10^5 depending inclusion of one-to-many/other paralogs. | Active genetic edge. Keep direction as source row order, but treat as symmetric/undirected for graph export if both endpoints are human genes. |

Implementation note: existing notebook samples show OpenTargets target records include `homologues` entries such as `homologyType: within_species_paralog` and `other_paralog`. The GCS scratch path `gs://jouvencekb/kg/scratch/opentargets-26.03/target/` was not present during this planning run, so the implementation card should copy the exact OpenTargets target Parquet shards into `.omoc/gcs-cache/kg-v2/raw/opentargets-target/` and count `homologyType` values before building.

## Source priority by family

| Family | First source | Second source | Defer / caution |
| --- | --- | --- | --- |
| Cellular component nodes + protein localization | HPA `proteinatlas.tsv.zip` subcellular/secretome fields + HPA hierarchy page | UniProt subcellular location comments / UniProt SL mapping | Do not use GO CC pathway membership as direct protein localization without evidence. |
| Cell component hierarchy | GO CC `is_a`/`part_of` + mapped HPA labels | UniProt SL hierarchy | HPA visual groupings may be display categories, not ontology edges. |
| Protein complexes | Complex Portal human complextab | Reactome complex crossrefs, CORUM after license review | Do not infer complexes from pairwise PPIs. |
| PTMs | UniProtKB reviewed human features | neXtProt historical; Reactome/SIGNOR mechanisms | PhosphoSitePlus/dbPTM require license gates before redistribution. |
| miRNA nodes/targets | miRBase/RNAcentral for nodes; miRTarBase for validated targets | TarBase/miRCarta integrations | Predicted targets should be features/context, not default edges. |
| lncRNA nodes/interactions/disease | GENCODE/RNAcentral for nodes; LncRNADisease and LncBook for first disease/interaction audit | NPInter, LncRNA2Target, ENCORI/starBase | Massive predicted lncRNA-miRNA/protein sets need support filtering and license review. |
| Paralogy | OpenTargets target `homologues`; Ensembl Compara | HGNC gene family metadata as features | Do not mix orthology/paralogy under one relation; preserve homology type. |

## Phased implementation cards

These are proposed cards, not executed in this planning card.

### Phase L2-A: schema extension only

1. Add candidate node types and schema docs for `cellular_component`, `protein_complex`, `mirna`, `lncrna`, and `ptm_site`.
2. Add candidate relations in `CANDIDATE_RELATIONS` first, not active `RELATIONS`, unless source/endpoint policy is already fully decided.
3. Update `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, and tests that enumerate node/relation names.
4. Acceptance: schema compiles, docs explain primary namespaces/xrefs, no Parquet files expected.

### Phase L2-B: HPA cellular component pilot

1. Copy only HPA `proteinatlas.tsv.zip` or a release-pinned raw file into `.omoc/gcs-cache/kg-v2/raw/hpa-<release>/`.
2. Build `nodes/cellular_component.parquet` from HPA labels mapped to GO CC/UniProt SL where possible.
3. Build `edges/protein_located_in_cellular_component.parquet` and evidence from HPA subcellular/secretome fields after resolving UniProt/gene rows to ENSP protein IDs.
4. Add `cellular_component_subtype_of_cellular_component` only for explicit GO/HPA hierarchy mappings.
5. Acceptance: endpoint anti-joins pass; evidence supports all protein-location edges; docs and coverage updated.

### Phase L2-C: Complex Portal first release

1. Cache `https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/9606.tsv` under `.omoc/gcs-cache/kg-v2/raw/complex-portal/`.
2. Build `nodes/protein_complex.parquet` using Complex Portal IDs.
3. Build `protein_part_of_protein_complex` evidence with stoichiometry, ECO evidence, PMIDs, crossrefs, and release.
4. Add nested `protein_complex_part_of_protein_complex` only if participant rows explicitly name child complexes.
5. Defer complex→disease/phenotype unless Complex Portal disease column has resolvable disease/phenotype endpoints.
6. Acceptance: UniProt→ENSP mapping audited; no projected member-protein disease assertions.

### Phase L2-D: UniProt PTM feature pilot

1. Query/download reviewed human UniProtKB entries with PTM features and disease comments.
2. Decide whether `ptm_site` is a graph node or whether PTMs stay as `features/protein_ptm_site.parquet` until site-level disease/phenotype evidence is found.
3. If graph nodes are justified, build `protein_has_ptm_site` first.
4. Build `ptm_site_associated_disease` / `ptm_site_associated_phenotype` only from explicit site-level disease/phenotype evidence.
5. Acceptance: no disease edges from generic “protein has disease + protein has PTM” joins.

### Phase L2-E: miRNA node + validated target pilot

1. Build `nodes/mirna.parquet` from miRBase/RNAcentral with mature and precursor IDs preserved.
2. Audit miRTarBase/TarBase license and download format; enumerate support types and species counts before building.
3. Build `mirna_regulates_gene` for validated human MTIs, preserving assay/support/PMID/context.
4. Add `mirna_regulates_transcript` only if the source has transcript/site endpoints.
5. Defer disease/phenotype until HMDD/miR2Disease terms and mapping to EFO/HPO are checked.

### Phase L2-F: lncRNA node + disease/interaction pilot

1. Build `nodes/lncrna.parquet` from GENCODE/RNAcentral with Ensembl transcript/gene and RNAcentral IDs.
2. Audit LncRNADisease v3 terms and map disease names/IDs to existing `disease` nodes.
3. Build `lncrna_associated_disease` from experimentally supported rows, preserving expression/evidence/PMID fields.
4. Separately audit LncBook lncRNA-protein interactions and decide whether support fields justify `lncrna_interacts_protein` or a context feature table.
5. Defer phenotype edges unless a direct phenotype source is found.

### Phase L2-G: paralog relation from OpenTargets/Ensembl

1. Copy OpenTargets target Parquet shards or Ensembl Compara homology dump into repo-local raw cache.
2. Count `homologyType`, species, and confidence values; filter human→human paralogs only.
3. Build `gene_paralog_gene` with evidence rows preserving the full homology metadata.
4. Decide graph export symmetry policy: store source row direction, optionally add reverse edges at export time.
5. Acceptance: no cross-species ortholog rows leak into `gene_paralog_gene`; no duplicate mirror-edge inflation unless explicitly chosen.

## Validation checklist for every later-family card

- Check source license and citation before copying data into canonical or distributable locations.
- Cache only targeted source files under `.omoc/gcs-cache/kg-v2/raw/<source-release>/`.
- Inspect raw schema and sample rows before naming relations.
- Resolve endpoints against existing node Parquets; for new node types, build nodes before edges.
- Materialize evidence at the same time as each non-ontology/non-derived edge file.
- Run endpoint anti-join validation and `manage_db.audit_edge_evidence` where applicable.
- Update `manage_db/kg_schema.py`, `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, coverage reports, and tests in the same implementation tranche.
- Keep restricted or prediction-only sources as features/context tables unless their terms and evidence semantics justify canonical graph edges.
