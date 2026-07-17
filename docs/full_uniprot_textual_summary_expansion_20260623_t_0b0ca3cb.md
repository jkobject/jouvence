# Full UniProt textual summary expansion staging

Task: `t_0b0ca3cb`

This run stages a future-review textual feature expansion only. It does not write canonical KG paths and does not create or modify `edges/` or `evidence/` artifacts.

## Staging roots

Local staging root:

```text
.omoc/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb
```

Uploaded review prefix:

```text
gs://jouvencekb/kg/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/
```

Uploaded review artifacts include `features/`, `reports/`, `scripts/`, and `raw/uniprot/uniprot_entries.slim.json`. The local staging root also preserves the full per-accession UniProt raw cache and batch payload cache under `raw/uniprot/entries/` and `raw/uniprot/batches/`.

## Build inputs and source policy

- Node root: `.omoc/gcs-cache/kg-v2/nodes`.
- Release label: `2026-06-23-full-uniprot-local-cache`.
- UniProt accessions requested: 80,388 distinct mapped accessions from `nodes/protein.parquet.uniprot_id`.
- UniProt fetch mode: approved UniProt REST API JSON, cached locally per accession with deterministic markers for accessions not returned by batch query. A staging-only batch helper was used after the original per-accession resumable path proved too slow; the final feature build consumed the project builder via `--uniprot-entries-json`.
- UniProt text fields: accepted comments only (`FUNCTION`, `SUBCELLULAR LOCATION`, `PTM`, `CATALYTIC ACTIVITY`, `PATHWAY`).
- UniProt license in rows: `CC BY 4.0`.
- Citation/provenance/release fields are populated per row.
- Reactome descriptions: deferred. I found no approved local Reactome pathway description JSON/TSV payload in the workspace, and no Reactome web scraping was performed.

## Commands run

```bash
uv run python -m py_compile manage_db/kg_textual_summary_features.py manage_db/build_textual_summary_features.py
uv run --group dev pytest tests/test_kg_textual_summary_features.py tests/test_build_textual_summary_features.py -q
```

Result: `10 passed`.

Full stage command:

```bash
uv run python -u -m manage_db.build_textual_summary_features \
  --node-root .omoc/gcs-cache/kg-v2/nodes \
  --output-root .omoc/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb \
  --release 2026-06-23-full-uniprot-local-cache \
  --uniprot-entries-json .omoc/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/raw/uniprot/uniprot_entries.slim.json \
  --uberon-obo .omoc/gcs-cache/kg-v2/raw/uberon/uberon-basic.obo \
  --go-obo .omoc/raw/go/go-basic.obo \
  --cl-obo .omoc/raw/cell_ontology/cl.obo \
  --hpo-obo .omoc/gcs-cache/kg-v2/raw/hpo/hp.obo \
  --cellosaurus-obo .omoc/raw/cellosaurus/cellosaurus.obo \
  --max-text-chars 5000
```

Independent validation command output is saved at:

```text
.omoc/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/reports/full_uniprot_textual_summary_independent_validation.json
```

and uploaded to:

```text
gs://jouvencekb/kg/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/reports/full_uniprot_textual_summary_independent_validation.json
```

## Validation results

The independent validation pass checked:

- exact textual feature schema columns;
- duplicate policy keys `(feature_table, node_id, source, source_dataset, source_record_id, summary_kind)`;
- endpoint anti-joins against local node cache;
- non-empty `summary_text`;
- `summary_text <= 5000` characters;
- required source/license/provenance/citation/release fields;
- source and node_type distributions;
- coverage against endpoint node counts.

Result: PASS.

| Table | Rows | Unique nodes | Endpoint nodes | Coverage | Source(s) |
|---|---:|---:|---:|---:|---|
| `cell_line_textual_summary` | 1,140 | 1,140 | 1,183 | 96.37% | Cellosaurus |
| `cell_type_textual_summary` | 3,135 | 3,135 | 3,513 | 89.24% | Cell Ontology |
| `disease_textual_summary` | 26,395 | 26,395 | 41,859 | 63.06% | OpenTargets |
| `gene_textual_summary` | 212,029 | 212,029 | 267,830 | 79.17% | OpenTargets |
| `molecule_textual_summary` | 22,230 | 22,230 | 31,007 | 71.69% | ChEMBL |
| `pathway_textual_summary` | 37,492 | 37,492 | 48,575 | 77.18% | GO |
| `phenotype_textual_summary` | 13,810 | 13,810 | 16,449 | 83.96% | HPO |
| `protein_textual_summary` | 162,163 | 162,163 | 233,995 | 69.30% | UniProtKB |
| `tissue_textual_summary` | 11,942 | 11,942 | 16,061 | 74.35% | UBERON |

All staged tables report:

- `duplicate_policy_key_duplicates = 0`;
- `nodes_not_in_endpoint = 0`;
- `missing_summary_text_rows = 0`;
- `over_max_text_rows = 0`;
- required source/license/provenance/citation/release field missing counts = 0.

UniProt source counts:

```json
{
  "distinct_accessions_requested": 80388,
  "entries_returned": 80388,
  "entries_with_accepted_comments": 27433,
  "protein_node_rows_emitted": 162163
}
```

## Code delta

A validation failure exposed that UniProt summaries could exceed `max_text_chars`. I patched `manage_db/build_textual_summary_features.py` so `rows_from_uniprot_entries()` applies deterministic `_bounded_text(..., max_text_chars)` before validation, and the stage call passes the CLI `--max-text-chars` value through. Focused textual-summary tests pass after the patch.

Changed code file:

```text
manage_db/build_textual_summary_features.py
```

## Residual risks / review notes

- This is a staged feature expansion for review, not a canonical promotion.
- Reactome pathway descriptions remain deferred until an approved Reactome pathway description JSON/TSV dump/API payload is provided locally. No scraping was done.
- The GCS upload intentionally excludes the 3.8 GB duplicate full raw `entries/` and `batches/` caches; those are preserved locally. The uploaded slim payload contains the exact `primaryAccession` + `comments` data consumed by the builder and is sufficient to reproduce the staged feature tables.
- The UniProt fetch used the approved REST API in batch query mode for practicality after the per-accession path was too slow. Raw per-accession cache files are preserved locally for audit/resume.
