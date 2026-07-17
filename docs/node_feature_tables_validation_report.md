# Node feature tables validation report

Task: `t_df83345a`
Generated: `2026-06-22T22:48:03.219438+00:00`

## Verdict

Overall status: **PASS**

This validation is staged-only. It did not write canonical `features/`, `nodes/`, `edges/`, or `evidence/` outputs.

Recommendation: promote the staged tables listed under the recommended inclusion set only via a separate canonical feature-promotion gate. Do not promote any biological `edges/` or `evidence/` from this wave.

## Inputs

- Local sequence prefix: `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/`
- GCS sequence prefix: `gs://jouvencekb/kg/staging/node-sequence-features-20260622-t_f9ef6389/`
- Local textual prefix: `.omoc/staging/textual-summary-features-20260622-t_1b89d078/`
- GCS textual prefix: `gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_1b89d078/`
- Node cache: `.omoc/gcs-cache/kg-v2/nodes/`

## Commands run

- `uv run python .omoc/reports/validate_node_feature_tables.py`
- `gsutil ls -l gs://jouvencekb/kg/staging/node-sequence-features-20260622-t_f9ef6389/features/`
- `gsutil ls -l gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_1b89d078/features/`
- `gsutil ls gs://jouvencekb/kg/staging/node-sequence-features-20260622-t_f9ef6389/edges/ (expected non-zero)`
- `gsutil ls gs://jouvencekb/kg/staging/textual-summary-features-20260622-t_1b89d078/evidence/ (expected non-zero)`

## Sequence feature tables

| table | status | rows | unique nodes | endpoint nodes | coverage | max length | sources |
|---|---:|---:|---:|---:|---:|---:|---|
| `protein_sequence` | PASS | 112051 | 112051 | 233995 | 47.8861% | 35991 | Ensembl |
| `transcript_sequence` | PASS | 187268 | 187268 | 507365 | 36.9099% | 82380 | Ensembl |

## Textual summary feature tables

| table | status | rows | unique nodes | endpoint nodes | coverage | max chars | sources |
|---|---:|---:|---:|---:|---:|---:|---|
| `cell_line_textual_summary` | PASS | 1140 | 1140 | 1183 | 96.3652% | 5000 | Cellosaurus |
| `cell_type_textual_summary` | PASS | 3135 | 3135 | 3513 | 89.2400% | 1303 | Cell Ontology |
| `disease_textual_summary` | PASS | 26395 | 26395 | 41859 | 63.0569% | 2314 | OpenTargets |
| `gene_textual_summary` | PASS | 212029 | 212029 | 267830 | 79.1655% | 293 | OpenTargets |
| `molecule_textual_summary` | PASS | 22230 | 22230 | 31007 | 71.6935% | 236 | ChEMBL |
| `pathway_textual_summary` | PASS | 37492 | 37492 | 48575 | 77.1837% | 1308 | GO |
| `phenotype_textual_summary` | PASS | 13810 | 13810 | 16449 | 83.9565% | 2036 | HPO |
| `protein_textual_summary` | PASS | 228 | 228 | 233995 | 0.0974% | 1322 | UniProtKB |
| `tissue_textual_summary` | PASS | 11942 | 11942 | 16061 | 74.3540% | 1682 | UBERON |

## Negative checks

- `.omoc/staging/node-sequence-features-20260622-t_f9ef6389`: local edges absent=True; local evidence absent=True; status=PASS
- `.omoc/staging/textual-summary-features-20260622-t_1b89d078`: local edges absent=True; local evidence absent=True; status=PASS
- `sequence` GCS: feature objects=2; edges absent=True; evidence absent=True; status=PASS
- `textual` GCS: feature objects=9; edges absent=True; evidence absent=True; status=PASS
- ReMap dependency scan: status=PASS; matching files=0; source/text field mentions=[]

## Recommended feature promotion / canonical inclusion set

- `features/cell_line_textual_summary.parquet`
- `features/cell_type_textual_summary.parquet`
- `features/disease_textual_summary.parquet`
- `features/gene_textual_summary.parquet`
- `features/molecule_textual_summary.parquet`
- `features/pathway_textual_summary.parquet`
- `features/phenotype_textual_summary.parquet`
- `features/protein_sequence.parquet`
- `features/protein_textual_summary.parquet`
- `features/tissue_textual_summary.parquet`
- `features/transcript_sequence.parquet`

## Notes and caveats

- `protein_textual_summary` remains a low-coverage pilot (228 / 233,995 protein nodes) because the accepted parent staged only the available UniProt comments payload; promote only if pilot coverage is acceptable, otherwise keep staged until full UniProt batch expansion.
- Sequence coverage reflects Ensembl release/node-cache overlap and deliberate rejection of invalid or overlength records, not a schema failure.
- JSON details, including GCS command output and per-field policy checks, are in `.omoc/reports/node_feature_tables_validation.json`.

## PASS/FAIL details

