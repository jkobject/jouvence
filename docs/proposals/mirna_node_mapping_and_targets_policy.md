# miRNA node mapping and target-source policy

Status: proposal/source audit only. No miRNA catalog or target-source data were ingested for this document.

This proposal answers the A4 audit question: how miRNA identities should coexist with existing Ensembl transcript nodes, and how validated miRNA target sources should map to future KG relations without duplicating biological entities or projecting source endpoints beyond what was measured.

## Executive recommendation

1. Reuse existing `transcript` nodes when a source identity maps 1:1 to an existing Ensembl transcript (`ENST...`). Add miRBase/RNAcentral identifiers as aliases/xrefs or a separate mapping table; do not create duplicate nodes for the same transcript entity.
2. Add miR-primary nodes only for entities that are distinct from the existing ENST transcript node: mature miRNA products and, if needed, precursor/hairpin entities. Mature miRNA products are not the same thing as an Ensembl transcript record.
3. Do not pick or infer a "main transcript" for a gene. A gene can have many transcript isoforms and RNA products; each transcript/product gets its own mapping evidence.
4. For target sources, use the target endpoint measured by the source:
   - source row names a target gene / Entrez / HGNC / Ensembl gene -> `mirna_targets_gene` or `mirna_regulates_gene` after relation naming is approved;
   - source row names a transcript, 3'UTR isoform, transcript-specific site, or source-native ENST/RefSeq transcript endpoint -> `mirna_targets_transcript` / `mirna_regulates_transcript`;
   - do not create protein target edges from protein readout assays unless the source gives a protein/isoform endpoint and the protein mapping policy is approved.
5. Keep prediction-only and ceRNA/correlation resources as candidate/correlative evidence or features unless a separate predicted/correlative relation is explicitly approved.

Preferred naming for the next schema tranche: use `mirna_targets_gene` and `mirna_targets_transcript` if the relation is intended to mean target-site/support evidence broadly, including weak/curated target evidence; use `mirna_regulates_gene` / `mirna_regulates_transcript` only if the relation is restricted to regulation/effect assertions. Existing docs contain both names; this proposal uses `targets` for the audited target-source policy and notes that final naming needs a schema gate.

## Current KG transcript representation

Inspected local canonical cache plus targeted GCS copies under `.omoc/gcs-cache/kg-v2` on 2026-06-21:

- `nodes/transcript.parquet`: 507,365 rows copied from `gs://jouvencekb/kg/v2/nodes/transcript.parquet`.
- `edges/gene_has_transcript.parquet`: 507,365 rows copied from `gs://jouvencekb/kg/v2/edges/gene_has_transcript.parquet`.
- `docs/kg_schema_overview.md` reports `transcript` as a canonical node type with primary namespace Ensembl (`ENST00000380152`) and 507,365 rows.
- `manage_db/kg_schema.py` defines `NodeType.TRANSCRIPT` with primary ontology `Ensembl`, ID format `ENST<11digits>`, and xref columns `ensembl_gene_id`, `protein_id`, `refseq_mrna`, and `ccds_id`.

Actual `nodes/transcript.parquet` columns:

```text
id, name, ensembl_gene_id, protein_id, refseq_mrna, ccds_id, source
```

Current transcript node behavior:

- `id`/`name` are ENST IDs.
- `ensembl_gene_id` stores the parent ENSG.
- `protein_id` stores an ENSP only when the transcript has a translation product.
- `refseq_mrna` and `ccds_id` exist but are currently null in sampled OpenTargets-built rows.
- `source` is `OpenTargets`.
- There is no transcript-node `biotype` column in the current Parquet, despite `sync_parquet_nodes_to_lamindb.py` being prepared to read `biotype` / `transcript_biotype` if present.
- There are no miRBase/RNAcentral/MIMAT/MI/hsa-miR alias columns on transcript nodes.

The OpenTargets builder in `manage_db/ingest_opentargets.py` creates transcript nodes from `target.transcripts[*].transcriptId`, stores `translationId` as `protein_id`, and writes transcript biotype only on the `gene_has_transcript` edge as `transcript_biotype`.

Observed miRNA-biotype representation:

- `edges/gene_has_transcript.parquet` has `transcript_biotype`.
- `transcript_biotype == miRNA`: 1,879 edges / 1,879 unique ENST transcript nodes.
- These miRNA-biotype transcript nodes have no `protein_id`, as expected for noncoding RNA.
- Parent genes are ENSG nodes; joined `nodes/gene.parquet` examples include gene symbols like `MIR494`, `MIRLET7E`, `MIR375`, `MIR30E`, `MIRLET7A2`, `MIR429`.
- Parent gene node `biotype` is only partially populated for these rows: 1,058 joined parent genes have `biotype == miRNA`; 821 have null `biotype` in the local cache.

Implication: the current KG already has Ensembl transcript nodes for many miRNA-biotype transcripts, but they are ENST transcript records, not mature miRNA product nodes, and they currently lack source aliases needed for miRBase target resources.

## Entity model: gene, transcript, precursor, mature miRNA

Keep these biological layers separate:

1. `gene` (`ENSG...`): genomic gene locus / Ensembl target gene. Example parent genes: `MIR494`, `MIR375`. A gene is not a single transcript and must not have a selected "main transcript" for miRNA mapping.
2. `transcript` (`ENST...`): Ensembl transcript record. Existing transcript nodes include miRNA-biotype transcripts and link to parent genes via `gene_has_transcript`.
3. precursor/hairpin miRNA: miRBase hairpin entity, usually `MI...` accession and name such as `hsa-mir-*`. This may correspond to a genomic/transcribed precursor, but exact one-to-one mapping to ENST must be proved per row/release.
4. mature miRNA: processed mature product, usually `MIMAT...` accession and mature name such as `hsa-miR-*-5p` / `hsa-miR-*-3p`. This is a regulatory molecule/product, not simply an ENST transcript.

Recommended node labels/fields if separate miR-primary nodes are required:

### Option A: one `mirna` node type with product level

Use one node type and distinguish mature vs precursor with fields. This is simpler for graph export and fits the ~2k human mature-miRNA scale.

Primary fields:

```text
id                         # primary ID; prefer MIMAT... for mature rows, MI... for precursor rows if precursor nodes are included
name                       # hsa-miR-... or hsa-mir-...
mirna_product_type          # mature | precursor_hairpin
species_id                  # NCBITaxon:9606 / 9606
mirbase_mature_accession    # MIMAT... when mature
mirbase_mature_name         # hsa-miR-... when mature
mirbase_precursor_accession # MI... when known
mirbase_precursor_name      # hsa-mir-... when known
ensembl_gene_id             # parent ENSG if mapped
ensembl_transcript_id       # ENST if true 1:1 mapping or best mapping with confidence retained
rnacentral_id               # URS... if available
sequence                    # optional; release-pinned
source                      # miRBase/RNAcentral/etc.
source_release              # release/version
mapping_confidence          # exact | many_to_one | name_only | inferred | unresolved
mapping_method              # source crossref | sequence/coordinate | name normalization | manual curation
```

### Option B: two node types, `mature_mirna` and `mirna_precursor`

Use this only if downstream algorithms need different node types for processed products vs hairpins. Fields are similar to Option A but relation `mirna_precursor_produces_mature_mirna` becomes mandatory.

Recommended fields for `mature_mirna`:

```text
id = MIMAT accession when available
name = hsa-miR-... arm-specific mature name
mirbase_mature_accession
mirbase_mature_name
arm = 5p | 3p | unknown
species_id
precursor_id / mirbase_precursor_accession
ensembl_gene_id
ensembl_transcript_id (nullable; only mapped with evidence)
rnacentral_id
sequence
source, source_release, mapping_confidence, mapping_method
```

Recommended fields for `mirna_precursor`:

```text
id = MI accession when available
name = hsa-mir-...
mirbase_precursor_accession
mirbase_precursor_name
species_id
ensembl_gene_id
ensembl_transcript_id (nullable; only mapped with evidence)
rnacentral_id
sequence
source, source_release, mapping_confidence, mapping_method
```

Default recommendation: start with Option A (`mirna` + `mirna_product_type`) unless a reviewer explicitly wants separate mature/precursor node types. It avoids schema sprawl while preserving product-level identity.

## Mapping policy

### Existing ENST transcript maps 1:1 to miRBase/hsa-miR identity

If a source/release provides a true one-to-one mapping between an existing ENST transcript node and a miRBase precursor/hairpin identity, do not create a duplicate node for that same transcript identity. Add mapping metadata as one of:

- new transcript xref columns if compact and stable (`mirbase_precursor_accession`, `mirbase_precursor_name`, `rnacentral_id`);
- a separate mapping table such as `mappings/transcript_mirbase.parquet` if one ENST can map to multiple source IDs or if mapping confidence/provenance needs row-level detail;
- evidence rows supporting a future `transcript_maps_to_mirna`/alias registry if graph-level mapping is needed.

Required mapping fields:

```text
ensembl_transcript_id
ensembl_gene_id
mirbase_accession
mirbase_name
mirbase_entity_type            # precursor_hairpin | mature | ambiguous
rnacentral_id
mapping_method                 # source_xref | coordinate_overlap | sequence_identity | name_normalization | manual
mapping_confidence             # exact | high | medium | low | unresolved
source_dataset
source_release
source_record_id
species_id
notes_json
```

### Mature miRNA or precursor/hairpin is distinct from ENST

Create miR-primary nodes when the entity is a processed mature miRNA product or a precursor/hairpin that is not identical to an existing ENST transcript node. This is especially important for arm-specific mature products: `hsa-miR-*-5p` and `hsa-miR-*-3p` can share a precursor/gene but have different target biology.

Do not collapse mature miRNA target edges onto parent ENSG gene nodes; the regulator endpoint should be the mature miRNA when the source reports mature miRNA names/accessions.

### Ambiguous name-only mappings

If a source gives only a symbol/name (`miR-21`, `hsa-miR-21-5p`, `MIR21`) and no stable accession:

- normalize to the exact release of miRBase/RNAcentral used for the node catalog;
- keep the original source string in evidence;
- set mapping confidence explicitly;
- do not silently merge deprecated names, family-level names, or arm-less names into arm-specific mature nodes without release-pinned resolution.

## Target-source audit: miRTarBase and DIANA-TarBase

### miRTarBase

Prior repo source audit classifies miRTarBase as `recommended`: experimentally validated miRNA-target interactions (MTIs) with support such as reporter assay, western blot, qPCR, microarray/NGS, CLIP/Ago-related evidence, and other support classes. Endpoint facts in existing docs: miRNA IDs/names from miRBase/MIMAT/MI naming; target fields are usually gene-level identifiers or gene symbols depending on release; species is available; web automation previously hit HTTP 412, so implementation must re-check exact release, schema, and license manually before download.

Policy:

- Use as the first validated target source after miRNA node mapping is approved.
- Default target relation: `mirna_targets_gene` / `mirna_regulates_gene` for rows whose target endpoint is a gene symbol, Entrez Gene, HGNC, or Ensembl gene.
- Use `mirna_targets_transcript` only for rows that directly identify transcript/UTR isoform/site endpoints, or where the source gives target-site coordinates that are explicitly mapped to a transcript with retained mapping evidence.
- Keep protein-effect assays (for example western blot readout) as evidence fields, not as `mirna_targets_protein`, unless the row has a protein/isoform endpoint and the protein endpoint mapping is approved.

### DIANA-TarBase

Prior repo source audit classifies DIANA-TarBase v8 as `recommended`: manually curated experimentally supported miRNA-gene interactions. TarBase v8 is described in NAR 2018 (PMID:29156006). Existing docs say endpoint fields are miRNA names/IDs, target genes, species, and usually gene identifiers rather than transcript/protein endpoints; methods/context include experimental method, cell/tissue/cell line, regulation direction, validation type, PMID, and source record.

Policy:

- Use as the second validated target source, complementary to miRTarBase.
- Default target relation: `mirna_targets_gene` / `mirna_regulates_gene` unless an exact TarBase release row provides transcript/UTR/site endpoints.
- Preserve method/context fields row-by-row; do not collapse support types into separate relation names.
- If miRTarBase and TarBase contain overlapping assertions, deduplicate graph edges by `(mirna_id, target_id, relation)` but keep separate evidence rows for each source record.

## Relation placement rules

### `mirna_targets_gene`

Use when source target endpoint is gene-level:

- target symbol, Entrez Gene, HGNC, Ensembl gene, or source-specific target gene ID;
- assay measures down-regulation, reporter activity, target-gene expression, broad MTI support, or curated target relation without transcript-specific endpoint;
- source does not distinguish target transcript isoform/site sufficiently.

Edge shape:

```text
x_id = mature miRNA node ID, preferably MIMAT... or approved `mirna` primary ID
x_type = mirna
y_id = ENSG...
y_type = gene
relation = mirna_targets_gene or mirna_regulates_gene
source = miRTarBase / DIANA-TarBase / ...
credibility = curated/experimental-derived value
```

### `mirna_targets_transcript`

Use only when source target endpoint is transcript/site-native:

- source gives ENST, RefSeq transcript, transcript-specific 3'UTR, isoform-specific target site, or equivalent;
- coordinate-to-transcript mapping is approved and evidence records preserve assembly, coordinates, site, and mapping confidence;
- do not expand a gene-level target row to all transcripts of that gene.

Edge shape:

```text
x_id = mature miRNA node ID
y_id = ENST... existing transcript node ID when mapped
relation = mirna_targets_transcript or mirna_regulates_transcript
```

### What not to do

- Do not represent mature miRNAs as generic `gene` nodes for target edges.
- Do not use parent `MIR*` gene symbol as a substitute for a mature arm-specific miRNA product when the source reports `hsa-miR-*-5p` / `3p`.
- Do not create one target edge per transcript from a gene-level target row.
- Do not create `mirna_targets_protein` or `mirna_regulates_protein` merely because an assay measured protein abundance; protein readout is evidence unless the target endpoint is source-native protein/isoform.
- Do not merge prediction-only target databases with experimentally validated targets without `prediction_only` / `evidence_type` flags and an explicit predicted-edge policy.

## Evidence fields to preserve

Every source-derived miRNA target edge should have `evidence/{relation}.parquet` rows. Required or recommended fields:

```text
relation
x_id, x_type, y_id, y_type
edge_key
source
source_dataset                 # miRTarBase, DIANA-TarBase, release-specific channel
source_version / source_release
source_record_id
original_mirna_id
original_mirna_name
original_mirna_id_namespace    # miRBase mature, hairpin, source name, etc.
mirna_mapping_method
mirna_mapping_confidence
original_target_id
original_target_name
target_id_namespace            # Entrez, HGNC, ENSG, ENST, RefSeq, site/coordinate
target_mapping_method
target_mapping_confidence
species_id / species_name
assay                          # reporter, western blot, qPCR, microarray, NGS, CLIP/Ago, etc.
support_type                   # strong/weak/functional/non-functional if source provides it
evidence_type                  # experimental_validated, curated, predicted, correlative, candidate
predicate                      # targets, represses, downregulates, validated_target, no_effect, etc.
regulation_direction           # down, up, no_change, unknown
sign_or_effect                 # repression/activation/effect size if available
target_region                  # 3UTR, CDS, 5UTR, promoter, unspecified
target_site_id
chromosome, start, end, strand, genome_assembly
seed_match / site_type / binding_site_sequence
pmid / paper_id
cell_line
cell_type
tissue
disease_context
treatment / condition
confidence
score / p_value / effect_size
source_url
license_checked
raw_metadata_json
```

For validated-source overlap, keep one graph edge but many evidence rows; source-specific rows are not duplicates.

## ceRNA prediction policy

ceRNA resources describe competing endogenous RNA hypotheses: lncRNAs, circRNAs, pseudogenes, or mRNAs may compete for shared miRNAs, often in cancer- or tissue-specific contexts. These signals frequently combine target prediction, expression correlation, differential expression, survival/disease association, and sometimes limited perturbation support.

Recommendation:

- Treat ceRNA rows as candidate/correlative/contextual evidence by default.
- Do not load ceRNA predictions into `mirna_targets_gene`, `mirna_targets_transcript`, or `transcript_interacts_gene` as if they were direct mechanism edges.
- If a ceRNA-specific schema is later approved, model it separately as a context-specific RNA-RNA regulatory hypothesis, with disease/tissue/cell context and prediction/correlation support fields preserved.
- Rows with direct experimental validation of a miRNA->target interaction may support miRNA target evidence; the ceRNA axis/correlation itself remains contextual evidence.

Suggested evidence labels:

```text
evidence_type = candidate_ceRNA | correlative_ceRNA | experimentally_supported_ceRNA
prediction_only = true/false
context_required = true
```

## Recommended builder tasks

No ingestion should proceed from this proposal directly. Create separate review/implementation cards after schema approval.

1. Schema/naming gate for miRNA entities and target relations.
   - Decide `mirna` single node type vs `mature_mirna` + `mirna_precursor`.
   - Decide final relation names: `mirna_targets_*` vs `mirna_regulates_*`.
   - Add schema docs/tests only; no Parquets expected.
2. Existing transcript-miRBase mapping audit.
   - Build a release-pinned mapping table from miRBase/RNAcentral/Ensembl xrefs.
   - Quantify exact / many-to-one / unresolved mappings against existing 1,879 miRNA-biotype ENST transcript nodes.
   - Add aliases/xrefs to transcript nodes only when mappings are exact and review-approved.
3. miRNA node catalog pilot.
   - Build `nodes/mirna.parquet` (or selected node types) from miRBase/RNAcentral after license check.
   - Preserve mature/precursor IDs, arm, species, sequence, source release, and parent ENSG/ENST mappings.
4. miRTarBase source audit card.
   - Manually check license/terms and exact release download format.
   - Inspect raw schema and sample rows; enumerate species, support/assay types, endpoint namespaces, and source IDs.
   - Decide which rows qualify as validated human target evidence.
5. DIANA-TarBase source audit card.
   - Check license/terms and release format.
   - Inspect raw schema/sample rows; enumerate method/context fields and endpoint namespaces.
6. Validated target builder card.
   - Build staged `mirna_targets_gene` first for validated human MTIs with gene endpoints.
   - Build `mirna_targets_transcript` only for source-native transcript/site endpoints; no gene-to-all-transcripts expansion.
   - Materialize evidence together with edges.
7. Optional ceRNA/context card.
   - Audit ENCORI/starBase/LncACTdb-style ceRNA resources separately.
   - Keep as features/evidence unless a context-specific relation is approved.

## Validation gates

Before promoting any miRNA tranche:

1. License/citation gate passes for every source release.
2. Raw schema audit is saved under `docs/` or `.omoc/reports/` with row counts and representative fields.
3. Node endpoint anti-joins pass:
   - all target `gene` IDs exist in `nodes/gene.parquet`;
   - all target `transcript` IDs exist in `nodes/transcript.parquet` if transcript relation is built;
   - all miRNA IDs exist in the approved miRNA node file.
4. Mapping confidence is explicit; name-only or deprecated mappings do not silently merge.
5. Evidence support audit passes: every non-ontology graph edge has at least one evidence row with source record and support type.
6. No gene-level target row is expanded to all transcript isoforms.
7. No protein relation is created from RNA/gene endpoints or assay readout alone.
8. Prediction-only and ceRNA/correlative rows are excluded from canonical target edges unless a predicted/candidate relation is explicitly approved.
9. `manage_db/kg_schema.py`, `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, tests, and coverage reports are updated in the same implementation tranche.

## Sources and local artifacts inspected

- `manage_db/kg_schema.py`: transcript node primary namespace and xref policy.
- `manage_db/ingest_opentargets.py`: OpenTargets target builder; transcript nodes from `target.transcripts[*].transcriptId`; `transcript_biotype` stored on `gene_has_transcript` edges.
- `docs/kg_schema_overview.md`: canonical node/edge counts and relation policy.
- `docs/source_measure_edge_matrix.md`: source-native endpoint doctrine and prior S1 miRNA policy rows.
- `docs/later_node_edge_families_plan.md`: later-family miRNA node/edge plan.
- `docs/proposals/source_native_transcript_rna_interaction_sources.md`: prior transcript/RNA source audit including miRTarBase, DIANA-TarBase, ENCORI/starBase, and ceRNA resource policy.
- `.omoc/gcs-cache/kg-v2/nodes/transcript.parquet`: copied targeted canonical transcript node file for schema/sample inspection.
- `.omoc/gcs-cache/kg-v2/edges/gene_has_transcript.parquet`: copied targeted canonical edge file for transcript biotype counts.
