# Textual summary feature expansion plan

Task: `t_76c42ace`

This is a source/implementation plan for expanding node textual descriptions. Text remains a model feature under `features/`, not a KG biological assertion, edge, or evidence row.

It preserves the feature-table contract from `docs/textual_summary_features.md`:

```text
feature_key, feature_table, node_id, node_type, summary_kind, summary_text,
source, source_dataset, source_record_id, provenance, license, citation,
release, created_at
```

Validation remains:

- `node_id` anti-joins cleanly against the matching canonical node table.
- `node_type` matches the feature-table contract.
- `summary_text` is non-empty and bounded by `max_text_chars`.
- duplicate rows are deduplicated by `(feature_table, node_id, source, source_dataset, source_record_id, summary_kind)`.
- feature tables are staged under `features/`; no `edges/`, `evidence/`, or canonical writes.

Machine-readable source matrix: `.omoc/reports/textual_summary_feature_source_matrix.json`.

## Local node/source audit

Local node cache inspected: `.omoc/gcs-cache/kg-v2/nodes`.

| Node type | Local nodes | Existing table | Expansion decision |
|---|---:|---|---|
| gene | 267,830 | `gene_textual_summary` | Keep existing OpenTargets/upstream description path; no GeneCards. |
| protein | 233,995 | `protein_textual_summary` | Build full UniProtKB comments beyond the 100-accession pilot. |
| disease | 41,859 | `disease_textual_summary` | Keep OpenTargets/EFO/MONDO descriptions; defer Orphanet until exact terms. |
| tissue | 16,061 | `tissue_textual_summary` | Keep UBERON `def` fields. |
| molecule | 31,007 | `molecule_textual_summary` | Keep ChEMBL/OpenTargets fields; no DrugBank text scraping. |
| pathway | 48,575 | `pathway_textual_summary` | Keep GO definitions; add Reactome descriptions from an accepted Reactome dump/API. |
| cell_type | 3,513 | new `cell_type_textual_summary` | Build now from Cell Ontology `def` fields. |
| phenotype | 16,449 | new `phenotype_textual_summary` | Build now from HPO definitions for current HP nodes; MP/EFO/MONDO only when nodes carry those namespaces. |
| cell_line | 1,183 | new `cell_line_textual_summary` | Build now from local Cellosaurus OBO comments using DepMap ACH xrefs. |
| organism | 1 | new optional `organism_textual_summary` | Low priority; build only a source-backed NCBI Taxonomy one-row table if consumers want it. |
| dataset | absent in local cache | defer | No local node table in inspected cache; define only after dataset nodes are canonical/staged. |
| paper | absent in local cache | defer | No local node table in inspected cache; use PubMed/OpenAlex/Crossref only after node provenance policy is set. |

## Per-node source decisions

### Existing accepted tables retained

#### Gene (`gene_textual_summary`)

- Decision: keep current staged table.
- Source: OpenTargets target node descriptions, preserving upstream Ensembl/NCBI/HGNC attribution where available.
- License/terms: OpenTargets open data plus upstream attribution; existing `SOURCE_POLICY["OpenTargets"]` is conservative: `CC BY 4.0 / upstream source attribution`.
- Mapping: canonical `nodes/gene.parquet.id`; description column when present/non-empty.
- Expected coverage from staged pilot: 212,029 / 267,830 endpoint nodes (79.17%).
- Reject/defer: GeneCards remains rejected for scraping/redistribution.

#### Disease (`disease_textual_summary`)

- Decision: keep current staged table.
- Source: OpenTargets disease descriptions, preserving upstream EFO/MONDO ontology attribution where available.
- License/terms: OpenTargets open data plus EFO/MONDO attribution where known.
- Mapping: canonical `nodes/disease.parquet.id`; description column when present/non-empty.
- Expected coverage from staged pilot: 26,395 / 41,859 endpoint nodes (63.06%).
- Reject/defer: Orphanet remains deferred until the exact API/product terms and allowed redistribution form are reviewed.

#### Tissue (`tissue_textual_summary`)

- Decision: keep current staged table.
- Source: UBERON `def` fields from `.omoc/gcs-cache/kg-v2/raw/uberon/uberon-basic.obo`.
- Source release observed locally: `uberon/releases/2026-04-01/uberon-basic.owl`.
- License/terms: OBO Foundry / UBERON attribution; represented in code as `CC BY 4.0 / ontology attribution`.
- Mapping: `nodes/tissue.parquet.id` CURIE to UBERON term id.
- Expected coverage from local OBO: 11,942 / 16,061 endpoint nodes (74.35%).

#### Molecule (`molecule_textual_summary`)

- Decision: keep current staged table.
- Source: ChEMBL-derived OpenTargets drug molecule metadata.
- License/terms: ChEMBL/OpenTargets attribution; existing code labels ChEMBL as `CC BY-SA 3.0`.
- Mapping: canonical `nodes/molecule.parquet.id`; description column when present/non-empty.
- Expected coverage from staged pilot: 22,230 / 31,007 endpoint nodes (71.69%).
- Reject/defer: DrugBank textual scraping remains rejected/deferred unless Jérémie provides a separate license/terms basis. Existing DrugBank identifiers may remain IDs only; do not redistribute DrugBank descriptions.

### Build now

#### Protein full UniProtKB (`protein_textual_summary`)

- Decision: build now; expand the pilot to all mapped protein nodes/accessions.
- Source: UniProtKB comments: `FUNCTION`, `SUBCELLULAR LOCATION`, `PTM`, `CATALYTIC ACTIVITY`, and `PATHWAY`.
- License/terms: UniProtKB is accepted with attribution under CC BY 4.0 in `SOURCE_POLICY`.
- Source release: read from the UniProt payload when available (`payload.release`); otherwise use CLI `--release`.
- Mapping strategy: collect all distinct accessions from `nodes/protein.parquet.uniprot_id`, splitting pipe-delimited values; fetch/read UniProtKB JSON entries keyed by accession; emit one row for each canonical protein node mapped to that accession.
- Expected coverage: upper bound is the number of protein nodes with at least one `uniprot_id`; local node table has 233,995 protein rows. Actual row coverage depends on which accessions have accepted comment blocks. Pilot produced 228 mapped rows from 100 accessions, so full run should be orders of magnitude larger but must report exact coverage after build.
- Builder changes needed:
  - keep existing `rows_from_uniprot_entries` contract;
  - add a non-scraping batch fetch/input helper for all accessions, preferably writing raw JSON pages under `.omoc/raw/uniprot/<release>/` before staging;
  - support pagination/retry/backoff and deterministic resume;
  - preserve current `--uniprot-entries-json` test/pilot path so tests remain offline;
  - add a summary count for distinct accessions requested, entries returned, entries with accepted comments, and protein-node rows emitted.
- Test changes needed:
  - extend `tests/test_build_textual_summary_features.py` with multiple accessions, pipe-delimited `uniprot_id`, unmapped accession, and missing-comment entry cases;
  - assert release propagation from payload;
  - assert no placeholder table is written when no acceptable comment rows exist.

#### Cell type (`cell_type_textual_summary`)

- Decision: build now.
- Source: Cell Ontology / CL OBO `def` fields from `.omoc/raw/cell_ontology/cl.obo`.
- Source release observed locally: `releases/2026-06-08`.
- License/terms: OBO Foundry/CL ontology attribution; should be added to `SOURCE_POLICY` as `allow_with_attribution`, `CC BY 4.0 / ontology attribution` after confirming the exact CL header/license metadata in the source file or release page.
- Mapping strategy: `nodes/cell_type.parquet.id` is already CL CURIE (`CL:...`); parse non-obsolete CL terms with `def` and join on id.
- Expected coverage measured locally: 3,135 / 3,513 cell_type nodes (89.24%).
- Builder changes needed:
  - add `cell_type_textual_summary` to `allowed_textual_summary_tables()` / `_TEXTUAL_SUMMARY_TABLE_TYPES`;
  - add `SOURCE_POLICY["Cell Ontology"]` or `SOURCE_POLICY["CL"]`;
  - add `OBO_SOURCE_DEFAULTS["cell_type"]` with `summary_kind="cell_type_definition"`;
  - add CLI arg `--cl-obo` and call `rows_from_obo_definitions(node_root, "cell_type", cl_obo, source_key="cell_type")`.
- Test changes needed:
  - fixture `cell_type.parquet` with a CL id and `cl.obo` term;
  - assert table appears under `features/cell_type_textual_summary.parquet` and endpoint validation catches misses.

#### Phenotype (`phenotype_textual_summary`)

- Decision: build now for HPO-backed phenotype nodes; prepare MP/EFO/MONDO support but only emit rows for namespaces present in `nodes/phenotype.parquet`.
- Source: HPO OBO `def` fields from `.omoc/gcs-cache/kg-v2/raw/hpo/hp.obo` for current HP nodes.
- Source release observed locally: `hp/releases/2026-06-06`.
- License/terms: HPO license URL appears in the local header as `https://hpo.jax.org/app/license`; use with attribution and preserve release/license URL in rows. Do not assume CC BY unless confirmed by the HPO license text.
- Mapping strategy: current phenotype ids are HP CURIEs (`HP:...`); join `nodes/phenotype.parquet.id` to HPO term ids. Add optional OBO inputs later for MP/EFO/MONDO when phenotype nodes include those namespaces.
- Expected coverage measured locally: 13,810 / 16,449 phenotype nodes (83.96%).
- Builder changes needed:
  - add `phenotype_textual_summary` to table contract;
  - add HPO source policy and `OBO_SOURCE_DEFAULTS["phenotype_hpo"]` with `summary_kind="phenotype_definition"`;
  - add CLI arg `--hpo-obo`;
  - optionally support namespace dispatch (`HP`, `MP`, `EFO`, `MONDO`) with source-specific defaults, but only HPO should be required for this cache.
- Test changes needed:
  - fixture `phenotype.parquet` with `HP:...` and `hp.obo` definition;
  - test an unmapped HP id is skipped rather than producing an empty summary;
  - validate source/license/release fields.

#### Cell line (`cell_line_textual_summary`)

- Decision: build now, but only for rows that map via stable Cellosaurus xrefs to canonical cell-line IDs.
- Source: Cellosaurus OBO `comment` fields and selected source-backed metadata from `.omoc/raw/cellosaurus/cellosaurus.obo`.
- Source release observed locally: `data-version: 55.0`, `date: 03:31:2026 12:00`; staged rows preserve this as `release="55.0; date=03:31:2026 12:00"` plus provenance header fields.
- License/terms: local Cellosaurus OBO header lines 39-45 state Creative Commons Attribution 4.0 International (CC BY 4.0), `https://creativecommons.org/licenses/by/4.0/`, with required appropriate credit, license link, and change notice. Staged rows/source audit must use `Creative Commons Attribution 4.0 International (CC BY 4.0); https://creativecommons.org/licenses/by/4.0/; attribution/link/change-notice required`, never the former placeholder.
- Mapping strategy: canonical cell-line nodes are DepMap ACH ids (`ACH-...`) with columns `id`, `ccle_name`, `cosmic_id`, `efo_id`, `name`, `source`. Cellosaurus OBO contains `xref: DepMap:ACH-...` entries, so parse terms and join `DepMap` xrefs to `nodes/cell_line.parquet.id`; emit source_record_id as the Cellosaurus `CVCL_...` id and provenance as the local OBO path plus xref.
- Expected coverage: local OBO contains 4,086 `ACH-` mentions / 5,975 `DepMap` mentions; local KG has 1,183 cell_line nodes. Exact coverage should be measured by the builder, but a high fraction of DepMap-backed nodes is expected.
- Text payload policy: use Cellosaurus `comment` text only when non-empty, bounded and source-backed. Do not include long xref lists as prose unless intentionally summarized by deterministic code.
- Builder changes needed:
  - add `cell_line_textual_summary` to table contract;
  - add a Cellosaurus parser for `id`, `name`, `xref: DepMap:ACH-*`, `comment`, `data-version`, `date`;
  - add CLI arg `--cellosaurus-obo`;
  - add source policy with the exact license/terms string once confirmed;
  - emit `summary_kind="cell_line_comment"`.
- Test changes needed:
  - fixture `cell_line.parquet` with `ACH-...` and a Cellosaurus OBO term with `xref: DepMap:ACH-...` and `comment`;
  - assert unmapped CVCL terms are skipped;
  - assert source_record_id is CVCL id and node_id is ACH id.

#### Pathway Reactome (`pathway_textual_summary` additional rows)

- Decision: build now if an acceptable Reactome source is available locally or via documented dump/API; do not scrape Reactome pages.
- Source: Reactome pathway stable IDs/descriptions from Reactome Content Service or a downloadable Reactome data dump with descriptions/summations.
- License/terms: Reactome is already accepted in `SOURCE_POLICY` as CC BY 4.0 with attribution.
- Mapping strategy: join Reactome stable ids to `nodes/pathway.parquet.reactome_id` when present and to `nodes/pathway.parquet.id` for `R-HSA-*` ids. Local pathway audit: 1,518 rows have `reactome_id`; 4,034 pathway node ids start with `R-HSA-`; source counts include 2,516 `REACTOME` rows plus 1,518 `OpenTargets/evidence` rows.
- Expected coverage: up to 4,034 Reactome pathway nodes from current ids, subject to source dump/API description availability.
- Builder changes needed:
  - add parser/input for Reactome pathway descriptions (`--reactome-pathways-json` or `--reactome-pathways-tsv`);
  - append rows into existing `pathway_textual_summary` alongside GO definitions with `summary_kind="reactome_pathway_description"`;
  - keep dedup key source-specific so GO and Reactome rows can coexist for the same pathway if applicable.
- Test changes needed:
  - fixture Reactome pathway row and Reactome source record;
  - assert GO and Reactome rows can both be written to `pathway_textual_summary` without collision.

### Optional low priority

#### Organism (`organism_textual_summary`)

- Decision: optional/low priority.
- Source: NCBI Taxonomy names/lineage or a small source-backed taxonomy record; local cache has one organism node (`NCBITaxon:9606`, human).
- License/terms: NCBI/NLM attribution requested/public-domain style; preserve source URL/release.
- Mapping strategy: join `nodes/organism.parquet.id` (`NCBITaxon:9606`) or `taxonomy_id` to source taxonomy record.
- Expected coverage: 1 / 1 if built.
- Builder/test changes: only add if downstream consumers benefit from organism prose; otherwise skip to avoid a trivial low-signal feature table.

### Defer

#### Dataset descriptions/provenance

- Decision: defer.
- Reason: `dataset.parquet` is absent from the inspected local cache, and source terms/provenance metadata depend on the eventual dataset-node schema.
- Future source candidates: local curated dataset metadata, OpenTargets study/dataset metadata, DepMap/Project Score dataset descriptions, GEO/SRA/BioProject metadata where terms allow.
- Requirement before build: stable dataset node IDs and a source-specific license/provenance policy.

#### Paper descriptions/provenance

- Decision: defer.
- Reason: `paper.parquet` is absent from the inspected local cache; paper text/abstract licensing varies by source.
- Future source candidates: PubMed title/abstract/MeSH metadata, Crossref title/license metadata, OpenAlex metadata, but only after redistribution/license policy is explicit.
- Requirement before build: stable paper node IDs and allowed textual fields; avoid full-text scraping.

## Explicit reject/defer list

Rejected or blocked unless terms are explicitly provided:

- GeneCards: rejected for scraping/redistribution.
- DrugBank textual descriptions: rejected/deferred; keep only allowed IDs/fields unless a separate license is provided.
- Orphanet descriptions: deferred pending exact API/product terms and allowed redistribution form.
- Reactome web-page scraping: rejected; use Content Service or downloadable source only.
- Cellosaurus build before terms capture: defer if the exact license/source terms cannot be recorded in `SOURCE_POLICY` and row metadata.
- PubMed/Crossref/OpenAlex paper abstracts: deferred until paper nodes and text-field/license policy are set.

## Exact code/test change checklist

`manage_db/kg_textual_summary_features.py`:

1. Extend `_TEXTUAL_SUMMARY_TABLE_TYPES` with:
   - `cell_type_textual_summary -> NodeType.CELL_TYPE`
   - `phenotype_textual_summary -> NodeType.PHENOTYPE`
   - `cell_line_textual_summary -> NodeType.CELL_LINE`
   - optional `organism_textual_summary -> NodeType.ORGANISM`
2. Extend `SOURCE_POLICY` with CL/Cell Ontology, HPO, Cellosaurus, NCBI Taxonomy; include exact license strings and conservative decisions.
3. Keep schema columns unchanged.

`manage_db/build_textual_summary_features.py`:

1. Add `OBO_SOURCE_DEFAULTS` entries for `cell_type` and `phenotype_hpo`.
2. Add CLI args: `--cl-obo`, `--hpo-obo`, `--cellosaurus-obo`, optional `--reactome-pathways-json/--reactome-pathways-tsv`, optional `--organism-taxonomy-json/--organism-taxonomy-tsv`.
3. Add Cellosaurus OBO parser for `comment` plus `xref: DepMap:ACH-*` mapping.
4. Add Reactome source parser that emits additional `pathway_textual_summary` rows.
5. Add full UniProt batch raw-input/fetch helper while retaining offline `--uniprot-entries-json`.
6. Include per-source coverage and skipped-row reasons in `reports/textual_summary_features_summary.json`.

Tests:

1. Extend `tests/test_kg_textual_summary_features.py` for the new allowed tables and node-type validation.
2. Extend `tests/test_build_textual_summary_features.py` fixtures for CL, HPO, Cellosaurus, Reactome, and multi-accession UniProt.
3. Keep tests offline by using tiny OBO/JSON/TSV fixtures; no network calls in unit tests.
4. Assert no placeholder Parquets are emitted for missing/unaccepted sources.

## Next staged build order

1. Add table policy/test coverage for `cell_type_textual_summary` and `phenotype_textual_summary` because CL/HPO local OBO mappings are straightforward and high coverage.
2. Add Cellosaurus parser and terms capture; stage `cell_line_textual_summary` if the Cellosaurus license line is accepted.
3. Add full UniProt raw fetch/read pipeline and stage all protein comments.
4. Add Reactome descriptions once an accepted dump/API payload is selected.
5. Decide whether the one-row organism table is useful; otherwise skip.
6. Revisit dataset/paper only when node tables and text-field license policy exist.
