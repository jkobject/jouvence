# REL-AUDIT: `transcript_interacts_protein` / `transcript_interacts_gene` blockers

Task: `t_40a66443`  
Status: source/policy audit only; no canonical writes.

## Short answer

The problem is not that RNA/transcript biology is unimportant. The problem is that the currently available canonical and staged material does not yet provide clean source-native endpoint pairs for the two active relations:

- `transcript_interacts_protein` requires a transcript/RNA endpoint and a protein/isoform endpoint for a physical RNA-protein/RBP binding assertion.
- `transcript_interacts_gene` requires a transcript/RNA endpoint and a gene endpoint for a regulatory/mechanistic assertion.

Most candidate sources seen so far are one of these instead:

1. gene-level target rows that should stay gene-level;
2. RNA/protein CLIP context with coordinates or symbols but no validated ENST/ENSP endpoint pair;
3. mature miRNA or lncRNA entities that are not represented by the current active node schema;
4. prediction/correlation/ceRNA/disease-association material that should remain context/evidence, not core mechanism edges.

## Current canonical/schema state inspected

From `manage_db/kg_schema.py`:

- `transcript_interacts_protein`: `transcript -> protein`, `physical`, direct=true. Description says RNA/transcript to protein binding with source-native transcript/protein endpoints, not from `gene_interacts_gene`.
- `transcript_interacts_gene`: `transcript -> gene`, `regulatory`, direct=false. Description says source must name transcript/RNA and gene endpoints with mechanism/direction/effect; not from `gene_interacts_gene`.
- A separate candidate relation also exists outside active `RELATIONS`: `protein_interacts_with_transcript`, but it is intentionally non-active until a concrete RBP/RNA-binding source is chosen.

From live canonical FUSE check against `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`:

- `edges/transcript_interacts_protein.parquet`: absent.
- `evidence/transcript_interacts_protein.parquet`: absent.
- `edges/transcript_interacts_gene.parquet`: absent.
- `evidence/transcript_interacts_gene.parquet`: absent.

From `docs/relation_coverage_current.md` / `docs/kg_schema_overview.md`:

- `transcript_interacts_protein` is `staged-only/deferred`, with `0/0` staged edge/evidence rows accepted. The RBP/ENCORI pilot had 0 accepted rows; next audit should focus POSTAR/ENCORI/NPInter/RNAInter endpoint IDs and license/access.
- `transcript_interacts_gene` is `schema-only/missing`; there is no canonical or staged edge. Docs explicitly say not to use ceRNA/expression correlation/disease association as edges.

## Why the old `gene_interacts_gene` split is blocked

`docs/block1_gene_interacts_gene_audit.md` is the key historical audit.

Canonical `gene_interacts_gene` is gene-endpointed:

- edge endpoints are `ENSG <-> ENSG` for OpenTargets and `NCBI <-> NCBI` for legacy rows;
- canonical evidence endpoints are all `ENSG <-> ENSG`;
- product IDs in OpenTargets raw/canonical evidence live in `intA` / `intB` inside metadata (`text_span` / `source_record_id`), not as graph endpoints.

The raw OpenTargets `interaction` table did contain some RNA-like identifiers in `intA`/`intB`:

- 876 IntAct rows with `URS...` identifiers;
- 1,598 SIGNOR rows with `URS...` identifiers.

But the canonical evidence retained only target-passing gene/gene rows. The relevant RNA-like raw rows are not first-class canonical evidence rows for these transcript relations. Even if raw `URS...` rows are re-audited, they still need endpoint namespace classification and assertion typing: RNA-protein binding, RNA-gene regulation, RNA-RNA interaction, or something else.

So the blocker is endpoint/assertion compression: `gene_interacts_gene` has useful metadata, but it is not a safe source for `transcript_interacts_*` graph edges.

## Candidate source inspection / policy conclusions

### RBP / RNA CLIP: ENCORI, POSTAR, CLIPdb, doRiNA

Best fit: possible future `transcript_interacts_protein` or subtype-specific `lncrna_interacts_protein`.

What they provide:

- POSTAR3 / POSTAR2 / CLIPdb lineage: RBP binding sites and RNA-protein interaction tracks from CLIP/Ribo-seq/function annotations, usually with RBP name, genome assembly, genomic coordinates, target RNA/gene/transcript annotations, assay/study context.
- ENCORI / starBase RBP modules: RBP-mRNA, RBP-lncRNA, RBP-circRNA, RBP-sncRNA, RBP-pseudogene, RBP-caRNA modules with CLIP method/region/context fields.

Why they are blocked now:

- source exports often provide RBP names/gene symbols and target GeneID/GeneName/GeneType or genomic coordinates, not clean `ENST... -> ENSP...` pairs;
- source-native transcript IDs / RefSeq transcript IDs / coordinate-to-transcript mapping must be confirmed per raw export;
- RBP gene symbol -> protein endpoint projection is not approved by default;
- lncRNA endpoints may be NONCODE/LncBook/RNAcentral/GENCODE IDs rather than current ENST transcript nodes;
- a prior ENCORI/POSTAR pilot staged 100 candidate/context rows but accepted 0 active edge/evidence rows because source-native endpoints / lncRNA schema support were missing.

Policy: use these as the first source family for a new audit, but do not canonical-promote until endpoints are validated. Coordinate-only CLIP rows should remain feature/context unless a reviewed coordinate-to-transcript mapping policy is accepted.

### NPInter / RNAInter

Best fit: aggregator/evidence layer first; possible direct experimental subsets later.

What they provide:

- NPInter v5: heterogeneous ncRNA interactions with proteins, genes, DNA, RNA, diseases, chemicals; some experimental ncRNA-protein and Human RBP module material.
- RNAInter v4: integrated RNA interactome across RNA-protein, RNA-RNA, RNA-DNA and other categories with confidence scores.

Why they are blocked now:

- heterogeneous endpoint namespaces: NONCODE, miRBase, RNAcentral/source IDs, UniProt, genes, diseases, chemicals;
- source-of-source provenance and experimental/computational status need row-level filtering;
- many rows are computational or aggregated confidence, not observed physical/mechanistic assertions;
- active KG lacks `lncrna`, `mirna`, RNA-RNA, and structured ncRNA node/relation policy for many endpoint types.

Policy: audit only direct experimental subsets with source-of-source provenance. Keep computational/confidence-only rows as predicted/context features unless a predicted relation is explicitly added.

### miRNA targets: miRTarBase, DIANA-TarBase, ENCORI/starBase miRNA modules

Best fit: future `mirna_targets_gene` / `mirna_regulates_gene`, and only rarely `mirna_targets_transcript`.

Current policy from `docs/proposals/mirna_node_mapping_and_targets_policy.md` and `docs/source_native_expansion_policy.md`:

- current KG has ENST transcript nodes, including 1,879 miRNA-biotype transcript nodes, but these are Ensembl transcript records, not mature arm-specific miRNA products;
- there are no miRBase/RNAcentral/MIMAT/MI alias columns on current transcript nodes;
- create miR-primary nodes only when mature/precursor miRNA entity is distinct from existing ENST;
- gene-level target sources stay gene-level; do not expand to all transcripts or proteins.

Source-specific conclusions:

- miRTarBase / DIANA-TarBase are good validated miRNA target sources, but target endpoints are usually gene symbols / Entrez / HGNC / Ensembl gene, not transcript or protein endpoints.
- ENCORI/starBase miRNA-target and ceRNA modules can be useful, but prediction/CLIP support and ceRNA/correlation status must be explicit.
- Protein readout assays (western blot, reporter effects, translation readout) are evidence fields, not protein endpoint edges unless the row natively identifies a protein/isoform endpoint and protein endpoint mapping is approved.

Policy: do not use `transcript_interacts_gene` as a backdoor for mature miRNA target biology. First approve/add `mirna` node policy and `mirna_targets_gene`; use `mirna_targets_transcript` only for source-native transcript/UTR/site endpoints.

### lncRNA / ceRNA / disease association resources

Best fit: future `lncrna_regulates_gene` for perturbation/mechanism rows; context/features for disease/correlation/ceRNA.

Candidate sources:

- LncRNA2Target: possible perturbation-backed lncRNA -> target gene regulation, if data/terms/schema are accessible.
- LncTarD: possible curated lncRNA target/regulatory mechanisms.
- LncBook: useful catalog and possible interaction source after support-type audit.
- LncRNADisease / Lnc2Cancer / HMDD-style sources: disease association mostly, not target-gene/protein mechanism.
- LncACTdb / ceRNA resources: ceRNA axes and expression/correlation hypotheses.

Why blocked now:

- active schema has `transcript` but no active `lncrna` node family;
- lncRNA source IDs are often NONCODE/LncBook/RNAcentral/GENCODE names, not guaranteed current ENST IDs;
- disease association and expression correlation do not imply transcript->gene mechanism;
- ceRNA hypotheses are RNA-RNA/context-specific and should not be collapsed into `transcript_interacts_gene`.

Policy: if source endpoint is a true ENST/GENCODE transcript and the row has perturbation/mechanism/direction/effect, it can support `transcript_interacts_gene`; otherwise prefer future `lncrna_regulates_gene` or context sidecar.

## Distinguishing true transcript-level evidence from projection

Acceptable for transcript-level relations:

- source names `ENST...`, RefSeq transcript (`NM_...` / `NR_...`), UTR/site/isoform endpoint, or coordinate-to-transcript mapping with retained assembly/site/mapping confidence;
- source names protein/isoform endpoint (`ENSP...`, UniProt mapped unambiguously to KG protein) for RNA-protein binding;
- evidence preserves assay/method, source record, PMID/study, context, score, direction/effect when applicable.

Not acceptable:

- gene-level target row expanded to every transcript of that gene;
- parent gene / symbol used as a proxy for mature miRNA or lncRNA transcript product;
- RBP gene symbol silently mapped to canonical protein edge without approved projection policy;
- protein readout assay converted to protein endpoint edge;
- ceRNA/correlation/disease association used as `transcript_interacts_gene`;
- OpenTargets `gene_interacts_gene` text metadata split into transcript/protein edges without raw endpoint backfill.

## Recommended next policy/cards

1. RBP CLIP endpoint audit for `transcript_interacts_protein`:
   - inspect exact downloadable POSTAR3 and ENCORI RBP exports;
   - classify target endpoint fields as ENST, RefSeq transcript, gene, coordinate-only, lncRNA-specific, or ambiguous;
   - classify RBP endpoint as UniProt/ENSP/protein-native versus gene symbol only;
   - stage only non-empty rows that pass endpoint anti-joins and evidence support;
   - otherwise keep `rbp_binding_site_context` sidecar.

2. RNAInter/NPInter experimental subset audit:
   - filter to direct experimental RNA-protein and RNA-gene rows;
   - preserve original source-of-source, interaction category, experimental/computational status, source IDs, and confidence;
   - decide whether rows belong to generic `transcript_interacts_*`, future `lncrna_*`, future `mirna_*`, RNA-RNA relation, or context only.

3. miRNA schema gate before target ingestion:
   - approve `mirna` / `mature_mirna` / `mirna_precursor` node representation and mapping table/xrefs;
   - approve naming `mirna_targets_gene` vs `mirna_regulates_gene`, and optional `mirna_targets_transcript`;
   - only then build miRTarBase/DIANA-TarBase staged edges.

4. lncRNA regulatory source gate:
   - approve whether broad `transcript_interacts_gene` is acceptable for ENST/GENCODE lncRNA perturbation rows or whether a subtype-specific `lncrna_regulates_gene` relation is required first;
   - audit LncRNA2Target/LncTarD access/license/schema;
   - reject/downgrade disease-only and ceRNA/correlation-only rows to context sidecars.

## Bottom line

Leave both active relations blocked for canonical promotion now:

- `transcript_interacts_protein`: viable, but only after POSTAR/ENCORI/NPInter/RNAInter raw endpoint audit proves transcript/RNA and protein endpoints without silent gene/protein projection.
- `transcript_interacts_gene`: currently weaker; viable only for perturbation/mechanism-backed RNA->gene regulation, preferably after deciding whether miRNA/lncRNA subtype-specific relations should replace the generic relation.

The safe near-term product is a source/context sidecar plus explicit schema gates, not canonical edges.
