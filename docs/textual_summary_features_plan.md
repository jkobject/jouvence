# Textual summary features plan for KG nodes

Status: planning only; no production data ingest or scraping was performed.

This plan covers textual summary features for the major node types requested in Kanban task `t_a7b2c8f7`:

- `gene`
- `protein`
- `disease`
- `tissue`
- `molecule`
- `pathway`

It uses the access pattern from `docs/txgnn_access_runbook.md`: GCS is the canonical KG root at `gs://jouvencekb/kg/v2`, workers should copy only targeted Parquets into `.omoc/gcs-cache/kg-v2/`, query them with DuckDB/PyArrow, avoid depending on a FUSE mount, and never print cloud/Lamin credentials. For this planning card, only the six node Parquets were copied locally for schema/coverage inspection.

## 1. Current KG node state

Observed from cached copies of `gs://jouvencekb/kg/v2/nodes/{gene,protein,disease,tissue,molecule,pathway}.parquet` on 2026-06-21.

| node type | rows | main current sources | important current identifiers / text fields |
|---|---:|---|---|
| `gene` | 267,830 | OpenTargets/target.homologues 182,920; OpenTargets 54,457; NCBI 27,610; OpenTargets/expression 2,797; OpenTargets/europepmc 46 | `id` 267,830; `name` 240,220; `description` 212,029; `ncbi_gene_id` 27,610; `hgnc_id` 19,252; `uniprot_id` 1,850 |
| `protein` | 233,995 | OpenTargets 233,995 | `id` 233,995, mostly Ensembl protein IDs; `uniprot_id` 233,869; `ensembl_gene_id` 233,995; `name` 233,995 |
| `disease` | 41,859 | OpenTargets 26,395; MONDO 8,282; OpenTargets/evidence 4,598; OpenTargets/HPO 2,015; MONDO_grouped 569 | `name` 41,859; `description` 26,395; `mondo_id` 14,726; `mesh_id` 5,761; `omim_id` 4,981; `doid_id` 6,438; `hp_id` 1,020 |
| `tissue` | 16,061 | OpenTargets 16,061 | `id` 16,061, currently UBERON-style IDs in samples; `name` 16,061; no description column |
| `molecule` | 31,007 | OpenTargets 22,230; DrugBank 7,957; CTD 818; OpenTargets/pharmacogenomics 2 | `name` 22,232; `description` 22,230; `drugbank_id` 19,100; `inchikey` 22,230; `smiles` 22,230; no current `pubchem_cid` coverage |
| `pathway` | 48,575 | GO 26,798; OpenTargets 17,743; REACTOME 2,516; OpenTargets/evidence 1,518 | `name` 19,261; `go_id` 44,541; `reactome_id` 1,518; no description/summation column |

Implication: some current node Parquets already contain names/descriptions, but the coverage and source semantics are inconsistent. Textual summaries should be treated as a derived feature layer with provenance, not silently overwritten into canonical node identity files.

## 2. Recommended storage model

Recommended: keep canonical node Parquets mostly source-native and add a separate text feature layer.

Create one logical table per release, preferably as Parquet and optionally registered as LaminDB artifacts:

`features/text_summary_features.parquet`

Suggested schema:

| column | meaning |
|---|---|
| `node_type` | `gene`, `protein`, `disease`, `tissue`, `molecule`, `pathway` |
| `node_id` | canonical KG node `id` exactly as in `nodes/{node_type}.parquet` |
| `source` | e.g. `NCBI Gene`, `UniProtKB`, `MONDO`, `UBERON`, `PubChem`, `Reactome`, `GO` |
| `source_record_id` | source-native accession/ID used to fetch text |
| `source_url` | resolvable source/API URL, when allowed |
| `source_release` | release tag/date/API version, when available |
| `license` | license string or `requires_review` / `restricted` |
| `field` | source-native field name, e.g. `summary`, `cc_function`, `definition`, `summation.text`, `Record Description` |
| `summary_text` | cleaned source text, no embedding-specific prefix |
| `summary_text_hash` | content hash for drift detection |
| `language` | usually `en` |
| `retrieved_at` | timestamp of source retrieval |
| `priority` | integer priority for source selection when multiple summaries exist |
| `usable_for_embedding` | boolean gate after license/content checks |
| `notes` | short caveat, e.g. `DrugBank restricted; skipped text` |

Then create embedding input views/tables from this table rather than from node Parquets directly:

- `features/text_embedding_inputs.parquet`: one selected text per `(node_type, node_id, embedding_recipe)` with `input_text`, `input_hash`, `source_priority_trace`, and model-tokenization metadata.
- `features/text_embeddings/{model}/{release}.parquet`: vector outputs keyed by `node_type`, `node_id`, `input_hash`, and embedding model/version.

Why separate tables:

1. Avoids re-releasing canonical graph identity files every time summary text or embeddings update.
2. Keeps license/provenance attached to text features.
3. Allows multiple candidate summaries per node and deterministic prioritization.
4. Makes embedding refreshes and backfills easy to audit.
5. Fits LaminDB artifact tracking: raw source snapshots, feature tables, and embedding matrices can be independent artifacts with versions and hashes.

Node Parquets may later gain compact convenience columns such as `best_summary_source` and `best_summary_text_hash`, but should not store long text blobs as the canonical source of truth.

## 3. Source recommendations by node type

### 3.1 Gene summaries

Primary recommendation: do not use GeneCards as a default source unless Jérémie obtains and records an explicit license for this KG use case.

GeneCards notes:

- GeneCards pages expose rich gene summaries, but the website explicitly states that use requires a license except for non-profit academic institutions and hospitals.
- Treat scraping/reuse as unsafe for KG feature generation unless a license file/approval is stored in the project.
- If used under license later, ingest through a licensed export/API, not ad-hoc web scraping.

Recommended open/licensable alternatives:

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| NCBI Gene / RefSeq via E-utilities | primary for NCBI-backed human genes and other taxa with Entrez Gene records | NCBI E-utilities are public; NCBI/NLM says US-government-created public-domain content may be freely copied, but external linked content may have separate restrictions. Respect E-utilities rate limits and use an email/tool parameter in production. | KG `ncbi_gene_id` -> Entrez Gene UID. For current KG, direct coverage is 27,610 rows. | ESummary JSON field `result[uid].summary`, plus `name`, `description`, `organism`; sample BRCA1 summary is a paragraph with RefSeq provenance. | practical monthly or per KG release; source itself changes continuously | high for rows with `ncbi_gene_id`; low for homologues currently represented mainly through OpenTargets/Ensembl without NCBI IDs |
| OpenTargets Platform target data | fallback / existing source for Ensembl-backed targets | Verify OpenTargets Platform license before marking reusable for embeddings; likely acceptable for internal research but document exact release/license. | KG OpenTargets gene rows already have `id`, `name`, `description`; map by Ensembl target/gene IDs where preserved. | target `description` field; usually a concise gene/product description rather than a long biological summary. | align with OpenTargets releases | already present for 212,029 gene rows in current node table, but source and species mix need audit |
| Alliance of Genome Resources / model organism databases | optional non-human fallback | open data but each contributor source should be checked before broad redistribution | NCBI Gene / Ensembl / gene symbol / species mappings | gene synopsis / automated descriptions where available | per Alliance releases | useful for model organisms if KG keeps many homologues |
| HGNC | labels/aliases only, not a summary source | HGNC is suitable for nomenclature, not broad biological descriptions | `hgnc_id`, gene symbol | approved name/symbol, locus type | monthly-ish | ~19,252 current HGNC IDs |

Decision: implement NCBI Gene first for rows with `ncbi_gene_id`, preserve current OpenTargets descriptions as a lower-priority candidate after license confirmation, and explicitly skip GeneCards until licensed.

Recommended priority order:

1. Licensed GeneCards export, if and only if approved later.
2. NCBI Gene `summary` for rows with Entrez Gene IDs.
3. OpenTargets `description` already in the KG, after license/release annotation.
4. HGNC/Alliance labels only as fallback text fragments when no summary exists.

### 3.2 Protein summaries

Primary recommendation: UniProtKB.

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| UniProtKB REST API / downloads | primary protein text source | UniProt publishes open data with attribution/license terms; record exact license from UniProt `help/license` and cite UniProt in downstream artifacts. REST API supports field selection; bulk should use downloads or batched ID mapping rather than one request per row. | KG `uniprot_id` -> UniProt accession. Current coverage: 233,869 / 233,995 proteins have `uniprot_id`. `id` is often Ensembl protein ID; keep endpoint as Ensembl protein and text source as UniProt accession evidence. | `proteinDescription.recommendedName.fullName.value`; comments such as `FUNCTION`, `SUBUNIT`, `CATALYTIC ACTIVITY`, `MISCELLANEOUS`; each comment can carry ECO/PubMed evidence. | per UniProt releases; practical quarterly or KG-release aligned | near-complete for current protein rows by accession |
| OpenTargets protein/target metadata | fallback labels only | verify OpenTargets license/release | `ensembl_gene_id` / Ensembl protein IDs / UniProt xrefs | names and cross-reference-derived labels | per OpenTargets release | complete labels, weak summaries |

Decision: create protein text features from UniProt `FUNCTION` when present, prefixed with the recommended protein name. Preserve comment type and evidence codes in auxiliary provenance fields if possible.

Example normalized text shape:

`Breast cancer type 1 susceptibility protein (UniProt:P38398). Function: ...`

Do not project gene-level NCBI summaries into protein summaries unless the feature recipe explicitly says it is a cross-entity fallback. Protein text should remain protein-product evidence.

### 3.3 Disease summaries

Primary recommendation: MONDO definitions, with OpenTargets descriptions as an existing fallback.

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| MONDO | primary disease definition source | MONDO download page states OWL/OBO/JSON formats under CC BY 4.0. Prefer release downloads over per-term API calls for production. | KG `mondo_id` / `id` when `MONDO:*`; current direct `mondo_id` coverage 14,726 rows. Use xrefs (`mesh_id`, `omim_id`, `doid_id`, `hp_id`) only through a deterministic mapping table. | OBO/OWL `definition` / OLS `description`; concise disease definition. | per MONDO releases; practical monthly or KG-release aligned | good for MONDO-backed rows; partial for OpenTargets-only diseases |
| OpenTargets disease data | fallback for OpenTargets disease nodes | verify OpenTargets license/release and capture release tag | current `description` exists for 26,395 rows | disease description paragraph/string | per OpenTargets release | already covers 26,395 rows |
| Disease Ontology / HPO / OMIM / MeSH / Orphanet | fallback or xref expansion | licenses differ; OMIM has restrictions, MeSH is NLM, HPO open; do not merge text blindly across sources | map via current xref columns, with source priority and conflict handling | definitions/synonyms, usually concise | source-specific | useful for rows missing MONDO/OpenTargets text, but license gates vary |

Decision: primary disease feature source is MONDO definition for all rows mappable to MONDO IDs. Existing OpenTargets descriptions can be retained as lower-priority candidates with license/release metadata. Avoid OMIM text unless license reviewed; OMIM IDs can remain xrefs.

### 3.4 Tissue summaries

Primary recommendation: UBERON definitions via OBO/OWL/OLS.

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| UBERON | primary anatomical/tissue definition source | UBERON is an OBO Foundry ontology; check and record the exact release/license in the raw snapshot. Use release files for production; OLS is fine for spot checks. | KG `id` currently samples as `UBERON:*`; direct ID mapping should cover most/all tissue rows if all are UBERON. | OBO definition / OLS `description`; may also include xrefs to BTO, FMA, MeSH, EFO, UMLS and notes. | per ontology releases; practical monthly or KG-release aligned | likely high for the 16,061 tissue rows, pending full prefix audit |
| BRENDA Tissue Ontology (BTO), FMA, EFO | fallback for non-UBERON or extra context | license/source-specific; use only when source ID exists and terms are not covered by UBERON | future `bto_id`, `fma_id`, EFO xrefs; current columns exist but are empty in sampled current tissue table | concise definitions / labels | source-specific | low in current table unless xrefs are backfilled |
| Human Cell Atlas / HuBMAP ASCT+B | optional human-specific richer context | not canonical anatomy ontology replacement; license and context should be checked | UBERON/CL IDs where mapped | tissue/cell anatomy prose, often context-specific | source-specific | useful for later cell/tissue embeddings, not L3 MVP |

Decision: use UBERON definitions as tissue summaries. Keep the text concise; do not pull Wikipedia depictions or external definitions unless explicitly whitelisted, because OLS annotations can include mixed external source strings.

### 3.5 Molecule summaries

Primary recommendation: PubChem for open compound descriptions where available, with ChEMBL as structured metadata fallback. Do not use DrugBank text unless licensed.

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| PubChem PUG-View / PUG-REST | primary open molecule description source | PubChem is NCBI/NLM-hosted; record source-specific references embedded in PUG-View because sections can cite third-party sources. Use PUG-REST/PUG-View respectfully; production should batch by CID/InChIKey and cache responses. | Current KG has no `pubchem_cid` coverage but has `inchikey` and `smiles` for 22,230 OpenTargets molecules. Map InChIKey -> PubChem CID via PUG-REST, store CID and mapping evidence. | PUG-View `Record Description` / `Ontology Summary`, plus selected concise description fields with references; avoid noisy toxicity-only summaries when not generally descriptive. | PubChem changes continuously; practical quarterly or KG-release aligned | likely high for small molecules with InChIKey/SMILES; lower for biologics/drugs lacking public structure |
| ChEMBL | fallback structured source for bioactive molecules | ChEMBL web services and downloads are open, but exact license/reuse terms should be recorded from ChEMBL release docs. | Map by InChIKey, ChEMBL ID if added, DrugBank crossrefs if available. | `pref_name`, `molecule_type`, mechanism/indication tables from separate endpoints; not always a prose summary. | per ChEMBL releases | good for drug-like molecules, less useful for salts/mixtures/biologics |
| DrugBank | identifier/source only unless licensed | DrugBank is restricted; current KG has 19,100 `drugbank_id` values, but text should not be copied from DrugBank pages or downloads without license review. | `drugbank_id` direct | if licensed: description/indication/mechanism fields; otherwise skip text | licensed release-specific | high ID coverage but not safe as default text source |
| OpenTargets molecule descriptions | existing candidate fallback | verify OpenTargets license/release | current `description`, `inchikey`, `smiles` for 22,230 rows | description field | per OpenTargets release | already covers 22,230 rows |

Decision: first implementation should add a PubChem mapping/enrichment lane for rows with InChIKey/SMILES, retain OpenTargets molecule descriptions as lower-priority candidates after license annotation, and mark DrugBank text as `restricted_skip` unless a license is documented.

### 3.6 Pathway summaries

Primary recommendation: split by pathway ID namespace: GO definitions for GO terms, Reactome summations for Reactome stable IDs. Avoid KEGG descriptions unless licensed.

| source | role | license/API constraints | identifier mapping | summary field shape | update cadence | expected coverage |
|---|---|---|---|---|---|---|
| Gene Ontology (GO) | primary for `GO:*` pathway/process nodes | GO citation/license page should be recorded; GO terms are suitable for open ontology-derived definitions with attribution. Use OBO/OWL release downloads or OLS for spot checks. | KG `go_id` / `id` when `GO:*`; current `go_id` coverage 44,541 rows. | GO term `definition` / OLS `description`; concise biological-process/molecular-function/cellular-component text. | per GO releases; practical monthly or KG-release aligned | very high for GO-backed pathway rows |
| Reactome | primary for `R-HSA-*` pathway/event nodes | Reactome provides a Content Service API and a license page; record release/license and cite Reactome. | KG `reactome_id` / `id` for Reactome stable IDs; current direct coverage 1,518 rows with `reactome_id`, plus 2,516 source `REACTOME` rows. | `summation[].text` from Content Service, cleaned of HTML tags; `displayName` as label. Some lower-level events have no summation, so fallback to parent pathway summation may be needed. | Reactome releases regularly; practical quarterly or KG-release aligned | good for high-level pathways; partial for individual reactions/events |
| KEGG | xref only unless licensed | KEGG has a REST API but redistribution/licensing is restrictive for many uses. Do not use KEGG pathway descriptions as default text without license review. | future/current `kegg_id` if present; currently no non-null `kegg_id` in pathway table | pathway names/definitions if licensed | KEGG release-specific | not an MVP text source |
| OpenTargets pathway descriptions | fallback existing source | verify OpenTargets license/release | current source rows; GO IDs dominate | names/descriptions where present | per OpenTargets release | variable |

Decision: implement GO + Reactome as separate source adapters with namespace-specific logic. For Reactome, keep `summation.text` provenance and strip HTML only at the cleaned-text layer; retain raw text in source snapshots if licensed.

## 4. Cross-cutting implementation policy

### 4.1 License gates

Each source adapter must emit a license status before `usable_for_embedding=true`:

- `open_verified`: source license recorded in adapter config and compatible with this KG use.
- `requires_review`: source seems usable but exact license/reuse terms were not captured in the implementation PR.
- `restricted_skip`: source should not be copied into feature tables by default.

Initial gate recommendations:

| source | initial gate |
|---|---|
| NCBI Gene / RefSeq ESummary | `open_verified`, with NCBI attribution/disclaimer and rate-limit compliance |
| UniProtKB | `open_verified` after recording current UniProt license text/version |
| MONDO | `open_verified` under CC BY 4.0 |
| UBERON | `requires_review` until exact release license is captured from the ontology snapshot, then likely open |
| GO | `requires_review` until exact license is captured from the GO release/citation policy, then likely open |
| Reactome | `requires_review` until exact license is captured from Reactome license page/release, then likely open |
| PubChem | `requires_review` because PUG-View sections can include third-party references; store per-section references |
| ChEMBL | `requires_review` until exact release license is recorded |
| OpenTargets | `requires_review` until exact Platform release/license is recorded |
| GeneCards | `restricted_skip` unless licensed |
| DrugBank | `restricted_skip` unless licensed |
| KEGG | `restricted_skip` unless licensed |
| OMIM prose | `restricted_skip` unless licensed; IDs/xrefs are fine |

### 4.2 Text cleaning and provenance

- Preserve source-native raw fields in source snapshots when licensing allows; generate cleaned `summary_text` separately.
- Strip HTML tags from Reactome summations and similar sources, but do not erase citations if they are part of the evidence trail.
- Do not concatenate every available field blindly. A noisy, long text blob is worse for embeddings than a concise curated definition.
- Keep labels, aliases, xrefs, definitions, functional summaries, and evidence citations as separate fields until the final embedding-input recipe.
- Hash cleaned text to detect source drift and avoid unnecessary embedding regeneration.

### 4.3 Mapping rules

- Source-native endpoint semantics apply. A gene summary is not a protein summary; a protein summary is not a gene summary.
- Use direct IDs first: Entrez Gene for NCBI, UniProt accession for UniProt, MONDO ID for MONDO, UBERON ID for UBERON, CID/InChIKey for PubChem, GO ID for GO, Reactome stable ID for Reactome.
- Crosswalks must be persisted as evidence/mapping tables with source, date, and collision handling.
- One-to-many mappings should produce multiple candidate summaries only if the source records are genuinely distinct; do not pick arbitrary first hits.
- Obsolete ontology terms should not produce embedding text unless the node is explicitly retained as legacy and the summary marks it obsolete.

### 4.4 Update cadence

Default cadence: regenerate text features on each KG release and no more often than monthly unless a source-specific release motivates it. Embeddings should regenerate only when `(summary_text_hash, embedding_recipe, embedding_model)` changes.

Recommended schedule:

- Monthly ontology refresh: MONDO, UBERON, GO.
- Quarterly / KG-release refresh: UniProt, Reactome, PubChem/ChEMBL/OpenTargets.
- NCBI Gene: monthly or KG-release aligned; avoid high-frequency per-row API churn.
- Licensed/restricted sources: only on approved licensed release imports.

## 5. Implementation cards

These are proposed follow-up Kanban cards; this planning card does not create them automatically unless an orchestrator wants to fan them out.

### Card T1: Create text feature schema and source registry

Assignee suggestion: KG/data-engineering worker.

Deliverables:

- Add `manage_db/text_features.py` or equivalent module defining `TextSummaryFeature` schema and adapter interface.
- Add `docs/text_feature_source_registry.md` with per-source license status, API/download URL, citation string, release metadata fields, and gate (`open_verified`, `requires_review`, `restricted_skip`).
- Add tests for required columns and duplicate `(node_type,node_id,source,source_record_id,field)` handling.

Acceptance:

- A toy in-memory build writes and reads a valid `text_summary_features.parquet`.
- License gate prevents `restricted_skip` rows from being selected into embedding inputs.

### Card T2: Implement ontology summary adapters for MONDO, UBERON, and GO

Assignee suggestion: KG ontology worker.

Deliverables:

- Download or read release OBO/OWL/JSON snapshots for MONDO, UBERON, GO into `.omoc/gcs-cache/kg-v2/raw/text-sources/` or a controlled GCS scratch path.
- Parse definitions/descriptions for direct KG IDs.
- Emit feature rows with source release, license, source record ID, and definition text.
- Report coverage for `disease`, `tissue`, and GO-backed `pathway` nodes.

Acceptance:

- No per-term production API loop; use release files or cached snapshots.
- Coverage report includes unmapped IDs and obsolete/missing terms.

### Card T3: Implement UniProt protein summary adapter

Assignee suggestion: protein/KG worker.

Deliverables:

- Use UniProt downloads or batched REST/API mapping to fetch fields for current `protein.uniprot_id` values.
- Extract recommended protein name and selected comments (`FUNCTION` first; optionally `CATALYTIC ACTIVITY`, `SUBUNIT`, `MISCELLANEOUS` as separate candidate fields).
- Preserve evidence code/PubMed metadata when available.

Acceptance:

- Coverage report over 233,869 current UniProt-accessioned protein nodes.
- No projection of gene-level text into protein rows.

### Card T4: Implement NCBI Gene summary adapter and GeneCards guardrail

Assignee suggestion: gene/KG worker.

Deliverables:

- Batch Entrez Gene ESummary for `gene.ncbi_gene_id` values with rate limiting and contact/tool metadata.
- Emit summaries with RefSeq/NCBI provenance and retrieved date.
- Add explicit test/config guard that GeneCards adapter is disabled unless a license file/path is configured.
- Optionally normalize existing OpenTargets gene descriptions into lower-priority candidate features after license review.

Acceptance:

- Coverage report over 27,610 current NCBI-backed gene nodes.
- GeneCards is not scraped and cannot be accidentally selected by default.

### Card T5: Implement molecule text source review and PubChem pilot

Assignee suggestion: molecule/KG worker.

Deliverables:

- Review and record exact PubChem, ChEMBL, OpenTargets, and DrugBank license statuses in the source registry.
- Build a small PubChem pilot mapping InChIKey -> CID for a sample of OpenTargets molecules; inspect PUG-View `Record Description` fields and references.
- Decide final PubChem section whitelist for general molecule summaries.
- Mark DrugBank text as restricted unless a license exists.

Acceptance:

- Pilot is small and cached; no bulk scrape.
- The report distinguishes open descriptions from third-party referenced text.

### Card T6: Implement Reactome pathway summary adapter

Assignee suggestion: pathway/KG worker.

Deliverables:

- Fetch Reactome release/download data or use Content Service in a cached, respectful batch mode.
- Extract `summation[].text` for pathway stable IDs; strip HTML into cleaned text while retaining raw/source refs.
- Handle lower-level events with missing summations by either leaving them unmapped or using a documented parent-pathway fallback recipe.

Acceptance:

- Coverage report for `reactome_id` and `source='REACTOME'` pathway rows.
- GO and Reactome text features remain separate sources, not merged into a generic pathway description without provenance.

### Card T7: Build embedding input selector

Assignee suggestion: ML/data worker.

Deliverables:

- Deterministic selection function from candidate text features to one or more embedding recipes.
- Recipe examples:
  - `summary_primary_v1`: best open verified source only.
  - `summary_plus_label_v1`: label + best summary.
  - `multi_source_concat_v1`: controlled concatenation of two source fields with source tags.
- Input hash and model metadata support.

Acceptance:

- Selector excludes `restricted_skip` and `requires_review` sources unless explicitly allowed.
- Outputs stable Parquet suitable for embedding jobs and LaminDB artifact registration.

## 6. Source references checked during planning

Official/reference URLs consulted or probed lightly during this planning card:

- A0 local runbook: `docs/txgnn_access_runbook.md`
- NCBI E-utilities help: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- NCBI/NLM policies: https://www.ncbi.nlm.nih.gov/home/about/policies/
- NCBI Gene ESummary example: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=672&retmode=json
- UniProt REST API example: https://rest.uniprot.org/uniprotkb/P38398.json
- UniProt help/API and license pages: https://www.uniprot.org/help/api and https://www.uniprot.org/help/license
- MONDO download/license page: https://mondo.monarchinitiative.org/pages/download/
- OLS MONDO term example: https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FMONDO_0007254
- UBERON site: https://obophenotype.github.io/uberon/
- OLS UBERON term example: https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FUBERON_0002107
- PubChem PUG-REST documentation: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- PubChem PUG-View example: https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/2244/JSON?heading=Record+Description
- ChEMBL web services/docs: https://chembl.gitbook.io/chembl-interface-documentation/web-services and https://chembl.gitbook.io/chembl-interface-documentation/downloads
- DrugBank terms page attempted but returned 403 from this worker: https://go.drugbank.com/legal/terms_of_use
- Reactome license and Content Service pages: https://reactome.org/license and https://reactome.org/ContentService/
- Reactome Content Service examples: https://reactome.org/ContentService/data/query/R-HSA-109581 and https://reactome.org/ContentService/data/query/R-HSA-1640170
- Gene Ontology citation/license page: https://geneontology.org/docs/go-citation-policy/
- OLS GO term example: https://www.ebi.ac.uk/ols4/api/ontologies/go/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FGO_0006915
- KEGG REST API manual: https://www.kegg.jp/kegg/rest/keggapi.html

## 7. Final recommendation

Use open ontology/database summaries as a provenance-rich feature layer, not as untracked long-text columns in node Parquets.

MVP source set:

1. `gene`: NCBI Gene summaries for Entrez-backed genes; existing OpenTargets descriptions only after license/release annotation; no GeneCards scraping.
2. `protein`: UniProtKB recommended names + `FUNCTION` comments.
3. `disease`: MONDO definitions first; OpenTargets descriptions as fallback after license annotation.
4. `tissue`: UBERON definitions.
5. `molecule`: PubChem pilot first, ChEMBL/OpenTargets fallback after license review; no DrugBank text by default.
6. `pathway`: GO definitions for GO IDs and Reactome summations for Reactome IDs; no KEGG text by default.

This keeps the KG legally cleaner, more reproducible, and easier to embed/refit without corrupting canonical node semantics.
