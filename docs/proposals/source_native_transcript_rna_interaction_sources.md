# Source-native transcript/RNA interaction sources for P3 KG expansion

Status: proposal only. No bulk data were downloaded or ingested.

S1/P4 update: later Jérémie decisions supersede the miRNA/transcript node policy in this proposal. Existing ENST `transcript` nodes remain; do not create duplicate transcript nodes or choose a main transcript. Add miRBase/hsa-miR aliases/xrefs to existing ENST transcript nodes only for true 1:1 mappings. Create miR-primary mature/precursor nodes only when the mature/precursor miRNA entity is distinct from an existing transcript entity. Gene-level miRNA target measurements stay gene-level; use `mirna_targets_transcript` only for transcript/UTR/site-level endpoints. See `docs/source_native_expansion_policy.md`.

Goal: identify source-native replacements for transcript/RNA-like rows that were not preserved in canonical `gene_interacts_gene`, without converting generic coexpression or gene-level interaction data into transcript/protein mechanisms.

## Recommendation summary

Keep four mechanisms separate:

1. RNA/transcript binds protein/RBP: physical binding, usually CLIP/eCLIP/PAR-CLIP/HITS-CLIP/iCLIP or curated RNA-protein interaction evidence. Candidate relation: `transcript_interacts_protein`; subtype-specific future relation: `lncrna_interacts_protein`.
2. miRNA regulates target gene/transcript/protein translation: post-transcriptional regulatory mechanism. Future relation: `mirna_regulates_gene`, with optional later `mirna_regulates_transcript` or `mirna_regulates_protein` only when the source endpoint is transcript/protein-native.
3. lncRNA regulates target gene: perturbation, transcriptional/post-transcriptional regulation, ceRNA, chromatin, or other mechanism. Future relation: `lncrna_regulates_gene`; use `transcript_interacts_gene` only as a temporary broad relation if Jérémie does not want subtype-specific ncRNA relations yet.
4. Generic transcript/RNA to gene association: use `transcript_interacts_gene` only for source-native RNA/transcript endpoint + gene endpoint mechanism assertions. Do not use it for expression correlation, disease association, pathway enrichment, or RBP binding projected to target genes.

Default stance: promote experimental/curated mechanism rows first; keep predictions, motif scans, ceRNA-only networks, and integrated confidence scores as evidence/features unless explicitly approved.

## Source assessment table

| Source | Class | Native assertion | Endpoint namespaces / IDs | Assay/context/provenance fields to preserve | Recommended placement |
|---|---|---|---|---|---|
| POSTAR3 / POSTAR2 / CLIPdb lineage | `recommended` | RBP binding sites and RNA-protein interaction tracks from public CLIP-seq/Ribo-seq/function annotations. POSTAR3 paper: NAR 2022, PMID:34403477; CLIPdb paper: PMID:25652745. | RBP/protein names; genome assembly/species; genomic coordinates; target RNA/transcript/gene annotations; CLIPdb paper reports coding, canonical ncRNA, and lncRNA transcript classes. Exact exported Ensembl/RefSeq transcript fields must be checked before ingest. | CLIP technology, RBP, RNA class, chromosome/start/end/strand, assembly, binding-site/peak, dataset accession, source study, PMID, functional annotations, confidence/support if present. | Primary candidate for `transcript_interacts_protein` when transcript or coordinate-to-transcript mapping is accepted; `lncrna_interacts_protein` when RNA class/ID is lncRNA. Keep Ribo-seq, variant, miRNA cross-talk annotations as evidence/context only. |
| ENCORI / starBase RBP modules | `recommended` | RBP-RNA and RNA-RNA interactomes from CLIP-seq; starBase v2.0 decoded protein-RNA networks from 108 CLIP-seq datasets (PMID:24297251); ENCORI 2026 describes updated modules (PMID:42185542). | RBP name; target `GeneID`, `GeneName`, `GeneType`; genome/clade/assembly; modules for RBP-mRNA, RBP-lncRNA, RBP-circRNA, RBP-sncRNA, RBP-pseudogene, RBP-caRNA. | CLIP method/type (`PAR-CLIP`, `iCLIP`, `eCLIP`, `HITS-CLIP`, other), CLIP region (`Single site`/`Peak`), P-value threshold, cluster/site counts, cell/tissue/treatment, accessions, source/reference, PMID. | Primary candidate for `transcript_interacts_protein` from RBP-mRNA/transcript-like modules and `lncrna_interacts_protein` from RBP-lncRNA. ENCORI miRNA/ceRNA modules are not physical RNA-protein edges; evaluate separately for miRNA/lncRNA regulation. |
| CLIPdb | `maybe_contextual` | Legacy CLIP-seq database for protein-RNA interactions; later merged/superseded by POSTAR2/POSTAR3. | RBP identifiers/names; RNA transcript classes; organism; binding-site coordinates. Current schema/access timed out in prior review. | CLIP method, dataset/study, RBP, organism, nucleotide-resolution binding sites, coordinates, PMID/accession if available. | Prefer POSTAR3. Use CLIPdb only as historical source label/evidence where POSTAR retains provenance. |
| doRiNA / doRiNA 2.0 | `maybe_contextual` | RBP and miRNA binding sites in post-transcriptional regulation; regulator/target searches. Papers PMID:22086949 and PMID:25416797. Current site appears archived. | RBP/miRNA regulators; target mRNA/gene; likely genomic binding-site tracks; exact IDs need archive/schema inspection. | RBP or miRNA, target mRNA, coordinates/tracks, regulator combinations, source evidence, PMID. | Evidence-only/historical unless accessible data and terms are confirmed. Do not prioritize over POSTAR/ENCORI. |
| ATtRACT | `maybe_contextual` | Experimentally validated RBP motifs, not observed transcript-specific binding events. | RBP gene name/synonyms; examples include Ensembl gene IDs; motif sequence/PWM; organism; PMID. | Experiment type (NMR, IP, RNAcompete, EMSA, SELEX, UV cross-linking, X-ray, RNA affinity, etc.), motif/domain, Qscore, PMID. | Feature/evidence table for motif support. Reject as direct `transcript_interacts_protein` unless a predicted-binding relation is approved. |
| oRNAment | `maybe_contextual` | Putative RBP motif instances across coding/non-coding transcriptomes; prediction/motif placement, not direct CLIP binding. Paper PMID:31724725. | Genes/transcripts; complete coding and noncoding RNA species; RBP motifs; species. Exact transcript namespace must be checked. | Motif instance, RBP motif, transcript attributes, thresholds/similarity, species. No cell/tissue CLIP context. | Feature table or predicted binding evidence only. Not a canonical physical interaction source by default. |
| NPInter v5 | `recommended` for experimental ncRNA-protein subset; `maybe_contextual` for broad aggregation | Functional ncRNA interactions with proteins, genes, DNA, RNA, diseases, chemicals, etc.; v5 reports millions of ncRNA interactions and a Human RBP module (PMID:36373614). | Examples include NONCODE lncRNA IDs (`NONHSAG...`), miRBase IDs (`MI...`), UniProt protein accessions (`P04637`), circBase, possibly RNAcentral/source IDs through integrated resources. | Interaction ID, ncRNA, partner, interaction level/class, organism, tags, data source, tissue/cell line, experimental vs computational category, PMID/publication, confidence/score if present. | Use experimental direct RNA-protein records for `lncrna_interacts_protein` or subtype-specific ncRNA-protein relations. Use RNA-gene regulatory rows only if mechanism and endpoints are explicit. Computational rows stay predicted evidence/features. |
| RNAInter v4 | `maybe_contextual`; `recommended` only after direct experimental subset audit | Integrated RNA interactome across RNA-protein, RNA-RNA, RNA-DNA and other interaction types; improved scoring (PMID:34718726). | Heterogeneous source IDs for RNA, proteins, genes, diseases/tissues; exact schema/download fields need API/download validation. | Confidence score, interaction type, tissue/cell type, source database/publication, evidence category, organism. | Aggregation/evidence layer first. Promote only direct experimental RNA-protein or RNA-gene mechanism records with resolvable endpoints and preserved source-of-source provenance. |
| miRTarBase | `recommended` | Experimentally validated miRNA-target interactions (MTIs), including reporter assays, western blot/qPCR/microarray/NGS and other support. Recent papers via PubMed/NCBI; web access returned HTTP 412 to automation in prior review. | miRNA IDs/names from miRBase/MIMAT/MI naming; target gene symbols/Entrez/Ensembl-like fields depending release; target species; target gene endpoint. Usually gene-level target, not protein endpoint. | Experiment/support type, strong/weak evidence class, assay, species, cell line/tissue/disease if present, PMID, direction/effect if reported, source record/release. | Primary candidate for future `mirna_regulates_gene`. Do not write `mirna_regulates_protein` unless the row directly measures protein/translation effect and protein endpoint mapping policy is approved; otherwise protein-effect assay belongs in evidence. |
| DIANA-TarBase v8 | `recommended` | Manually curated experimentally supported miRNA-gene interactions. TarBase v8 paper: NAR 2018, PMID:29156006. | miRNA names/IDs; target genes; species; often gene identifiers rather than transcript/protein endpoints. | Experimental method, cell/tissue/cell line, regulation direction, validation type, PMID, source record, tissue/cell-type context when available. | Primary/secondary source for future `mirna_regulates_gene`, complementary to miRTarBase. Keep assay-specific protein readouts as evidence, not as protein endpoint edges unless explicitly source-native. |
| ENCORI / starBase miRNA-target and ceRNA modules | `maybe_contextual` | CLIP-supported miRNA-target interactions and ceRNA/RNA-RNA network modules. | miRNA IDs/names; target `GeneID`/`GeneName`/`GeneType`; lncRNA/circRNA/mRNA/pseudogene endpoints; assembly/context. | CLIP support count, Ago/RBP-related CLIP evidence, predicted target program support, cancer/cell context, site/region, PMID/source. | Use carefully for `mirna_regulates_gene` only when target support is CLIP/experimental enough and prediction status is explicit. ceRNA/RNA-RNA modules should be evidence-only or future RNA-RNA relations, not `transcript_interacts_gene` by default. |
| LncRNA2Target | `recommended` if site/data are accessible and terms pass | lncRNA perturbation-derived target genes from knockdown/overexpression and downstream expression effects. Site timed out in prior review; use paper facts until schema is checked. | lncRNA names/IDs; target gene symbols/IDs; cell/tissue/species; perturbation dataset. Endpoint is usually lncRNA -> gene. | Perturbation type, knockdown/overexpression, expression direction/effect, cell line/tissue, disease/context, assay/platform, PMID/source dataset. | Strong candidate for future `lncrna_regulates_gene` or broad `transcript_interacts_gene`, but not physical binding. Reject pure expression correlation rows without perturbation/mechanism. |
| LncBook / LncBook 2.0 | `maybe_contextual` for regulation; `recommended` for audited lncRNA-protein subset | Human lncRNA catalog plus lncRNA-protein/miRNA/omics annotations; prior planning doc notes large lncRNA-protein and lncRNA-miRNA interaction counts. | LncBook IDs, lncRNA gene/transcript IDs, Ensembl/GENCODE-like IDs, gene symbols; partner proteins/miRNAs/genes depending module. | Interaction/support type, source database, score/confidence, tissue/cell context, PMID/source if present, predicted vs experimental status. | Use as lncRNA node/catalog source after RNAcentral/GENCODE harmonization. Promote lncRNA-protein or lncRNA-gene rows only after support-type audit; predicted-only rows remain features/evidence. |
| LncTarD / LncTarD 2.0 | `recommended` if terms/access pass | Curated lncRNA-target regulations with disease associations and mechanisms. | lncRNA names/IDs; target genes; diseases; likely gene symbols/Entrez/Ensembl mapping needed. | Regulation mechanism, direction/effect, disease/context, expression change, experimental support, PMID. | Candidate for future `lncrna_regulates_gene` / `transcript_interacts_gene` with evidence. Disease annotations stay evidence/context, not target-gene mechanism by themselves. |
| Lnc2Cancer / LncRNADisease / HMDD-style disease resources | `maybe_contextual` | ncRNA-disease associations, often expression/disease relation rather than mechanism to a target gene/protein. | lncRNA/miRNA IDs or names; disease names/IDs; sometimes target/mechanism fields. | Disease, expression direction, sample/tissue, evidence type, PMID, curation status. | Do not populate `transcript_interacts_gene` or RNA-protein relations from disease association alone. Use future `lncrna_associated_disease`/`mirna_associated_disease` if approved. |
| LncACTdb / ceRNA resources | `maybe_contextual` or `reject_for_causal_mechanism` depending row | ceRNA axes among lncRNA/circRNA/mRNA/miRNA, often cancer-context regulatory hypotheses. | lncRNA/circRNA/miRNA/mRNA names/IDs; disease/cancer context; target gene. | ceRNA axis, cancer/tissue/cell line, experimental support, expression/correlation, PMID. | Keep as evidence-only unless Jérémie approves a distinct RNA-RNA/ceRNA relation. Do not collapse ceRNA correlation into `transcript_interacts_gene`. |
| Generic coexpression/correlation resources | `reject_for_causal_mechanism` | RNA/gene expression correlation, pathway enrichment, pan-cancer association, or disease co-occurrence. | Usually gene/transcript names and sample contexts, not mechanism endpoints. | Correlation/effect sizes, context, study. | Reject for `transcript_interacts_protein`, `transcript_interacts_gene`, `mirna_regulates_gene`, and `lncrna_regulates_gene`. These are features/evidence at most. |

## Relation-specific placement

### `transcript_interacts_protein`

Use only for source-native RNA/transcript-protein binding.

Recommended first-pass sources:

1. POSTAR3 RBP binding sites when target RNA can be represented as an Ensembl/RefSeq transcript or a coordinate interval that maps to a transcript with retained provenance.
2. ENCORI/starBase RBP-mRNA/RBP-caRNA modules when CLIP fields and target type support transcript-like RNA binding.
3. NPInter/RNAInter experimental RNA-protein subset only after source-of-source provenance, terms, and endpoint normalization are audited.

Evidence fields: `source_dataset`, `source_version`, `source_record_id`, `rna_id`, `rna_id_namespace`, `rna_class`, `rbp_name`, `protein_id`, `protein_id_namespace`, `genome_assembly`, `chromosome`, `start`, `end`, `strand`, `clip_method`, `clip_region_type`, `dataset_accession`, `cell_type`, `tissue`, `treatment`, `score`, `p_value`, `confidence`, `pmid`, `experimental_vs_computational`.

Endpoint policy:

- RNA endpoint: prefer Ensembl transcript (`ENST...`) or RefSeq transcript (`NM_...`, `NR_...`) if source provides it.
- Coordinate-only rows: require explicit approval for coordinate-to-transcript mapping; preserve assembly and mapping method.
- Protein endpoint: prefer existing KG `protein` node (`ENSP...`) with UniProt accession retained as xref/evidence. If source only has RBP gene symbol, decide whether canonical protein projection is allowed; do not silently create protein edges.

### `lncrna_interacts_protein`

This should probably be a future subtype-specific relation rather than squeezing lncRNA rows into generic `transcript_interacts_protein`, because lncRNA endpoints often use NONCODE/LncBook/RNAcentral IDs and not ENST.

Recommended first-pass sources:

1. ENCORI/starBase RBP-lncRNA CLIP-supported module.
2. POSTAR3 lncRNA/canonical ncRNA binding sites.
3. NPInter v5 experimental lncRNA/ncRNA-protein rows.
4. RNAInter v4 direct experimental RNA-protein rows after source audit.

Endpoint namespaces: Ensembl transcript (`ENST...`) when available; NONCODE (`NONHSAG...`); LncBook IDs; RNAcentral/URS; GENCODE transcript/gene IDs; UniProt protein accessions; KG protein `ENSP...` after mapping.

### `transcript_interacts_gene`

Use as a broad regulatory relation only when the source has a source-native RNA/transcript endpoint and a target gene endpoint with mechanism. It should not be a dumping ground for all RNA-gene associations.

Acceptable source-native mechanisms:

- lncRNA perturbation regulates target gene expression, with knockdown/overexpression and direction/effect.
- miRNA target regulation only if Jérémie chooses to use broad `transcript_interacts_gene` before adding `mirna` nodes; otherwise prefer `mirna_regulates_gene`.
- RNA-guided/chromatin/transcriptional regulation with target gene endpoint, if a source explicitly captures the mechanism.

Recommended sources:

- LncRNA2Target for perturbation-backed lncRNA -> target gene regulation, after access/license/schema validation.
- LncTarD for curated lncRNA -> target gene regulation with disease/mechanism evidence, after terms validation.
- ENCORI/starBase miRNA-target rows only if prediction/CLIP support is explicit and a subtype-specific relation is not yet available.
- NPInter/RNAInter only for direct, mechanism-labeled RNA-gene records with experimental support.

Reject for this relation: RBP binding projected to “gene regulation” without target-gene regulatory evidence; ceRNA correlation; disease association; expression correlation; pathway enrichment.

Evidence fields: `rna_id`, `rna_id_namespace`, `rna_class`, `target_gene_id`, `target_gene_namespace`, `mechanism`, `regulation_direction`, `sign_or_effect`, `perturbation_type`, `assay`, `cell_type`, `tissue`, `disease_context`, `score`, `confidence`, `source_dataset`, `source_record_id`, `pmid`, `experimental_vs_computational`.

### Future `mirna_regulates_gene` / `mirna_regulates_protein`

Recommendation: add `mirna` nodes before ingesting miRNA target edges. Do not represent mature miRNAs as generic gene nodes unless the source row itself is precursor-gene-level.

Primary namespaces:

- Mature miRNA: miRBase mature accession (`MIMAT...`) and mature name (`hsa-miR-...`).
- Precursor miRNA: miRBase hairpin accession (`MI...`) as xref.
- RNAcentral/URS as consolidation xref if mapping is available.
- Target: Ensembl gene (`ENSG...`) or source target gene ID/symbol mapped to KG gene nodes.

Recommended sources:

1. miRTarBase: primary validated MTI source.
2. DIANA-TarBase v8: secondary/manual curated validated miRNA-gene interactions.
3. ENCORI/starBase: contextual CLIP-supported miRNA-target or AGO-supported rows; keep predicted status explicit.

Evidence policy:

- Reporter assay, western blot/qPCR, CLIP/Ago evidence, microarray/NGS after perturbation, and support type should be row-level evidence.
- Protein-level assay readouts do not automatically make a `mirna_regulates_protein` edge unless the target protein endpoint is source-native or approved mapping is used.
- Prediction-only target programs should be evidence/features, not canonical edges, unless a predicted relation is explicitly added.

### Future `lncrna_regulates_gene`

Recommendation: add `lncrna` nodes before building lncRNA regulatory edges when source endpoints are not ordinary ENST transcripts.

Primary namespaces:

- Ensembl transcript (`ENST...`) and Ensembl gene (`ENSG...`) where available.
- GENCODE transcript IDs.
- RNAcentral/URS where available.
- NONCODE and LncBook IDs retained as source IDs/xrefs.

Recommended sources:

1. LncRNA2Target for perturbation-backed lncRNA target genes, if data/terms are accessible.
2. LncTarD for curated lncRNA target/regulatory mechanisms.
3. LncBook only after support-type audit; use as node/catalog and possible interaction source, not blindly as a regulatory-edge source.
4. NPInter/RNAInter experimental rows only when mechanism and target gene endpoint are explicit.

Reject: lncRNA-disease association without target mechanism; lncRNA/protein binding without target-gene regulation; ceRNA expression correlation without mechanistic support.

## Classification by first ingestion priority

### `recommended`

- POSTAR3 and ENCORI/starBase RBP modules for CLIP-supported RNA-protein binding.
- miRTarBase and DIANA-TarBase for validated miRNA -> target gene regulation.
- LncRNA2Target and LncTarD for lncRNA -> target gene regulation, pending access/licensing/schema validation.
- NPInter v5 experimental lncRNA/ncRNA-protein subset, after endpoint/source-of-source filtering.

### `maybe_contextual`

- RNAInter v4 as an aggregator/evidence layer until exact schema, source provenance, and direct experimental subset are audited.
- CLIPdb and doRiNA as historical/contextual resources, likely superseded by POSTAR/ENCORI.
- ATtRACT and oRNAment as motif/prediction feature tables.
- ENCORI ceRNA/RNA-RNA/pan-cancer modules as context for future RNA-RNA/ceRNA decisions, not current target relations.
- LncBook as lncRNA catalog and possible interaction source after support audit.
- lncRNA/miRNA disease resources for future disease association relations, not mechanism edges.

### `reject_for_causal_mechanism`

- Generic coexpression or expression-correlation-only resources.
- Motif scans alone as physical binding edges.
- Prediction-only miRNA/lncRNA targets as canonical regulatory edges without predicted-edge semantics.
- Disease association resources used as a proxy for RNA -> gene/protein mechanism.
- ceRNA networks collapsed into `transcript_interacts_gene` without explicit mechanism/evidence.
- RBP binding rows projected into gene regulation without a target-gene regulation assertion.

## Approval questions for Jérémie

1. For POSTAR/ENCORI CLIP sites that are genomic-coordinate or gene-level rather than explicit `ENST`/RefSeq transcript endpoints: should we allow coordinate-to-transcript mapping to create `transcript_interacts_protein`, or keep them evidence-only until the source exports transcript IDs?
2. For RBP endpoints reported only as RBP gene symbols: should the KG create protein edges via gene -> canonical protein mapping with provenance, or require UniProt/protein-native source endpoints?
3. Should we add subtype-specific `mirna_regulates_gene`, `lncrna_regulates_gene`, and `lncrna_interacts_protein` before ingesting these sources, or temporarily use broad `transcript_interacts_gene` / `transcript_interacts_protein` with `rna_class` evidence?
4. Are prediction-only resources such as oRNAment, ATtRACT motif scans, predicted miRNA targets, and computational NPInter/RNAInter rows allowed as low-confidence predicted evidence, or should they stay out of canonical edge files entirely?
5. Should ceRNA resources be treated as future RNA-RNA regulatory relations, evidence-only context, or rejected from the KG core?
6. Licensing gate: ENCORI exposes CC-BY-4.0 in page HTML, but POSTAR3, NPInter, RNAInter, oRNAment, ATtRACT, LncRNA2Target, LncTarD, and LncBook terms were not fully verified in quick public-page review. Should implementation wait for explicit license/contact confirmation for every source?

## Implementation gates for any future ingestion card

1. Do not ingest from this proposal directly. Create a separate implementation card per source family.
2. Check license/redistribution terms and citation requirements first.
3. Download only a release-pinned, targeted file into `.omoc/gcs-cache/kg-v2/raw/<source-release>/`.
4. Inspect the raw schema and sample rows before naming relations.
5. Normalize endpoints against existing KG nodes; add `mirna`/`lncrna` nodes first if subtype-specific relations are approved.
6. Materialize evidence rows alongside every edge row; include source-specific support and experimental/predicted status.
7. Validate endpoint anti-joins and evidence support before promotion.

## Sources checked / source facts used

- Existing repo docs: `docs/source_measure_edge_matrix.md`, `docs/kg_schema_overview.md`, `docs/block1_relation_source_split_plan.md`, `docs/later_node_edge_families_plan.md`.
- POSTAR3 public pages and NAR paper PMID:34403477; POSTAR2 PMID:30239819; CLIPdb PMID:25652745.
- ENCORI/starBase pages and papers: starBase v2.0 PMID:24297251; ENCORI 2026 PMID:42185542.
- doRiNA papers PMID:22086949 and PMID:25416797.
- ATtRACT public docs/pages.
- oRNAment paper PMID:31724725.
- NPInter v5 pages/paper PMID:36373614.
- RNAInter v4 pages/paper PMID:34718726.
- miRTarBase paper facts via PubMed/NCBI; automated website access returned HTTP 412 in prior review, so license/schema must be manually checked.
- DIANA-TarBase v8 official page/paper PMID:29156006.
- LncRNA2Target papers; public site timed out in prior review.
- LncBook 2.0, LncTarD 2.0, Lnc2Cancer, LncACTdb and lncRNA-disease resource facts from public pages/papers as summarized in prior L2 planning and source review.
