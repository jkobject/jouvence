# Node feature tables canonical promotion report

Task: `t_e6227487`
Generated: `2026-06-22T22:54:00.854983+00:00`

## Verdict

Overall status: **PASS**

The 10 reviewer-approved sequence/textual node feature tables were copied to a versioned canonical-feature staging prefix. No biological `edges/` or `evidence/` objects were written, and no `kg/v2/features/` pointer/path was updated because the live canonical KG had no existing `features/` convention at task time.

Canonical-feature staging root: `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487`

Reviewer/human action required before official pointer creation: approve moving/copying these exact objects to the official feature-layer destination (for example `gs://jouvencekb/kg/v2/features/` if that convention is accepted).

## Approved/promoted tables

| feature path | rows | unique nodes | endpoint nodes | coverage | source | sha256 parity | destination |
|---|---:|---:|---:|---:|---|---|---|
| `features/cell_line_textual_summary.parquet` | 1140 | 1140 | 1183 | 96.3652% | Cellosaurus | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/cell_line_textual_summary.parquet` |
| `features/cell_type_textual_summary.parquet` | 3135 | 3135 | 3513 | 89.2400% | Cell Ontology | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/cell_type_textual_summary.parquet` |
| `features/disease_textual_summary.parquet` | 26395 | 26395 | 41859 | 63.0569% | OpenTargets | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/disease_textual_summary.parquet` |
| `features/gene_textual_summary.parquet` | 212029 | 212029 | 267830 | 79.1655% | OpenTargets | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/gene_textual_summary.parquet` |
| `features/molecule_textual_summary.parquet` | 22230 | 22230 | 31007 | 71.6935% | ChEMBL | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/molecule_textual_summary.parquet` |
| `features/pathway_textual_summary.parquet` | 37492 | 37492 | 48575 | 77.1837% | GO | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/pathway_textual_summary.parquet` |
| `features/phenotype_textual_summary.parquet` | 13810 | 13810 | 16449 | 83.9565% | HPO | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/phenotype_textual_summary.parquet` |
| `features/protein_sequence.parquet` | 112051 | 112051 | 233995 | 47.8861% | Ensembl | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/protein_sequence.parquet` |
| `features/tissue_textual_summary.parquet` | 11942 | 11942 | 16061 | 74.3540% | UBERON | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/tissue_textual_summary.parquet` |
| `features/transcript_sequence.parquet` | 187268 | 187268 | 507365 | 36.9099% | Ensembl | True | `gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487/features/transcript_sequence.parquet` |

Total rows: `627492` across `10` tables; local/readback bytes: `188086567`.

## Validation performed

- exact reviewer-approved whitelist only; `protein_textual_summary` excluded despite earlier raw validation recommendation;
- schema columns checked for each sequence/textual contract;
- exact expected row and unique-node counts checked against parent reviewer handoff;
- `feature_key` dedup, blank metadata, node type/source, empty payload, sequence length/checksum, and text length checks;
- node endpoint anti-join against `.omoc/gcs-cache/kg-v2/nodes/<node_type>.parquet`;
- GCS write to versioned staging prefix;
- post-write readback download and local sha256/byte parity for every object.

## Excluded/deferred

- `features/protein_textual_summary.parquet` was not promoted: parent reviewer `t_61304e4a` deferred the 228-row/0.097% UniProt pilot pending full UniProt/Reactome expansion.
- No ReMap, no biological edges, no biological evidence, no node-table mutation.

## Rollback

If rejected, remove exactly the staged prefix:

```bash
gsutil -m rm -r gs://jouvencekb/kg/v2/_promotion_staging/node-feature-layer-20260623-t_e6227487
```

Because no official pointer/path was updated, rollback is limited to deleting the versioned staging prefix.

## Machine-readable outputs

- Manifest: `.omoc/reports/node_feature_tables_canonical_promotion_manifest.json`
- Coverage CSV: `.omoc/reports/node_feature_tables_canonical_promotion_coverage.csv`
