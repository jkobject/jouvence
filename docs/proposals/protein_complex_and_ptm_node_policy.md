# Proposal: protein complex nodes and PTM site/event node policy

Date: 2026-06-21

Status: proposal only; source audit only. No data was ingested, no schema code was changed, and no Parquet files were produced for this card.

## Executive decision

Add `protein_complex` and `ptm_site` only as source-native node families, not as projections from the existing gene-level graph.

Recommended policy:

1. Use `protein_complex` for named, stable molecular complexes from complex-native sources. Start with Complex Portal human complexes; treat BioGRID complex downloads as recommended after raw subset inspection; use Reactome complex entities as crossrefs/hierarchy/evidence, not as generic pathway expansion; put CORUM behind a license/manual-terms gate.
2. Use `ptm_site` only for site-level modified residue assertions. The node identity must include parent protein, residue/position, and modification type. Vague protein-level PTM statements stay as protein feature/evidence rows, not nodes.
3. Materialize membership and PTM edges only with evidence tables. The graph edge should stay broad (`protein_part_of_complex`, `protein_has_ptm_site`, `protein_modifies_ptm_site`), while source-specific fields carry complex assembly, stoichiometry, modification vocabulary, assay, evidence code, PMIDs, source record IDs, release, and endpoint mapping provenance.
4. Do not infer complex disease/phenotype edges from member protein disease edges. Do not infer site disease/phenotype edges from “protein has disease” + “protein has PTM”. Those are derived features at best unless a source directly asserts the complex/site link.
5. Keep the existing `protein` endpoint policy: canonical KG protein IDs are Ensembl Protein (`ENSP...`) with UniProt/neXtProt/RefSeq accessions as xrefs. Complex/PTM source rows usually start as UniProt accessions and must be resolved to existing `nodes/protein.parquet` IDs before promotion.

This refines the earlier planning in `docs/later_node_edge_families_plan.md` and aligns with `docs/proposals/source_native_protein_interaction_sources.md`: source-native complex/PTM assertions are acceptable mechanism additions, but implementation must be gated before ingestion.

## Existing schema context reviewed

Current active schema (`manage_db/kg_schema.py`, `docs/kg_schema_overview.md`) contains these relevant facts:

- Active node types stop at `protein`, `pathway`, `mutation`, `enhancer`, etc.; there is no active `protein_complex` or `ptm_site` node type yet.
- `protein` uses Ensembl Protein as primary namespace, with `uniprot_id`, `refseq_protein`, and `pdb_ids` as xrefs.
- `protein_interacts_protein` is active in schema but has no canonical Parquet yet; it is reserved for direct protein/isoform interaction evidence, not projections from `gene_interacts_gene`.
- `pathway_contains_protein` is active but explicitly source-native only; complex membership should not be smuggled through pathway membership if a complex-specific node is needed.
- `disease_associated_protein` exists for protein-native disease association evidence; it does not justify projecting disease associations onto complexes or PTM sites.
- The later-family plan already proposed `protein_complex` and `ptm_site` but left exact node fields, relation evidence, and staged builder gates to this audit.

The existing relation name in the later plan is `protein_part_of_protein_complex`. For brevity and consistency with the user-facing requested name, this document recommends `protein_part_of_complex` if schema maintainers are willing to introduce the shorter name; otherwise keep `protein_part_of_protein_complex` as the code-facing relation and document `protein_part_of_complex` as the display relation. Do not maintain both as separate biological relations.

## Source audit: protein complexes

### Complex Portal

Classification: recommended first source.

Observed during this audit from `https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/9606.tsv`:

- HTTP status 200, `text/tab-separated-values`.
- Human complextab rows: 2,498.
- Columns: `#Complex ac`, `Recommended name`, `Aliases for complex`, `Taxonomy identifier`, `Identifiers (and stoichiometry) of molecules in complex`, `Evidence Code`, `Experimental evidence`, `Go Annotations`, `Cross references`, `Description`, `Complex properties`, `Complex assembly`, `Ligand`, `Disease`, `Agonist`, `Antagonist`, `Comment`, `Source`, `Expanded participant list`.
- Member count from `Identifiers (and stoichiometry) of molecules in complex`: min 1, max 54, mean 4.04.
- Example row: `CPX-1`, SMAD2-SMAD3-SMAD4 complex, members `P84022(1)|Q13485(1)|Q15796(1)`, ECO evidence code, disease `-`.

Mechanism fit:

- Cleanest first release for named human molecular complexes.
- Directly supports `protein_complex` nodes and `protein_part_of_complex` membership evidence.
- Supports nested complex membership only if participant fields explicitly identify complex participants; do not infer nesting from member overlap.
- Disease field can support `protein_complex_associated_disease` only when it is populated and maps to existing disease nodes with evidence. Sparse/blank disease fields mean no disease edge.

Endpoint policy:

- Primary complex node ID: `CPX-...`.
- Protein participants: UniProt accessions in member fields; map to canonical `protein` ENSP IDs via existing protein xrefs before graph promotion.
- Preserve original UniProt accessions and stoichiometry even after mapping.

License/access notes:

- EMBL-EBI/Complex Portal is open enough for an implementation pilot, but the builder should record exact terms/citation for the release before canonical promotion.

### BioGRID complexes

Classification: recommended with strict subset/raw-schema gate.

Observed from the BioGRID download page during this audit:

- Download repository is live.
- Page states data are freely available to academic and commercial users under the MIT License.
- Page explicitly says it provides additional custom formats for post-translational modifications, chemical interactions, and complexes.

Mechanism fit:

- Use only explicit BioGRID complex files/subsets, not generic BioGRID physical interaction pairs expanded into complexes.
- Good candidate as a second source after Complex Portal, especially for coverage and publication-backed support.
- BioGRID IDs, Entrez IDs, symbols, UniProt/Swiss-Prot/Trembl accessions, experimental systems, throughput, qualifications, tags, ontology terms, and publication source should remain in evidence.

Gates before building:

1. Download/cache only the exact BioGRID complex release/subset in scratch.
2. Inspect the raw complex file header and representative rows.
3. Verify whether participant endpoints are protein accessions, BioGRID IDs, Entrez IDs, or mixed.
4. Promote only participant rows with direct protein endpoint support or auditable UniProt→ENSP mapping.
5. Keep BioGRID source IDs/publication fields in `evidence/protein_part_of_complex.parquet`.

### Reactome complexes

Classification: candidate support/crossref source, not first primary complex catalog.

Mechanism fit:

- Reactome represents complexes and reactions/pathways, but the current KG already uses Reactome heavily for `pathway` and `pathway_contains_gene`.
- Use Reactome complex IDs as crossrefs, hierarchy, or supporting evidence for Complex Portal/BioGRID complex nodes when mappings are explicit.
- Reactome participants can support complex membership only if the source row is a complex membership assertion, not merely pathway co-membership.

Policy:

- Do not turn all Reactome pathways into `protein_complex` nodes.
- Do not load every pathway participant as `protein_part_of_complex`; use `pathway_contains_protein` only for protein-native pathway membership if a separate card approves it.
- If Reactome complex entities become nodes, use a separate reconciliation strategy: either map to Complex Portal/CORUM IDs when available or use `ReactomeComplex:<stable_id>` as a source-specific fallback with `reactome_id` xref.

### CORUM

Classification: maybe after license/manual-terms gate.

Mechanism fit:

- CORUM is biologically strong for mammalian protein complexes and can increase coverage beyond Complex Portal.
- It is not the first implementation source because redistribution/license automation is less obvious than Complex Portal/BioGRID.

Policy:

- Treat CORUM as a second-pass audit source.
- Before ingestion, record terms of use, release date, species filtering, member endpoint namespace, complex ID stability, and duplicate reconciliation against Complex Portal.
- If approved, use as additional evidence or new nodes only after deduplication policy is explicit.

### SIGNOR complexes / IntAct complex rows

Classification: contextual support.

Mechanism fit:

- SIGNOR has complex/family entities and explicit mechanism/regulation rows; it is excellent for directed regulation and may contain complex participants.
- IntAct/MITAB can include stoichiometry/features/expansion method and complex-like rows, but it is primarily an interaction evidence source.

Policy:

- Use SIGNOR/IntAct complex information as evidence only unless the exact download is a complex membership table.
- Complex/family endpoints must not be forced into protein endpoints. If a row has a complex endpoint and no active complex node exists, keep it as evidence or defer until `protein_complex` is active.

## `protein_complex` node model

Recommended node file: `nodes/protein_complex.parquet`.

Primary ID policy:

- First release primary namespace: Complex Portal accession (`CPX-...`).
- Optional future fallback namespaces only after reconciliation: `CORUM:<id>`, `R-HSA:<stable_id>` for Reactome complex entities, `BIOGRID-COMPLEX:<id>` if BioGRID has stable complex IDs that cannot map to Complex Portal.
- Do not use free-text complex names as primary IDs.

Minimum columns:

| Column | Required? | Meaning |
| --- | --- | --- |
| `id` | yes | Canonical complex ID, initially Complex Portal `CPX-...`. |
| `name` | yes | Recommended/display name. |
| `description` | recommended | Source description/summary. |
| `organism_id` | yes | NCBI taxonomy CURIE, e.g. `NCBITaxon:9606`. |
| `source` | yes | Primary node source for this row, e.g. `complex_portal`. |
| `source_record_id` | yes | Original source accession/record ID. |
| `complex_portal_id` | yes for first release | Complex Portal accession. |
| `corum_id` | optional | CORUM crossref when mapped. |
| `reactome_id` | optional | Reactome crossref when mapped. |
| `biogrid_complex_id` | optional | BioGRID stable complex ID if available. |
| `go_id` | optional | GO complex/component/function xref when source supplies it. |
| `aliases` | optional | Pipe-separated or JSON aliases. |
| `stoichiometry_json` | recommended | Source-level aggregate stoichiometry if stable; per-member stoichiometry still belongs in evidence. |
| `assembly` | optional | Complex assembly field/source vocabulary. |
| `ligand_ids` | optional | Source ligand references if present; do not model as edges until molecule endpoint policy is approved. |
| `disease_xrefs` | optional | Raw disease xrefs/labels from source; not a disease edge by itself. |
| `release` | yes | Source release/date downloaded. |
| `license` | recommended | Source license/terms note. |

Node deduplication policy:

- The node row is a stable biological complex assertion from a primary source. Evidence rows can merge multiple sources onto the same complex only when crossrefs or curated mapping support the merge.
- Same name + overlapping members is not enough to collapse complexes automatically. Store candidate duplicates in a reconciliation report first.
- Complexes with one listed member are allowed only if source treats them as complexes/assemblies; otherwise implementation should review whether they are artifacts, families, or monomeric entities.

## `protein_part_of_complex` relation and evidence

Recommended edge: `protein_part_of_complex` (`protein` → `protein_complex`, kind `physical`, direct `true`).

If the codebase keeps the longer name from `docs/later_node_edge_families_plan.md`, use `protein_part_of_protein_complex` internally and set display relation to `protein_part_of_complex`. Pick one canonical relation name before implementation.

Edge row minimum:

- `x_id`: canonical ENSP protein ID.
- `x_type`: `protein`.
- `y_id`: canonical complex ID.
- `y_type`: `protein_complex`.
- `relation`: canonical relation name.
- `display_relation`: `part of complex`.
- `source`: source family, e.g. `complex_portal`.
- `credibility`: usually 3 for curated complex membership, adjusted if source/evidence is weak.

Evidence file: `evidence/protein_part_of_complex.parquet`.

Evidence columns:

| Column | Meaning |
| --- | --- |
| `edge_key` / relation keys | Support link to edge row. |
| `source` | Source family. |
| `source_dataset` | Exact table/file, e.g. `complex_portal_complextab_9606`, `biogrid_complexes`. |
| `source_record_id` | Complex accession/record ID. |
| `source_complex_id` | Original complex ID. |
| `source_complex_name` | Original complex name. |
| `source_participant_id` | Original participant accession/ID. |
| `source_participant_namespace` | UniProt, BioGRID, Entrez, Reactome, etc. |
| `mapped_protein_id` | Canonical ENSP ID. |
| `mapping_method` | How participant was resolved to ENSP. |
| `mapping_confidence` | Exact xref, reviewed UniProt match, ambiguous, etc. |
| `stoichiometry` | Source stoichiometry for this participant if present. |
| `participant_role` | Role/component type if source supplies it. |
| `evidence_code` | ECO/PSI-MI/source evidence code. |
| `experimental_evidence` | Source experimental evidence text/IDs. |
| `pmids` | Source PMIDs, normalized as `PMID:...` list. |
| `go_annotations` | GO annotations attached to complex/membership if present. |
| `crossrefs` | Raw source crossrefs. |
| `complex_assembly` | Source assembly field. |
| `release` | Source release/date. |
| `license` | License/terms note. |
| `raw_json` | Lossless raw/source fields for future repair. |

Do not create pairwise `protein_interacts_protein` from complex co-membership unless a later card explicitly builds a derived projection for an algorithm that needs it. Complex membership is not identical to direct binary physical interaction.

## Source audit: PTM sites and events

### UniProtKB PTM features

Classification: recommended first source for site catalog / protein feature pilot.

Observed during this audit from UniProt REST:

- Query: reviewed human proteins with `ft_mod_res:*` returned `x-total-results: 9491`.
- Existing later-family plan recorded 20,431 reviewed human proteins, 9,491 reviewed human proteins with PTM features, 5,330 with disease comments, and 3,338 with both.

Mechanism fit:

- Best open first source for curated human protein feature annotations, including modified residues/sites.
- Directly supports `protein_has_ptm_site` if the source feature has a residue/range and modification type.
- Disease comments alone do not support site→disease edges unless the source explicitly links the disease/variant/effect to that site.

Endpoint policy:

- UniProt accession is a source ID/xref; canonical graph source endpoint remains ENSP `protein` after mapping.
- Preserve isoform/accession/feature location because canonical ENSP mapping can lose isoform nuance.

License/access:

- UniProtKB is the preferred open source. Implementation should record exact UniProt release and CC BY 4.0 attribution.

### BioGRID PTM subsets

Classification: recommended with strict role/site gate.

Observed from BioGRID page:

- BioGRID provides custom downloads for post-translational modifications and uses MIT License terms according to the download page.

Mechanism fit:

- Valuable for PTM event evidence because BioGRID PTM rows can identify modifier/substrate, modification type, experimental system, author/publication, throughput, score, qualifications, tags, source database, accessions, and ontology terms.
- Supports `protein_modifies_ptm_site` only when the row identifies the modifying protein/enzyme and the substrate/site or at least substrate protein + modification type.
- If site position/residue is missing, do not create a `ptm_site` node. Model it as a protein-level PTM event evidence row or defer.

Gates before building:

1. Inspect exact BioGRID PTM header and sample rows.
2. Determine whether interactor A/B roles are enzyme/substrate, substrate/modifier, or merely participants.
3. Require site-level residue/position for `ptm_site` node creation.
4. Preserve experimental system, ontology term IDs/names/categories/qualifiers, modification field, publication source, and throughput.
5. Keep rows without role/site clarity out of `protein_modifies_ptm_site`; they can support a future protein-level PTM feature/evidence table.

### SIGNOR phosphorylation / directed mechanism rows

Classification: recommended for directed mechanism evidence after source approval.

Mechanism fit:

- SIGNOR rows expose directed entity A/B, effect, mechanism, residue/sequence, PMID, direct flag, sentence, score, and relation ID.
- Excellent candidate for `protein_modifies_ptm_site` and/or `protein_regulates_protein` when both endpoints are proteins and the mechanism is phosphorylation/ubiquitination/etc. with target site information.
- Complex/family endpoints should wait for active complex/family nodes or remain evidence.

Policy:

- Use `protein_modifies_ptm_site` when target site is explicit.
- Use `protein_regulates_protein` when directed protein regulation is explicit but site is absent/vague.
- Preserve effect/sign, directness, mechanism, residue/sequence, PMIDs, sentence, cell/tissue context, and SIGNOR ID in evidence.

### Reactome PTM/mechanism events

Classification: candidate, event-modeling gate needed.

Mechanism fit:

- Reactome reactions can encode modified proteins and catalyst/activity context, but translating this into site nodes/events requires careful event semantics.
- Good support for pathway/reaction context, not necessarily a clean global kinase-substrate site catalog.

Policy:

- Do not ingest Reactome PTM events until a separate card defines event extraction from reactions, physical entities, catalysts, and modified residues.
- If used, preserve reaction ID, catalyst/activity, compartment, pathway, modified residue, and evidence.

### neXtProt PTMs

Classification: historical supplemental only.

Observed during this audit:

- The neXtProt about page states that after 14 years, neXtProt reached end of life and no longer provides data or services; archived data remain accessible via Zenodo/source archives.

Mechanism fit:

- Useful as archived supplemental annotation if exact release/version is pinned.
- Not recommended as a primary live source because it is no longer updated.

Policy:

- Use only after UniProt/BioGRID/SIGNOR pilot if archived neXtProt adds fields not otherwise available.
- Preserve archive DOI/release and mark source status as historical.

### PhosphoSitePlus / dbPTM / kinase-substrate databases

Classification: defer behind license/source approval.

Mechanism fit:

- These are biologically valuable for phosphosite and kinase-substrate relations.
- They should not be used until redistribution/commercial/internal-use constraints are reviewed.

Policy:

- Create a separate approval card before any implementation.
- If approved, they likely feed `ptm_site`, `protein_has_ptm_site`, and `protein_modifies_ptm_site` with richer site and enzyme evidence.

## PTM modeling policy

PTM assertions come in at least four levels. Do not collapse them into one graph shape.

| Source assertion level | Example | Graph handling |
| --- | --- | --- |
| Site-level modified residue | `UniProt P31749 MOD_RES 308 phosphothreonine` | Create/reuse `ptm_site`; add `protein_has_ptm_site`. |
| Directed enzyme→site event | `AKT1 phosphorylates substrate S473` with residue/position | Create/reuse `ptm_site`; add `protein_modifies_ptm_site`. |
| Directed enzyme→protein modification, no site | `kinase phosphorylates substrate protein`, site unknown | Do not create `ptm_site`; use `protein_regulates_protein` or event evidence if mechanism/direction is strong. |
| Vague protein has PTM / protein is modified | `protein is phosphorylated`, no residue/position | Feature/evidence table only; no PTM node. |
| Site/disease or site/phenotype link | disease/phenotype explicitly tied to site/modified residue | Add `ptm_site_associated_disease` or `ptm_site_associated_phenotype` only with direct support. |

Recommended `ptm_site` identity:

- Canonical ID: deterministic composite over canonical protein + modification type + residue + position + isoform when needed.
- Suggested format: `PTMSITE:<protein_id>:<modification_type_normalized>:<residue><position>` for canonical ENSP-level rows.
- If isoform-specific and no safe ENSP canonical position exists, include isoform/source accession: `PTMSITE:UniProtKB:<accession>:<mod_type>:<residue><position>` until mapping is resolved.
- Do not key only by UniProt feature ID if that ID is release-local/unstable; keep it as `source_feature_id`.

Recommended `ptm_site` columns:

| Column | Required? | Meaning |
| --- | --- | --- |
| `id` | yes | Canonical PTM site ID. |
| `protein_id` | yes | Canonical ENSP protein ID when resolvable. |
| `protein_id_namespace` | yes | Usually `Ensembl Protein`; source fallback if unresolved in staging. |
| `uniprot_accession` | recommended | Original/source UniProt accession. |
| `isoform` | optional | Isoform accession or label if source-specific. |
| `residue` | yes for site nodes | One-letter residue code if known. |
| `position` | yes for site nodes | Amino-acid coordinate in source sequence. |
| `end_position` | optional | For modified ranges; same as position for single residues. |
| `modification_type` | yes | Normalized label, e.g. `phosphorylation`, `glycosylation`. |
| `modification_label` | recommended | Source label, e.g. `Phosphothreonine`. |
| `psi_mod_id` | optional | PSI-MOD / controlled vocabulary ID when available. |
| `site_label` | recommended | Human-readable site label, e.g. `T308`. |
| `sequence_context` | recommended | Flanking sequence if source provides or if reproducibly computed. |
| `source_ids` | yes | JSON/list of source feature/record IDs. |
| `pmids` | optional | Publication IDs directly supporting the site. |
| `evidence_level` | recommended | Curated/predicted/inferred/source-specific level. |
| `release` | yes | Source release/date for first source creating node. |
| `raw_json` | optional | Source fields needed for repair/reconciliation. |

PTM nodes should be sparse and useful. A massive UniProt feature catalog can also be stored as `features/protein_ptm_site.parquet`; promote to graph nodes when the site participates in disease/phenotype/mechanism edges or when downstream models explicitly need site nodes.

## PTM relations and evidence

### `protein_has_ptm_site`

Relation: `protein` → `ptm_site`, kind `physical` or `central_dogma`-adjacent feature relation, direct `true`.

Use when:

- Source has site-level residue/range on a specific protein/isoform.
- Protein endpoint maps to canonical ENSP or is kept in staging until mapping is repaired.

Evidence columns:

| Column | Meaning |
| --- | --- |
| `source`, `source_dataset`, `source_record_id` | Exact source and record/feature ID. |
| `source_protein_id`, `source_protein_namespace` | UniProt/neXtProt/BioGRID/etc. original endpoint. |
| `mapped_protein_id`, `mapping_method`, `mapping_confidence` | ENSP mapping provenance. |
| `feature_type` | Source feature class, e.g. `MOD_RES`, glycosylation. |
| `modification_type`, `modification_label`, `psi_mod_id` | Normalized and source modification labels. |
| `residue`, `position`, `end_position`, `site_label`, `sequence_context` | Site details. |
| `evidence_code`, `evidence_level` | ECO/source evidence level. |
| `pmids` | Site-supporting publications. |
| `release`, `license`, `raw_json` | Reproducibility and repair fields. |

### `protein_modifies_ptm_site`

Relation: `protein` → `ptm_site`, kind `regulatory`, direct `true`.

Use when:

- Source identifies a modifying enzyme/controller protein and a substrate PTM site.
- Direction is source-native and roles are explicit.
- Site-level residue/position is present or can be losslessly mapped from source fields.

Do not use when:

- Source only says two proteins interact.
- Source says a protein is modified but not who modifies it.
- Source gives a kinase-substrate protein pair with no site and no site-resolvable evidence; use `protein_regulates_protein` or evidence-only until site policy is clear.

Evidence columns:

| Column | Meaning |
| --- | --- |
| `source`, `source_dataset`, `source_record_id` | Exact source row. |
| `modifier_source_id`, `modifier_namespace`, `modifier_protein_id` | Enzyme/controller endpoint and mapping. |
| `substrate_source_id`, `substrate_namespace`, `substrate_protein_id` | Substrate endpoint and mapping. |
| `ptm_site_id` | Target PTM site node. |
| `mechanism` | Phosphorylation, ubiquitination, acetylation, etc. |
| `effect`, `sign`, `direction` | Activation/inhibition/up/down/unknown if source supplies it. |
| `directness` | Direct/indirect/source flag. |
| `residue`, `position`, `site_label`, `sequence_context` | Site details. |
| `assay`, `experimental_system`, `ontology_terms` | Method/system fields. |
| `pmids`, `supporting_sentence` | Literature evidence. |
| `cell_context`, `tissue_context`, `organism_id` | Context fields if present. |
| `score`, `confidence`, `throughput` | Source support metrics. |
| `release`, `license`, `raw_json` | Reproducibility and repair fields. |

### `protein_regulates_protein` fallback for PTM mechanisms without site

If the source is directed and mechanistic but site-vague, use `protein_regulates_protein` rather than fabricating a PTM node. Evidence must carry `mechanism=phosphorylation` or equivalent, source roles, direction/sign, PMIDs, and raw fields.

### Disease/phenotype links

Candidate relations:

- `ptm_site_associated_disease`: `ptm_site` → `disease`, kind `disease_assoc`, direct `false` unless source asserts causality.
- `ptm_site_associated_phenotype`: `ptm_site` → `phenotype`, kind `phenotype_assoc`, direct `false` unless source asserts causal phenotype effect.
- `protein_complex_associated_disease`: `protein_complex` → `disease`, kind `disease_assoc`.
- `protein_complex_associated_phenotype`: `protein_complex` → `phenotype`, kind `phenotype_assoc`.

Use only when source-backed at the complex/site level.

Allowed examples:

- Complex Portal row has a disease annotation for a named complex and maps to EFO/MONDO.
- UniProt/neXtProt/ClinVar/literature row explicitly ties a modified residue/site or variant affecting a PTM site to a disease/phenotype.
- SIGNOR or a curated disease mechanism source directly states a disease-relevant PTM site event.

Rejected examples:

- Member protein has `disease_associated_protein`; therefore complex has disease.
- Protein has many PTM sites and protein has disease; therefore every site has disease.
- Disease pathway contains complex; therefore complex has disease.
- Variant overlaps site and disease locus without explicit site consequence; keep as contextual feature until reviewed.

## Recommended schema lifecycle

Start as candidate definitions, not immediate canonical Parquet expectations.

Suggested additions in a schema-only card:

1. Add `NodeType.PROTEIN_COMPLEX` with primary ontology `Complex Portal`, example `CPX-1`, xrefs `corum_id`, `reactome_id`, `biogrid_complex_id`, `go_id`.
2. Add `NodeType.PTM_SITE` with primary ontology `Composite PTM site ID`, example `PTMSITE:ENSP00000369497:phosphorylation:T308`, xrefs `uniprot_accession`, `source_feature_id`, `psi_mod_id`.
3. Add candidate relations first:
   - `protein_part_of_complex` or `protein_part_of_protein_complex` (`protein` → `protein_complex`, physical, direct).
   - `protein_complex_part_of_complex` (`protein_complex` → `protein_complex`, physical/ontological, direct) only for explicit nested complexes.
   - `protein_has_ptm_site` (`protein` → `ptm_site`, direct feature/molecular relation).
   - `protein_modifies_ptm_site` (`protein` → `ptm_site`, regulatory, direct).
   - `ptm_site_associated_disease` and `ptm_site_associated_phenotype` as candidates only.
   - `protein_complex_associated_disease` and `protein_complex_associated_phenotype` as candidates only.
4. Keep candidate relation definitions outside `RELATIONS` until a builder card actually produces edge/evidence files or validators know not to require Parquets for candidate rows.

## Staged builder tasks

### Stage A5-S1: schema-only proposal implementation

Goal: add node/relation candidates and docs, no data.

Acceptance:

- `manage_db/kg_schema.py` compiles.
- Docs explain primary namespaces and xref columns.
- Tests that enumerate schema names are updated.
- No new canonical Parquets expected.

### Stage A5-S2: Complex Portal pilot

Goal: build first source-backed complex nodes/membership in staging.

Steps:

1. Cache release-pinned `complextab/9606.tsv` under `.omoc/gcs-cache/kg-v2/raw/complex-portal/<release>/`.
2. Build `nodes/protein_complex.parquet` from `CPX-...` rows.
3. Parse `Identifiers (and stoichiometry) of molecules in complex` and `Expanded participant list`.
4. Resolve UniProt participants to canonical ENSP `protein` nodes.
5. Build staged `edges/protein_part_of_complex.parquet` and `evidence/protein_part_of_complex.parquet` together.
6. Report unresolved/ambiguous UniProt→ENSP mappings and one-member complex rows.
7. Do not build complex disease/phenotype edges unless disease fields are populated and mapped with evidence.

Validation:

- Node ID uniqueness and required columns.
- Endpoint anti-join: all membership proteins exist in `nodes/protein.parquet`; all complexes exist in `nodes/protein_complex.parquet`.
- Evidence support audit: every membership edge has at least one evidence row.
- Raw row count, member count distribution, mapping loss report.

### Stage A5-S3: BioGRID complexes/PTM source audit

Goal: exact raw schema audit before build.

Steps:

1. Download exact latest or release-pinned BioGRID complex and PTM custom files to scratch/cache.
2. Record release, URL, license text, headers, species counts, row counts, endpoint namespaces, modification fields, and publication columns.
3. Classify rows as:
   - `complex_membership_ready`,
   - `ptm_site_ready`,
   - `ptm_event_site_ready`,
   - `ptm_event_no_site`,
   - `protein_pair_only`,
   - `reject_or_feature_only`.
4. Ask for approval before implementation if the subset semantics are not obvious.

Validation:

- No graph build in this stage.
- Markdown audit report with sample rows and recommended filters.

### Stage A5-S4: UniProt PTM feature pilot

Goal: decide and stage PTM site catalog from UniProt.

Steps:

1. Download reviewed human UniProtKB entries with PTM feature fields and release metadata.
2. Parse site/range, modification label/type, evidence codes, PMIDs, isoform qualifiers, sequence context if available.
3. Resolve accessions/isoforms to canonical ENSP proteins; report mapping loss and ambiguous mappings.
4. Initially build `features/protein_ptm_site.parquet` or staged `nodes/ptm_site.parquet` + `edges/protein_has_ptm_site.parquet` depending on model need.
5. Do not build disease/phenotype PTM edges unless source evidence explicitly links disease/phenotype to that site.

Validation:

- PTM site ID determinism and uniqueness.
- Required site fields present for node rows (`protein`, `residue`, `position`, `modification_type`).
- Endpoint anti-join against protein nodes.
- Evidence support for every graph edge if graph promotion is chosen.

### Stage A5-S5: SIGNOR/BioGRID directed PTM event pilot

Goal: build `protein_modifies_ptm_site` only for directed site-level events.

Steps:

1. Use source rows with explicit modifier/substrate roles and mechanism.
2. Require site-resolvable target for `protein_modifies_ptm_site`; otherwise route to `protein_regulates_protein` or evidence-only.
3. Preserve directness, effect/sign, mechanism, assay, context, PMIDs, source relation IDs, and source sentence where available.
4. Avoid canonical sorting; modifier is source, PTM site is target.

Validation:

- All modifier proteins and PTM sites exist.
- Directionality/source role audit on sample rows.
- Evidence support audit.

### Stage A5-S6: disease/phenotype edge audit only

Goal: decide if complex/site disease/phenotype edges are justified.

Steps:

1. Count and sample Complex Portal disease fields, mapped disease IDs, and evidence codes.
2. Inspect UniProt/BioGRID/SIGNOR/neXtProt disease/site assertions for direct site-level links.
3. Produce a report separating direct source-backed links from derived overlaps.
4. Build only after review approval.

Validation:

- No member-protein disease projection.
- No generic protein disease + PTM join.
- Evidence rows include disease/phenotype mapping provenance.

## Implementation red lines

- No ingestion from this proposal card.
- No gene→protein projection for PTM/complex relations.
- No complex inference from pairwise PPI overlap.
- No disease/phenotype projection from member proteins or generic protein-level disease.
- No PTM node without residue/position/modification type unless explicitly modeled as an event/feature table instead.
- No source-specific relation explosion; source specificity belongs in evidence.
- No restricted/licensed PTM databases until a separate approval card records terms.

## Validation checklist for future builders

- Source release, URL, license, and citation captured.
- Raw schema/header and sample rows inspected before relation naming.
- Endpoint namespaces classified before mapping.
- UniProt/neXtProt/BioGRID/Reactome IDs mapped to canonical ENSP proteins with loss report.
- Complex/PTM nodes built before edges.
- Edge/evidence files built together.
- Endpoint anti-joins pass.
- `manage_db.audit_edge_evidence` passes for new non-derived edges.
- `docs/kg_schema_overview.md`, `docs/source_measure_edge_matrix.md`, coverage reports, and tests updated in the same implementation tranche.
- Restricted or prediction-only rows stay in feature/context tables unless approval and evidence semantics justify graph edges.
