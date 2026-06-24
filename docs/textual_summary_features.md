# Textual summary feature tables

Tasks: `t_3834a45b` pilot, `t_1646af09` expansion, `t_1b89d078` Cellosaurus license metadata fix.

Textual summaries are staged as model feature tables under `features/`, not as KG biological edges. They do not assert new biology and should not be promoted into `edges/` or `evidence/`.

## Staged artifact

Current expanded local staging root:

```text
.omoc/staging/textual-summary-features-20260622-t_1b89d078
```

Current expanded uploaded staging root:

```text
gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_1b89d078/
```

Previous expanded root (`t_1646af09`) and pilot root (`t_3834a45b`) remain:

```text
.omoc/staging/textual-summary-features-20260622-t_1646af09
gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_1646af09/
.omoc/staging/textual-summary-features-20260622-t_3834a45b
gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_3834a45b/
```

Every staged table has this contract:

```text
feature_key, feature_table, node_id, node_type, summary_kind, summary_text,
source, source_dataset, source_record_id, provenance, license, citation,
release, created_at
```

Validation performed by `manage_db.kg_textual_summary_features`:

- `node_id` must anti-join cleanly against the corresponding canonical node table.
- `node_type` must match the feature table contract.
- `summary_text` must be non-empty.
- `summary_text` must be <= the configured max text size (`5000` chars in this run).
- duplicate rows are deduplicated by `(feature_table, node_id, source, source_dataset, source_record_id, summary_kind)`.

## Source / license decisions

The full machine-readable audit is staged at:

```text
reports/textual_summary_source_audit.csv
```

Summary decisions / source matrix delta from the pilot:

| Entity | Accepted staged source(s) | Decision in `t_1646af09` |
|---|---|---|
| Gene | OpenTargets target node descriptions, preserving upstream Ensembl/NCBI/HGNC attribution where available | Retained from pilot; GeneCards explicitly rejected. |
| Protein | UniProtKB comments (`FUNCTION`, `SUBCELLULAR LOCATION`, `PTM`, `CATALYTIC ACTIVITY`, `PATHWAY`) | Source policy and resumable full-fetch helper added. This bounded staged run reused the local 99-entry pilot JSON, so protein rows remain pilot-scale pending the long UniProt fetch. |
| Disease | OpenTargets disease node descriptions, preserving upstream EFO/MONDO ontology attribution where available | Retained from pilot; Orphanet deferred until exact API/product terms are reviewed. |
| Tissue | UBERON `def` fields from `uberon-basic.obo` | Retained from pilot. |
| Molecule | ChEMBL-derived OpenTargets drug molecule metadata | Retained from pilot; DrugBank textual scraping rejected/deferred unless a separate license is provided. |
| Pathway | GO `def` fields from `go-basic.obo` for GO-backed pathway nodes | Retained from pilot. Reactome remains source-approved, and JSON/TSV input support was added, but no accepted local Reactome description dump was available in this run. |
| Cell type | Cell Ontology `def` fields from `.omoc/raw/cell_ontology/cl.obo` | New staged table `cell_type_textual_summary`. |
| Phenotype | HPO `def` fields from `.omoc/gcs-cache/kg-v2/raw/hpo/hp.obo` | New staged table `phenotype_textual_summary`; only HP IDs are emitted. |
| Cell line | Cellosaurus OBO `comment` fields from `.omoc/raw/cellosaurus/cellosaurus.obo`, mapped via `xref: DepMap:ACH-*` | New staged table `cell_line_textual_summary`; comments are bounded to `max_text_chars`, with provenance preserving CVCL, DepMap xref, local `data-version=55.0`, `date=03:31:2026 12:00`, and exact CC BY 4.0 header terms. |

Explicit rejections/deferments:

- GeneCards: rejected for scraping/redistribution; no acceptable terms were established for this task.
- DrugBank: no textual scraping; use only existing IDs unless a separate license is provided.
- Orphanet: deferred until exact source/API terms are reviewed.
- Reactome web pages: no scraping. Use only Reactome Content Service/dump JSON or TSV via `--reactome-pathways-json` / `--reactome-pathways-tsv`.

## Row counts from expanded staged run

From `.omoc/staging/textual-summary-features-20260622-t_1b89d078/reports/textual_summary_features_summary.json`:

| Table | Rows | Endpoint nodes | Coverage |
|---|---:|---:|---:|
| `cell_line_textual_summary` | 1,140 | 1,183 | 96.37% |
| `cell_type_textual_summary` | 3,135 | 3,513 | 89.24% |
| `disease_textual_summary` | 26,395 | 41,859 | 63.06% |
| `gene_textual_summary` | 212,029 | 267,830 | 79.17% |
| `molecule_textual_summary` | 22,230 | 31,007 | 71.69% |
| `pathway_textual_summary` | 37,492 | 48,575 | 77.18% |
| `phenotype_textual_summary` | 13,810 | 16,449 | 83.96% |
| `protein_textual_summary` | 228 | 233,995 | 0.10% |
| `tissue_textual_summary` | 11,942 | 16,061 | 74.35% |

All written tables reported:

- `nodes_not_in_endpoint = 0`
- `missing_summary_text_rows = 0`
- `over_max_text_rows = 0`

UniProt source counts from this run:

```json
{
  "distinct_accessions_requested": 80388,
  "entries_returned": 99,
  "entries_with_accepted_comments": 34,
  "protein_node_rows_emitted": 228
}
```

## Commands

Focused tests:

```bash
uv run python -m py_compile manage_db/kg_textual_summary_features.py manage_db/build_textual_summary_features.py
uv run --group dev pytest tests/test_kg_textual_summary_features.py tests/test_build_textual_summary_features.py -q
```

Expanded stage from the local cache used for `t_1646af09`:

```bash
uv run python -m manage_db.build_textual_summary_features \
  --node-root .omoc/gcs-cache/kg-v2/nodes \
  --output-root .omoc/staging/textual-summary-features-20260622-t_1b89d078 \
  --release 2026-06-22-local-cache-expanded \
  --uberon-obo .omoc/gcs-cache/kg-v2/raw/uberon/uberon-basic.obo \
  --go-obo .omoc/raw/go/go-basic.obo \
  --cl-obo .omoc/raw/cell_ontology/cl.obo \
  --hpo-obo .omoc/gcs-cache/kg-v2/raw/hpo/hp.obo \
  --cellosaurus-obo .omoc/raw/cellosaurus/cellosaurus.obo \
  --uniprot-entries-json .omoc/raw/uniprot/textual-summary-pilot-t_3834a45b/uniprot_entries.json \
  --max-text-chars 5000
```

Upload:

```bash
gcloud storage cp -r \
  .omoc/staging/textual-summary-features-20260622-t_1b89d078 \
  gs://jouvencekb/kg/staging/
```

Optional full UniProt raw fetch path added by `t_1646af09`:

```bash
uv run python -m manage_db.build_textual_summary_features \
  --node-root .omoc/gcs-cache/kg-v2/nodes \
  --output-root .omoc/staging/textual-summary-features-<date>-full-uniprot \
  --release <source-release-label> \
  --fetch-uniprot \
  --uniprot-raw-dir .omoc/raw/uniprot/<release> \
  --uniprot-sleep-seconds 0.25 \
  --uberon-obo .omoc/gcs-cache/kg-v2/raw/uberon/uberon-basic.obo \
  --go-obo .omoc/raw/go/go-basic.obo \
  --cl-obo .omoc/raw/cell_ontology/cl.obo \
  --hpo-obo .omoc/gcs-cache/kg-v2/raw/hpo/hp.obo \
  --cellosaurus-obo .omoc/raw/cellosaurus/cellosaurus.obo \
  --max-text-chars 5000
```

## Residual risks / next steps

- Protein coverage is still pilot-scale in the uploaded `t_1646af09` artifact because the only local UniProt payload contains 99 entries. The builder now has a deterministic resumable full-fetch path for the 80,388 distinct mapped accessions, but that long network job should be run separately before promoting protein textual summaries beyond pilot scale.
- Reactome descriptions are source-approved and input support exists, but no local accepted Reactome description JSON/TSV dump was found in this workspace; GO definitions remain the staged pathway text source.
- Cellosaurus comments are accepted only as local OBO content with CVCL/DepMap provenance; long comments are deterministically truncated to the configured `max_text_chars` so validation remains strict.
- No canonical KG writes were performed.
