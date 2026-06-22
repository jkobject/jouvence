# BioGRID category audit: physical interactions, complexes, PTMs, and genetic interactions

Date: 2026-06-21
Task: `t_0aad9e87`
Scope: source audit only; no data ingestion or canonical KG promotion.

## Executive recommendation

BioGRID is useful, but it is not one homogeneous protein mechanism source. Treat its release files as four separate source-native families:

1. `protein_interacts_protein` candidate evidence from physical interaction rows only, with protein endpoints required from source-provided protein accessions (`SWISS-PROT`, `TREMBL`, or `REFSEQ`) rather than projected gene IDs.
2. Complex-like physical evidence from complex/co-purification/reconstituted-complex assays should not create `protein_complex` nodes by itself. BioGRID standard downloads expose binary interaction/evidence rows and assay labels, not stable complex records with complex IDs/names/membership/stoichiometry. Use these rows as physical interaction/complex-association evidence, or create `protein_complex` nodes only after an explicit complex source with stable complex identifiers is approved.
3. PTM data from `BIOGRID-PTMS-*.ptm.zip` should become site-level `ptm_site` / structured PTM-event nodes when residue+position+sequence/reference support is present; PTMREL rows can support kinase/phosphatase or regulatory event evidence. Do not flatten site-level PTMs into generic undirected PPI.
4. Genetic interaction rows are not protein mechanism edges. Keep them out of `protein_interacts_protein`; if useful later, model them as a separate genetic/perturbation relation family with gene/allele/perturbation endpoints and phenotype/effect metadata.

## Official downloads and API access audited

Current release observed from the public BioGRID download page:

- Release root: `https://downloads.thebiogrid.org/BioGRID/Release-Archive/BIOGRID-5.0.258/`
- Latest-release alias also exists: `https://downloads.thebiogrid.org/BioGRID/Latest-Release/`
- License file: `https://biogrid-downloads.nyc3.digitaloceanspaces.com/LICENSE.txt`

Relevant release files:

| File | Role | Notes |
|---|---|---|
| `BIOGRID-ALL-5.0.258.tab3.zip` | All interaction/evidence rows in BioGRID TAB 3.0 | General source for complete physical+genetic interaction audit. Download attempt hit a temporary HTTP 429 after other large downloads; schema is identical to sampled `SYSTEM`/`MV` TAB3 headers and documented in BioGRID TAB 3.0 wiki. |
| `BIOGRID-SYSTEM-5.0.258.tab3.zip` | Same interaction rows split by `Experimental System` | Best audit file for category gating; sampled locally. Contains 31 system-specific TAB3 files. |
| `BIOGRID-MV-Physical-5.0.258.tab3.zip` | Multi-validated physical subset | Good stricter first-pass candidate for physical PPI evidence. Sampled locally; 552,689 rows in release 5.0.258. |
| `BIOGRID-PTMS-5.0.258.ptm.zip` | PTMTAB + PTMREL post-translational modification data | Site/event-specific PTM family. Sampled locally; 1,128,339 PTMTAB rows and 73,388 PTMREL rows. |
| `BIOGRID-IDENTIFIERS-5.0.258.tab.zip` | Identifier mapping/support | Useful for endpoint mapping audits; do not use to project gene-level rows into proteins without source-native protein support. |
| `BIOGRID-ORGANISM-5.0.258.{tab3,mitab,psi25}.zip` | Interactions split by organism | Useful for human-only staging after category gates. |
| `BIOGRID-PROJECT-*.zip` | Project-focused bundles | May contain interactions/PTMs/chemical interactions for special projects (e.g. UPS project), but should be treated as project subsets, not new relation semantics. |
| `BIOGRID-CHEMICALS-5.0.258.chemtab.zip` | Chemical interaction data | Out of scope for this physical/complex/PTM audit. |

REST service:

- Base: `https://webservice.thebiogrid.org/`
- WADL: `https://webservice.thebiogrid.org/application.wadl`
- Single interaction: `/interactions/<INT ID>?accesskey=[ACCESSKEY]`
- Multiple interactions: `/interactions/?accesskey=[ACCESSKEY]`, documented as returning the first 10,000 interactions by default with filters.
- Supported organisms: `/organisms/?accesskey=[ACCESSKEY]&format=json`
- Supported identifier types: `/identifiers/?accesskey=[ACCESSKEY]&format=json`
- Constraint: the REST service requires a unique access key included as `accesskey=[ACCESSKEY]`; bulk release files are the better route for reproducible KG builds.

License/access:

- BioGRID downloads are distributed under the MIT License. The release license permits use, copy, modification, merge, publish, distribute, sublicense, and sale, provided the copyright and permission notice are included in substantial portions.
- Keep the BioGRID release version and license URL in evidence metadata and downstream build manifests.
- Cite BioGRID and original publications in documentation/output where relevant.
- Practical access caveat: large public downloads may rate-limit (`HTTP 429`) during repeated automated pulls; builder tasks should cache by release and avoid repeated full downloads.

## TAB3 interaction schema audited

BioGRID TAB3 files are tab-delimited; the first line is a `#` header. The sampled `SYSTEM` and `MV-Physical` files share this 37-column header:

- `BioGRID Interaction ID`
- `Entrez Gene Interactor A`, `Entrez Gene Interactor B`
- `BioGRID ID Interactor A`, `BioGRID ID Interactor B`
- `Systematic Name Interactor A`, `Systematic Name Interactor B`
- `Official Symbol Interactor A`, `Official Symbol Interactor B`
- `Synonyms Interactor A`, `Synonyms Interactor B`
- `Experimental System`
- `Experimental System Type` (`physical` or `genetic`)
- `Author`
- `Publication Source` (e.g. `PUBMED:9006895`)
- `Organism ID Interactor A`, `Organism ID Interactor B`
- `Throughput` (`High Throughput`, `Low Throughput`, or both)
- `Score`
- `Modification`
- `Qualifications`
- `Tags`
- `Source Database`
- `SWISS-PROT Accessions Interactor A`, `TREMBL Accessions Interactor A`, `REFSEQ Accessions Interactor A`
- `SWISS-PROT Accessions Interactor B`, `TREMBL Accessions Interactor B`, `REFSEQ Accessions Interactor B`
- `Ontology Term IDs`, `Ontology Term Names`, `Ontology Term Categories`
- `Ontology Term Qualifier IDs`, `Ontology Term Qualifier Names`, `Ontology Term Types`
- `Organism Name Interactor A`, `Organism Name Interactor B`

Source-native endpoint policy:

- BioGRID rows are fundamentally interaction/evidence rows over BioGRID IDs, Entrez Gene IDs, symbols, organism IDs, and optional protein accessions.
- For `protein_interacts_protein`, require both endpoints to have source-provided protein product identifiers (`SWISS-PROT`, `TREMBL`, or acceptable RefSeq protein accessions) and map those to canonical protein/isoform nodes. Preserve Entrez/BioGRID IDs in evidence.
- Rows with only Entrez/BioGRID gene identifiers should remain gene-level or evidence-only. Do not convert them to protein edges through general gene→protein projection.
- Cross-species rows should be allowed only if cross-species protein interactions are explicitly wanted; otherwise gate to taxon pairs (e.g. human-human) before staging.

## Category audit

### 1. Physical protein/protein interactions -> candidate `protein_interacts_protein`

Primary files:

- `BIOGRID-MV-Physical-5.0.258.tab3.zip` for a conservative first build.
- `BIOGRID-SYSTEM-5.0.258.tab3.zip` filtered to `Experimental System Type == physical` for full physical evidence.
- `BIOGRID-ALL-5.0.258.tab3.zip` may be used after the same filters; it is not category-specific.

Observed release 5.0.258 counts from `SYSTEM` split:

- physical rows: 2,012,381
- genetic rows: 887,862
- throughput: 2,412,468 high-throughput; 474,295 low-throughput; 13,480 both
- `BIOGRID-MV-Physical`: 552,689 rows

Physical experimental systems present in `SYSTEM` split include:

- Direct/binary-ish physical evidence: `Two-hybrid`, `FRET`, `PCA`, `Co-crystal Structure`, `Far Western`, `Cross-Linking-MS (XL-MS)`, `Surface Display`, `Thermal Shift Assay`.
- Affinity/proximity/co-complex evidence: `Affinity Capture-MS`, `Affinity Capture-Western`, `Affinity Capture-Luminescence`, `Co-purification`, `Co-fractionation`, `Co-localization`, `Proximity Label-MS`, `Reconstituted Complex`.
- Non-protein endpoint or special physical evidence: `Protein-RNA`, `Affinity Capture-RNA`, `Protein-peptide`.
- Biochemical/PTM-like physical evidence: `Biochemical Activity`, with non-empty `Modification` values.

Recommended `protein_interacts_protein` gate:

- `Experimental System Type == physical`.
- Both endpoints have source protein support in `SWISS-PROT`, `TREMBL`, or `REFSEQ` fields and resolve to canonical protein/isoform nodes.
- Exclude `Protein-RNA` and `Affinity Capture-RNA` from protein-protein edges unless endpoint typing proves both endpoints are proteins, which the system name itself argues against for many rows.
- Preserve the exact `Experimental System`, `Throughput`, `Score`, `Modification`, `Qualifications`, ontology fields, BioGRID interaction ID, source database, author, publication source, organism IDs/names, and all source endpoint identifiers in evidence.
- Consider a confidence/evidence-class field rather than separate relation names: e.g. `binary_physical`, `complex_association`, `proximity_or_colocalization`, `biochemical_activity`.

Evidence columns for `evidence/protein_interacts_protein`:

- graph edge ID/source-target canonical protein IDs
- `source_dataset = biogrid`
- `source_release = BIOGRID-5.0.258`
- `source_file`
- `biogrid_interaction_id`
- `experimental_system`
- `experimental_system_type`
- `evidence_class`
- `publication_source`, parsed `pmid` when `PUBMED:*`
- `author`
- `throughput`
- `score`
- `modification`
- `qualifications`
- `tags`
- `source_database`
- all A/B source identifiers: Entrez, BioGRID ID, symbol, systematic name, synonyms, Swiss-Prot, TrEMBL, RefSeq, organism ID/name
- ontology term IDs/names/categories/qualifiers/types
- optional `is_multi_validated` when sourced from or matching `BIOGRID-MV-Physical`

### 2. Protein complexes -> do not infer `protein_complex` nodes from BioGRID TAB3 alone

BioGRID documentation explicitly warns that “interaction” includes direct physical binding, co-existence in a stable complex, and genetic interaction. The standard release files audited here encode binary interaction/evidence rows plus experimental systems, not stable complex entities.

Complex-like BioGRID evidence observed:

- `Reconstituted Complex`: 70,644 physical rows in `SYSTEM` split.
- `Co-purification`: 8,683 rows.
- `Co-fractionation`: 154,911 rows.
- `Affinity Capture-MS`: 979,110 rows.
- `Co-localization`: 10,096 rows.
- `Proximity Label-MS`: 232,009 rows.

These rows can support physical association/co-complex evidence, but they do not provide canonical complex IDs, complex names, membership lists, or stoichiometry columns in TAB3. The fields available are the same binary A/B interactor fields plus assay/provenance metadata.

Recommendation:

- Do not build `protein_complex` nodes or `protein_part_of_complex` membership edges directly from BioGRID TAB3/MV rows.
- If complex nodes are desired, use an explicit complex source (e.g. CORUM/Complex Portal/Reactome complex records/SIGNOR complex membership) that has stable complex identifiers and membership semantics, then optionally attach BioGRID complex-like rows as supporting evidence.
- If BioGRID rows are used before complex nodes exist, keep them under `protein_interacts_protein` evidence with `evidence_class = complex_or_cofractionation_association` or a separate evidence-only table, not as memberships.

Fields to preserve for complex-like BioGRID evidence:

- all TAB3 identifiers/provenance fields listed above
- exact `Experimental System` (`Reconstituted Complex`, `Affinity Capture-MS`, etc.)
- `Throughput`, `Score`, `Qualifications`, `Tags`
- `Publication Source`/PMID and `Author`
- ontology term fields if populated
- source endpoint accessions and organism metadata

Validation gate before any `protein_complex` task:

- Builder must prove a source table contains stable complex IDs/names and member identifiers.
- Membership anti-join against canonical protein nodes must pass.
- No pairwise BioGRID rows may be reified into pseudo-complex IDs just to satisfy a schema.

### 3. PTMs -> `ptm_site` / structured PTM event nodes or regulatory evidence

Primary file:

- `BIOGRID-PTMS-5.0.258.ptm.zip`, containing:
  - `BIOGRID-PTM-5.0.258.ptmtab.txt`
  - `BIOGRID-PTM-RELATIONSHIPS-5.0.258.ptmrel.txt`

PTMTAB schema observed:

- `PTM ID`
- `Entrez Gene ID`
- `BioGRID ID`
- `Systematic Name`
- `Official Symbol`
- `Synonymns` (source spelling)
- `Sequence`
- `Refseq ID`
- `Position`
- `Post Translational Modification`
- `Residue`
- `Author`
- `Pubmed ID`
- `Organism ID`
- `Organism Name`
- `Has Relationships`
- `Notes`
- `Source Database`

PTMREL schema observed:

- `PTM ID`
- `Entrez Gene ID`
- `BioGRID ID`
- `Systematic Name`
- `Official Symbol`
- `Synonymns`
- `Relationship`
- `Identity`
- `Author`
- `Pubmed ID`
- `Organism ID`
- `Organism Name`
- `Source Database`

Observed PTMTAB row counts by major PTM type in release 5.0.258:

- Ubiquitination: 1,024,892
- Phosphorylation: 92,599
- Sumoylation: 6,120
- Neddylation: 3,948
- FAT10ylation: 696
- ISGylation: 71
- Ufmylation: 10
- ATG12-ATG5 conjugate: 3

Observed PTMREL relationship/identity counts:

- `Relationship`: `kinase` 13,978; `phosphatase` 1,575; `-` 57,835.
- `Identity`: `PTM` 57,835; `catalytic` 11,978; `regulatory` 3,575.

Modeling recommendation:

- Site-level PTMTAB rows with sequence, RefSeq ID, position, residue, PTM type, publication, and source database should become `ptm_site` nodes or structured PTM event nodes. The node key should include source release, protein/reference sequence, position, residue, and modification type; do not rely on `PTM ID` as a durable global ID because BioGRID documents PTM IDs as file-specific/non-persistent.
- PTMREL rows linking a kinase/phosphatase/regulator to PTM IDs can support directed regulatory evidence such as `protein_regulates_ptm_site` or, if the active schema lacks PTM nodes, evidence-only records pending schema approval.
- `Biochemical Activity` rows in TAB3 with `Modification` populated may support directed `protein_regulates_protein` or PTM evidence when the bait/target roles and modification are semantically clear. They should not be collapsed into undirected `protein_interacts_protein` without preserving `Modification` and direction/role assumptions.

PTM evidence columns to preserve:

- `source_dataset = biogrid_ptm`
- `source_release = BIOGRID-5.0.258`
- `source_file`
- `ptm_id` (file-scoped source ID)
- target source identifiers: Entrez, BioGRID ID, systematic name, official symbol, synonyms
- target protein reference: sequence, RefSeq ID, organism ID/name
- site: position, residue, modification type
- `author`, `pubmed_id`, `source_database`, `notes`, `has_relationships`
- for PTMREL: regulator/source identifiers, `relationship`, `identity`, publication/source fields

Validation gates for PTM build:

- Do not create site nodes when `Position`, `Residue`, sequence/refseq, or modification type is missing or inconsistent.
- Validate residue at position against the provided sequence and/or mapped canonical sequence; mismatches go to quarantine/evidence-only.
- Treat `PTM ID` as release/file-scoped evidence ID, not stable canonical node ID.
- Separate catalytic vs regulatory relationship evidence.

### 4. Genetic interactions -> exclude from protein mechanism edges

BioGRID `SYSTEM` split contains 887,862 genetic rows in release 5.0.258. Genetic systems observed include:

- `Negative Genetic`
- `Positive Genetic`
- `Synthetic Lethality`
- `Synthetic Growth Defect`
- `Synthetic Rescue`
- `Synthetic Haploinsufficiency`
- `Dosage Growth Defect`
- `Dosage Lethality`
- `Dosage Rescue`
- `Phenotypic Enhancement`
- `Phenotypic Suppression`

Recommendation:

- Do not ingest any `Experimental System Type == genetic` row into `protein_interacts_protein`, `protein_regulates_protein`, or other protein mechanism relations.
- If later useful, propose a separate relation family such as `gene_genetically_interacts_gene`, `gene_perturbation_modifies_gene_phenotype`, or a perturbation-event schema. That proposal must define whether endpoints are genes, alleles, perturbations, phenotypes, or screens.
- Preserve `Experimental System`, `Throughput`, `Score`, `Qualifications`, `Tags`, source IDs, organism IDs, and publication metadata in any future genetic evidence table.

## Proposed staged builder tasks and validation gates

These are recommendations only; no ingestion was performed by this audit.

### Stage A — BioGRID release manifest/cache task

Goal: add a release-aware downloader/cache manifest for BioGRID 5.0.258 (or latest pinned version) without building KG edges.

Acceptance gates:

- Manifest records release version, URLs, file sizes/checksums, license URL, retrieval time, and rate-limit retry policy.
- Uses cached files under a project scratch/cache path; avoids repeated full downloads.
- Verifies expected headers for TAB3/PTMTAB/PTMREL.

### Stage B — physical PPI evidence prototype in scratch only

Goal: parse `BIOGRID-MV-Physical` first, optionally full `SYSTEM` physical after review, into a scratch `protein_interacts_protein` candidate/evidence table.

Acceptance gates:

- Filter `Experimental System Type == physical`.
- Exclude RNA, genetic, and non-protein endpoint rows.
- Require both endpoints to have source-provided protein accession support and successful canonical protein mapping.
- Preserve all evidence columns listed above.
- Run endpoint anti-joins and edge/evidence support audit before any promotion proposal.
- Report counts by experimental system, throughput, species pair, endpoint namespace, and dropped-row reason.

### Stage C — complex evidence/source decision task

Goal: decide whether to use BioGRID complex-like rows only as physical evidence or to introduce an explicit external complex source for `protein_complex` nodes.

Acceptance gates:

- Must name exact complex source file/API if creating `protein_complex` nodes.
- Must show stable complex IDs/names/member lists/stoichiometry or explicitly defer nodes.
- BioGRID TAB3 pairwise rows cannot be converted to pseudo-complex membership without external complex identifiers.

### Stage D — PTM site/event schema proposal + scratch parser

Goal: propose and test PTM node/event schema from `BIOGRID-PTMS`.

Acceptance gates:

- Validate site residue/position against sequence.
- Treat BioGRID `PTM ID` as source evidence ID, not persistent node ID.
- Preserve PTMTAB/PTMREL fields and source database.
- Separate PTM site nodes from kinase/phosphatase/regulatory relationships.
- Quarantine ambiguous or sequence-mismatched rows.

### Stage E — genetic interaction proposal only

Goal: decide whether BioGRID genetic rows are useful for TxGNN/Jouvence as a separate perturbation/genetic relation.

Acceptance gates:

- No protein mechanism edge output.
- Define endpoint types and evidence semantics before any parser work.
- Summarize row counts by genetic experimental system/species/throughput and recommend relation names.

## Audit artifacts produced locally

Temporary audit cache (not canonical KG data): `.omoc/biogrid_audit/`

Sampled files:

- `BIOGRID-MV-Physical-5.0.258.tab3.zip`
- `BIOGRID-SYSTEM-5.0.258.tab3.zip`
- `BIOGRID-PTMS-5.0.258.ptm.zip`
- `LICENSE.txt`
- raw wiki/API docs cached for audit notes
- `summary.json` with counts/header summaries used in this document

These artifacts are for audit reproducibility only and should not be promoted as KG inputs without a dedicated builder task.

## Follow-up staging result: RefSeq PTM mapping and explicit complex-source decision

Date: 2026-06-22
Task: `t_9fb5bc76`
Scope: local staging/report update only; no canonical GCS writes.

### PTMTAB RefSeq protein mapping decision

The original zero PTM output was a protein-accession mapping gap, not a biological rejection. The cached canonical `nodes/protein.parquet` has ENSP primary protein IDs and UniProt xrefs, but no populated RefSeq protein xrefs in the local snapshot. A source-native mapping path is feasible:

1. BioGRID PTMTAB provides RefSeq protein accessions in `Refseq ID`.
2. UniProt `HUMAN_9606_idmapping.dat.gz` maps RefSeq protein accessions (`NP_`/`XP_`/`YP_`) to UniProt accessions.
3. Existing canonical `nodes/protein.uniprot_id` maps unambiguous UniProt accessions to ENSP protein node IDs.

This is protein-accession mapping only; Entrez/Gene-only PTMTAB fields are not projected to proteins.

The staged builder now loads the cached UniProt human idmapping file when present and records the mapping audit in `.omoc/reports/biogrid_categorized_stage_20260622.json`:

- UniProt→ENSP xrefs used: 60,652 unique UniProt accessions.
- RefSeq protein mappings added through UniProt idmapping: 13,845.
- Ambiguous RefSeq mappings rejected: 224.
- BioGRID PTMTAB rows seen: 1,128,339.
- Non-human PTMTAB rows rejected: 129,157.
- Rows missing site fields rejected: 45,247.
- Human/site rows still lacking a RefSeq→ENSP mapping rejected: 891,839.

Reliable mapped PTMTAB rows are now staged under `.omoc/staging/biogrid-categorized-20260622/`:

- `nodes/ptm_site.parquet`: 28,169 rows.
- `edges/protein_has_ptm_site.parquet`: 28,169 rows.
- `evidence/protein_has_ptm_site.parquet`: 62,096 rows.
- Modification evidence counts: Ubiquitination 57,098; Phosphorylation 4,680; Neddylation 318.

PTM evidence preserves BioGRID PTM ID, RefSeq ID, residue, position, modification type, sequence, PMID, author, source database, organism, BioGRID/Entrez/symbol source IDs, and `mapping_evidence = protein_node_refseq_xref_or_uniprot_human_idmapping_refseq_to_uniprot`. Site rows are validated against the provided PTMTAB sequence before staging.

Validation from the 2026-06-22 report:

- `ptm_protein_endpoint_antijoin`: 0.
- `ptm_site_endpoint_antijoin`: 0.
- `ptm_edges_without_evidence`: 0.
- `ptm_evidence_without_edges`: 0.
- `ptm_node_duplicate_ids`: 0.

PTMREL kinase/phosphatase/regulatory rows remain report-only until a directed `protein_modifies_ptm_site` or PTM-event regulation schema is explicitly approved.

### Complex-source decision

The follow-up rechecked the BioGRID cached release artifacts and the cached BioGRID download-format page. The listed BioGRID bulk formats are TAB3, MITAB/PSI, PTMTAB/PTMREL, CHEMTAB, PROJECTINDEX, and MV datasets; no explicit complex-member file with stable complex IDs/names/membership/stoichiometry was found in the audited release cache.

Therefore BioGRID complex outputs remain intentionally zero:

- `explicit_biogrid_complex_files_found`: `[]`.
- `protein_complex` staged nodes: 0.
- `protein_part_of_complex`/membership staged edges: 0.

BioGRID TAB3 complex-like/cofractionation rows remain physical association evidence only and must not be reified into pseudo-complex nodes. If Jouvence needs complex nodes, use a source-native complex source such as Complex Portal, CORUM, or Reactome complex records as a separate approved source family, then optionally attach BioGRID complex-like rows as supporting evidence.

### Genetic interaction decision

BioGRID genetic rows remain report-only/excluded from protein mechanism edges. The 2026-06-22 system-split audit reports 887,841 `genetic_excluded` rows and still stages none of them into protein relations.
