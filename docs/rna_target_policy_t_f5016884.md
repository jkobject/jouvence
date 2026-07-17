# RNA-target policy gate before miRNA/lncRNA/RBP ingestion

Task: `t_f5016884`  
Status: policy decision only; no canonical KG writes.

## Decision summary

Do not use the existing generic transcript relations as a backdoor for subtype-specific RNA biology.

Near-term allowed path:

1. RBP/RNA physical binding may use active `transcript_interacts_protein` only for source-native transcript/RNA endpoint rows that can be represented as current `transcript` nodes plus source-native or approved-mapped protein endpoints.
2. lncRNA-protein rows should wait for subtype-specific `lncrna_interacts_protein` unless the RNA endpoint is genuinely an existing ENST/RefSeq transcript and the source row is not lncRNA-catalog-specific.
3. miRNA target ingestion should wait for `mirna`/mature-miRNA node policy implementation plus `mirna_targets_gene` and optional `mirna_targets_transcript`. Do not load mature miRNA target rows into generic `transcript_interacts_gene`.
4. lncRNA target-gene regulation should prefer future `lncrna_regulates_gene`; use active `transcript_interacts_gene` only for ENST/RefSeq/GENCODE transcript endpoint rows with perturbation/mechanism/direction/effect, not for lncRNA-name-only or catalog IDs.
5. Coordinate-only CLIP/site rows remain context sidecars unless a reviewed coordinate-to-transcript/site mapping policy is approved and evidence retains assembly, interval, mapping method, confidence, and source site/peak ID.
6. RBP gene-symbol endpoints are not enough for canonical protein edges. Require source-native UniProt/ENSP/protein endpoint, or a separate reviewed gene-symbol-to-protein projection gate with row-level provenance and ambiguity handling.

## Relation and node gates

### Physical RBP/RNA binding

Allowed canonical/staged relation now, with strict gates:

- `transcript_interacts_protein`
  - x endpoint: current `transcript` node (`ENST...`) or reviewed RefSeq/GENCODE transcript mapping to current transcript nodes.
  - y endpoint: current `protein` node (`ENSP...`) or source-native UniProt/protein accession mapped unambiguously to a KG protein node with the original accession retained in evidence.
  - assertion: physical RNA/transcript-protein binding or interaction, e.g. CLIP/eCLIP/PAR-CLIP/HITS-CLIP/iCLIP or curated direct RNA-protein interaction.
  - evidence must preserve source dataset/release, source record, original RNA/protein IDs, RBP name, RNA class, assay/method, coordinates/sites if present, context, score/confidence, PMID/study/accession, and experimental/computational flag.

Do not use `transcript_interacts_protein` for:

- RBP binding exported only as target gene ID/name plus RBP gene symbol with no transcript/protein mapping gate;
- lncRNA-specific IDs such as NONCODE/LncBook/RNAcentral when they are not mapped to existing transcript nodes;
- motif-only or prediction-only RBP binding such as ATtRACT/oRNAment without an explicit predicted/context relation;
- rows from canonical `gene_interacts_gene` metadata without raw source endpoint backfill.

Needed future relation before many lncRNA/RBP rows:

- `lncrna_interacts_protein`
  - x endpoint should be an approved lncRNA/ncRNA node or ENST/GENCODE/RNAcentral/NONCODE/LncBook mapping table, not a parent gene proxy.
  - y endpoint follows the same protein endpoint rule as above.
  - use for ENCORI/starBase RBP-lncRNA, POSTAR lncRNA/canonical-ncRNA binding sites, NPInter/RNAInter direct experimental ncRNA-protein subsets after source audit.

### RNA to gene regulation

Do not populate active `transcript_interacts_gene` from mature miRNA target sources by default.

Allowed generic relation only for narrow cases:

- `transcript_interacts_gene`
  - x endpoint: source-native transcript/RNA endpoint representable as current `transcript` node or reviewed transcript mapping.
  - y endpoint: target gene mapped to current `gene` node.
  - assertion: source-native RNA/transcript -> gene regulatory or mechanistic assertion with mechanism/direction/effect/perturbation support.
  - examples: lncRNA perturbation row with ENST/GENCODE lncRNA endpoint and target ENSG/gene endpoint; RNA-guided/chromatin/transcriptional regulation row with explicit RNA endpoint and target gene.

Reject for `transcript_interacts_gene`:

- miRTarBase/DIANA-TarBase rows where regulator is a mature miRNA product; these need miRNA nodes and `mirna_targets_gene`/`mirna_targets_transcript`.
- ceRNA networks, shared-miRNA hypotheses, disease association, coexpression/correlation, pathway enrichment.
- RBP binding projected to target-gene regulation.
- gene-level target rows expanded to transcripts.

Needed future relations before builder ingestion:

- `mirna_targets_gene`
  - x endpoint: approved `mirna`/`mature_mirna` node, preferably mature miRBase `MIMAT...` or equivalent release-pinned ID.
  - y endpoint: current `gene` node (`ENSG...`) for gene-level target sources.
  - use `targets` rather than `regulates` unless schema gate restricts edges to direction/effect regulation assertions; assays and direction/effect live in evidence.

- `mirna_targets_transcript`
  - x endpoint: approved miRNA node.
  - y endpoint: current `transcript` node only when the source row has transcript/UTR/site-native endpoint or reviewed coordinate-to-transcript mapping.
  - no gene-target-to-all-transcripts expansion.

- `lncrna_regulates_gene`
  - x endpoint: approved lncRNA/ncRNA node, or ENST/GENCODE lncRNA transcript only when source-native and mapped with provenance.
  - y endpoint: current `gene` node.
  - assertion: perturbation/mechanism/regulatory row with direction/effect when source provides it.

## Endpoint projection rules

1. Source-native endpoint wins. Model the source row at the endpoint type it actually measures or asserts.
2. Gene-level source rows stay gene-level. They must not be expanded to all transcript isoforms or projected to proteins.
3. Mature miRNA products are not parent MIR genes and are not automatically ENST transcript nodes. Use existing transcript nodes only for true 1:1 transcript identities; create miR-primary nodes for mature/precursor products when distinct.
4. lncRNA IDs/names from NONCODE, LncBook, RNAcentral, or GENCODE require an approved lncRNA/transcript mapping table before graph edges.
5. RBP gene symbol -> canonical protein is blocked by default. Approve only after a separate projection gate defines species, canonical isoform choice, ambiguity handling, and evidence fields. Until then, such rows are context/rejected candidates.
6. Coordinate-only site/peak rows are blocked from canonical edges unless mapping policy is reviewed. If approved later, preserve genome assembly, chromosome, start, end, strand, source site/peak ID, transcript/UTR mapping method, mapping confidence, and overlapping feature in evidence.
7. Protein readout in miRNA assays is evidence, not a protein target edge, unless the row natively names a protein/isoform endpoint and a protein endpoint relation is separately approved.
8. Prediction/correlation/context-only rows can be staged as feature/context sidecars with honest labels (`predicted`, `correlative`, `candidate_context`, `ceRNA_context`), not as canonical mechanism edges.

## Approved source families for builder cards

Builders may be created only as source-audit/staging cards; every card must first check license/terms, raw schema, endpoint namespaces, evidence fields, and endpoint anti-joins. No canonical promotion without independent review.

Approved first-pass audit/build cards:

1. RBP CLIP/source-native RNA-protein binding audit
   - sources: POSTAR3/POSTAR lineage, ENCORI/starBase RBP modules.
   - target output: `transcript_interacts_protein` staged edges only for passing ENST/RefSeq/GENCODE transcript + UniProt/ENSP protein rows; otherwise `rbp_binding_site_context` sidecar/rejected-candidate report.
   - include lncRNA rows in a separate bucket pending `lncrna_interacts_protein`.

2. NPInter/RNAInter direct experimental subset audit
   - sources: NPInter v5 and RNAInter v4.
   - target output: classification report first; staged edges only for direct experimental rows with explicit endpoint namespaces and source-of-source provenance.
   - separate rows into RNA-protein, RNA-gene, RNA-RNA, disease/chemical/context, computational/predicted.

3. miRNA schema/node gate
   - sources: miRBase/RNAcentral/Ensembl xrefs as catalog inputs.
   - target output: approved `mirna`/`mature_mirna` node design, mappings to existing ENST only when true 1:1, and schema docs/tests. No target edges in this card.

4. Validated miRNA target source audits
   - sources: miRTarBase and DIANA-TarBase.
   - target output after miRNA node gate: staged `mirna_targets_gene` for validated human gene-level MTIs; staged `mirna_targets_transcript` only for transcript/UTR/site-native rows.
   - preserve support type, assay, direction/effect, cell/tissue/context, PMID, source record, original IDs, and mapping confidence in evidence.

5. lncRNA regulation source audits
   - sources: LncRNA2Target and LncTarD first; LncBook only after support-type audit.
   - target output: `lncrna_regulates_gene` once lncRNA node/mapping policy exists; narrow `transcript_interacts_gene` only for source-native ENST/GENCODE transcript rows with perturbation/mechanism support.
   - reject disease-only and ceRNA/correlation-only rows to context sidecars.

Not approved for canonical mechanism edges now:

- ATtRACT/oRNAment motif or predicted RBP binding as physical edges.
- ceRNA/correlation networks collapsed into `transcript_interacts_gene` or miRNA target relations.
- disease-association-only ncRNA resources as RNA-target mechanism edges.
- canonical `gene_interacts_gene` metadata split into transcript/protein/RNA edges without raw endpoint backfill.

## Builder acceptance gates

Every downstream builder card must prove:

1. exact source release/download and license/redistribution status;
2. raw schema/sample rows documented under `docs/` or `artifacts/`;
3. row-level endpoint namespace classification;
4. mapping tables and confidence/provenance for any non-native endpoint mapping;
5. endpoint anti-joins against current canonical nodes;
6. edge/evidence co-materialization with source record IDs and support fields;
7. context/predicted/correlative rows excluded from canonical mechanism edges unless a predicted/context relation is explicitly approved;
8. coverage docs updated only with real staged/canonical counts;
9. reviewer acceptance before canonical writes.

## Immediate conclusion

Keep `transcript_interacts_protein` and `transcript_interacts_gene` blocked for canonical promotion until source-specific endpoint audits pass. Add subtype-specific miRNA/lncRNA schema before ingesting mature miRNA and lncRNA target biology. The only safe near-term artifacts are source audit reports, staged passing rows, and context sidecars; no canonical KG writes are approved by this policy task.
