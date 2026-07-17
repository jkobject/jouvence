# Node feature tables official promotion report

Task: `t_ed43b234`
Generated: `2026-06-22T23:10:51.747399+00:00`

## Verdict

Overall status: **PASS**

Official destination: `gs://jouvencekb/kg/v2/features/`
Source staging prefix: `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/`

The 10 reviewer-approved node feature objects were copied from validated staging to the official `kg/v2/features/` layer. This was a feature-layer path promotion only; no `edges/` or `evidence/` objects were written.

## Pre-write guard

- Destination guard status: `PASS` (`absent_or_empty`)
- `protein_textual_summary.parquet` is excluded and remains absent from the official feature layer.

## Official objects

| feature path | rows | unique nodes | bytes | generation | sha256 parity | validation | official uri |
|---|---:|---:|---:|---|---|---|---|
| `features/cell_line_textual_summary.parquet` | 1140 | 1140 | 419158 | `1782169808349167` | True | PASS | `gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet` |
| `features/cell_type_textual_summary.parquet` | 3135 | 3135 | 352433 | `1782169810447963` | True | PASS | `gs://jouvencekb/kg/v2/features/cell_type_textual_summary.parquet` |
| `features/disease_textual_summary.parquet` | 26395 | 26395 | 2964350 | `1782169812047483` | True | PASS | `gs://jouvencekb/kg/v2/features/disease_textual_summary.parquet` |
| `features/gene_textual_summary.parquet` | 212029 | 212029 | 7588830 | `1782169813900972` | True | PASS | `gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet` |
| `features/molecule_textual_summary.parquet` | 22230 | 22230 | 730115 | `1782169815729970` | True | PASS | `gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet` |
| `features/pathway_textual_summary.parquet` | 37492 | 37492 | 3578312 | `1782169817298055` | True | PASS | `gs://jouvencekb/kg/v2/features/pathway_textual_summary.parquet` |
| `features/phenotype_textual_summary.parquet` | 13810 | 13810 | 1296148 | `1782169819880354` | True | PASS | `gs://jouvencekb/kg/v2/features/phenotype_textual_summary.parquet` |
| `features/protein_sequence.parquet` | 112051 | 112051 | 32214242 | `1782169822702242` | True | PASS | `gs://jouvencekb/kg/v2/features/protein_sequence.parquet` |
| `features/tissue_textual_summary.parquet` | 11942 | 11942 | 1290803 | `1782169825680065` | True | PASS | `gs://jouvencekb/kg/v2/features/tissue_textual_summary.parquet` |
| `features/transcript_sequence.parquet` | 187268 | 187268 | 137652176 | `1782169828167398` | True | PASS | `gs://jouvencekb/kg/v2/features/transcript_sequence.parquet` |

Total rows: `627492` across `10` tables.
Total bytes: `188086567`.

## Validation performed on official readback

- `gsutil ls -l` official listing checked exactly 10 objects / 188,086,567 bytes;
- official objects downloaded to `.omoc/readback/official-node-feature-layer-20260623-t_ed43b234/features/`;
- byte parity and SHA256 parity checked against the validated staging manifest;
- schema, expected rows/unique node counts, duplicate `feature_key`, endpoint anti-join, blank provenance/license/citation/release/source metadata, sequence length/checksum/case, text nonempty/max-length checks run with DuckDB/PyArrow on official readback files.

## Negative probes

- staging `edges/` absent: `True`
- staging `evidence/` absent: `True`
- official `protein_textual_summary.parquet` absent: `True`
- official `edges/` listing unchanged during write: `True`
- official `evidence/` listing unchanged during write: `True`

## Rollback

Because `kg/v2/features/` was absent before this promotion, rollback is removal of exactly the 10 official feature objects written by this card. Prefer generation-checked removal using the generations recorded in the manifest:

```bash
gsutil rm 'gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet#1782169808349167'
gsutil rm 'gs://jouvencekb/kg/v2/features/cell_type_textual_summary.parquet#1782169810447963'
gsutil rm 'gs://jouvencekb/kg/v2/features/disease_textual_summary.parquet#1782169812047483'
gsutil rm 'gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet#1782169813900972'
gsutil rm 'gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet#1782169815729970'
gsutil rm 'gs://jouvencekb/kg/v2/features/pathway_textual_summary.parquet#1782169817298055'
gsutil rm 'gs://jouvencekb/kg/v2/features/phenotype_textual_summary.parquet#1782169819880354'
gsutil rm 'gs://jouvencekb/kg/v2/features/protein_sequence.parquet#1782169822702242'
gsutil rm 'gs://jouvencekb/kg/v2/features/tissue_textual_summary.parquet#1782169825680065'
gsutil rm 'gs://jouvencekb/kg/v2/features/transcript_sequence.parquet#1782169828167398'
```

Non-generation fallback, only if the generation-checked command is unavailable and the objects still match this manifest:

```bash
gsutil -m rm \
  gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/cell_type_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/disease_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/pathway_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/phenotype_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/protein_sequence.parquet \
  gs://jouvencekb/kg/v2/features/tissue_textual_summary.parquet \
  gs://jouvencekb/kg/v2/features/transcript_sequence.parquet
```

## Machine-readable outputs

- Manifest: `.omoc/reports/node_feature_tables_official_promotion_manifest.json`
- Coverage CSV: `.omoc/reports/node_feature_tables_official_promotion_coverage.csv`
- Official readback directory: `.omoc/readback/official-node-feature-layer-20260623-t_ed43b234`

## Addendum — ReMap CRM full support sidecar

Task `t_f2a2952e` promoted a separate, shard-aware, support-only feature/QA sidecar after readiness gate `t_7e356c5c` and reviewer `t_0d77b4f0`:

- canonical prefix: `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/`
- data layout: 24 `summary_chr*.parquet` chromosome shards plus `tf_global_summary.parquet`
- rows: `48,768,788` summary rows, including `48,741,900` enhancer summary rows and `26,888` per-chromosome TF rows; `1,179` global TF summary rows
- semantics: `crm_aggregated_support`; support-only feature/QA material, not graph topology, not evidence, not `observed_binding`, and not canonical `tf_binds_enhancer` edge/evidence
- manifest/report: `docs/remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md` and `gs://jouvencekb/kg/v2/features/remap_crm_tf_enhancer_support_full/manifest.json`
