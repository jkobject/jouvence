# Textual summary feature tables

Task: `t_3834a45b`

Textual summaries are staged as model feature tables under `features/`, not as KG biological edges. They do not assert new biology and should not be promoted into `edges/` or `evidence/`.

## Staged artifact

Local staging root:

```text
.omoc/staging/textual-summary-features-20260622-t_3834a45b
```

Uploaded staging root:

```text
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

Summary decisions:

| Entity | Accepted staged source(s) | Decision |
|---|---|---|
| Gene | OpenTargets target node descriptions, preserving upstream Ensembl/NCBI/HGNC attribution where available | Allowed as feature text with attribution; GeneCards explicitly rejected. |
| Protein | UniProtKB comments (`FUNCTION`, `SUBCELLULAR LOCATION`, `PTM`, `PATHWAY`) | Allowed with UniProt attribution / CC BY 4.0; current artifact is a 100-accession pilot producing 228 mapped protein-node rows. |
| Disease | OpenTargets disease node descriptions, preserving upstream EFO/MONDO ontology attribution where available | Allowed as feature text with attribution; Orphanet deferred until exact API/product terms are reviewed. |
| Tissue | UBERON `def` fields from `uberon-basic.obo` | Allowed with ontology attribution / CC BY-style OBO attribution. |
| Molecule | ChEMBL-derived OpenTargets drug molecule metadata | Allowed with ChEMBL/OpenTargets attribution; DrugBank textual scraping rejected/deferred unless a separate license is provided. |
| Pathway | GO `def` fields from `go-basic.obo` for GO-backed pathway nodes | Allowed with GO attribution / CC BY 4.0. Reactome remains allowed but was not used in this staged run because no local Reactome description dump was available. |

Explicit rejections/deferments:

- GeneCards: rejected for scraping/redistribution; no acceptable terms were established for this task.
- DrugBank: no textual scraping; use only existing IDs unless a separate license is provided.
- Orphanet: deferred until exact source/API terms are reviewed.

## Row counts from staged run

From `reports/textual_summary_features_summary.json`:

| Table | Rows | Endpoint nodes | Coverage |
|---|---:|---:|---:|
| `gene_textual_summary` | 212,029 | 267,830 | 79.17% |
| `protein_textual_summary` | 228 | 233,995 | 0.097% |
| `disease_textual_summary` | 26,395 | 41,859 | 63.06% |
| `tissue_textual_summary` | 11,942 | 16,061 | 74.35% |
| `molecule_textual_summary` | 22,230 | 31,007 | 71.69% |
| `pathway_textual_summary` | 37,492 | 48,575 | 77.18% |

All tables reported:

- `nodes_not_in_endpoint = 0`
- `missing_summary_text_rows = 0`
- `over_max_text_rows = 0`

## Commands

Focused tests:

```bash
uv run --group dev pytest tests/test_kg_textual_summary_features.py tests/test_build_textual_summary_features.py -q
```

Stage from the local cache used for this task:

```bash
uv run python -m manage_db.build_textual_summary_features \
  --node-root .omoc/gcs-cache/kg-v2/nodes \
  --output-root .omoc/staging/textual-summary-features-20260622-t_3834a45b \
  --release 2026-06-22-local-cache-pilot \
  --uberon-obo .omoc/gcs-cache/kg-v2/raw/uberon/uberon-basic.obo \
  --go-obo .omoc/raw/go/go-basic.obo \
  --uniprot-entries-json .omoc/raw/uniprot/textual-summary-pilot-t_3834a45b/uniprot_entries.json \
  --max-text-chars 5000
```

Upload:

```bash
gcloud storage cp -r \
  .omoc/staging/textual-summary-features-20260622-t_3834a45b \
  gs://jouvencekb/kg/staging/
```

## Residual risks / next steps

- Protein coverage is intentionally a UniProt pilot. For full coverage, batch UniProt accessions from `nodes/protein.parquet` through UniProt REST/idmapping with rate-limit/backoff and rerun the same builder.
- Reactome descriptions are source-approved but not staged because this run had pathway names/IDs but no local Reactome description dump. Add a Reactome stable ID description source before staging Reactome text.
- OpenTargets node-description rows preserve the local source tag in `provenance`, but some rows still require upstream-source granularity if a future reviewer wants stricter per-row attribution.
