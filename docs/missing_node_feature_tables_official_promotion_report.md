# Missing node feature tables official promotion report

Task: `t_607adb48`
Generated: `2026-06-23T08:53:40.539625+00:00`

## Verdict

Overall status: **PASS**

Promoted exactly one reviewer-approved feature object:

- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/features/molecule_fingerprint.parquet` -> `gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet`

No `gene_sequence`, `gene_genomic_interval`, `edges/`, `evidence/`, or ReMap outputs were promoted.

## Pre-write guard

- Reviewer-approved canonical scope: `molecule_fingerprint` only.
- Destination before write: absent during preflight (`gsutil stat gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet` returned no match).
- Existing official feature layer before write had the prior 10 approved feature objects / 188,086,567 bytes.

## Official feature listing after promotion

| object | bytes | uri |
|---|---:|---|
| `cell_line_textual_summary.parquet` | 419158 | `gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet` |
| `cell_type_textual_summary.parquet` | 352433 | `gs://jouvencekb/kg/v2/features/cell_type_textual_summary.parquet` |
| `disease_textual_summary.parquet` | 2964350 | `gs://jouvencekb/kg/v2/features/disease_textual_summary.parquet` |
| `gene_textual_summary.parquet` | 7588830 | `gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet` |
| `molecule_fingerprint.parquet` | 4719133 | `gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet` |
| `molecule_textual_summary.parquet` | 730115 | `gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet` |
| `pathway_textual_summary.parquet` | 3578312 | `gs://jouvencekb/kg/v2/features/pathway_textual_summary.parquet` |
| `phenotype_textual_summary.parquet` | 1296148 | `gs://jouvencekb/kg/v2/features/phenotype_textual_summary.parquet` |
| `protein_sequence.parquet` | 32214242 | `gs://jouvencekb/kg/v2/features/protein_sequence.parquet` |
| `tissue_textual_summary.parquet` | 1290803 | `gs://jouvencekb/kg/v2/features/tissue_textual_summary.parquet` |
| `transcript_sequence.parquet` | 137652176 | `gs://jouvencekb/kg/v2/features/transcript_sequence.parquet` |

Post-write object count: `11`. Prior 10 approved objects still present: `True`. New object present: `True`.

## Readback byte/SHA parity

| source | bytes | sha256 |
|---|---:|---|
| staging | 4719133 | `4d49fb6274445face5fadc52ad54d5d69877e5f121eafdd2cac187806672207a` |
| official | 4719133 | `4d49fb6274445face5fadc52ad54d5d69877e5f121eafdd2cac187806672207a` |

Byte parity: `True`. SHA parity: `True`.
Official generation: `1782204703155462`.

## Official Parquet validation

| check | value |
|---|---:|
| rows | 18614 |
| unique nodes | 18614 |
| endpoint molecule nodes | 31007 |
| coverage fraction | 0.6003160576643983 |
| duplicate feature_key rows | 0 |
| nodes not in endpoint | 0 |
| empty payload rows | 0 |
| out-of-range on-bit rows | 0 |
| unsorted on-bit rows | 0 |
| checksum mismatch rows | 0 |
| source SMILES mismatch rows | 0 |
| min on-bit count | 1 |
| max on-bit count | 242 |
| multi-component rows | 1918 |

Schema exact expected columns: `True`.
Blank required metadata counts: `{'source': 0, 'source_dataset': 0, 'source_record_id': 0, 'source_release': 0, 'rdkit_version': 0, 'invalid_smiles_policy': 0, 'salt_mixture_policy': 0, 'provenance': 0, 'license': 0, 'citation': 0, 'created_at': 0}`.
Fixed parameter values: `{'feature_table': ['molecule_fingerprint'], 'node_type': ['molecule'], 'fingerprint_kind': ['morgan_binary'], 'fingerprint_format': ['sparse_on_bits_uint16_list'], 'n_bits': ['2048'], 'radius': ['2'], 'use_chirality': ['True'], 'use_bond_types': ['True'], 'input_smiles_field': ['nodes/molecule.parquet.smiles'], 'rdkit_version': ['2026.03.3'], 'invalid_smiles_policy': ['skip_with_report'], 'salt_mixture_policy': ['fingerprint_input_as_is_record_component_count']}`.

## Negative probes

- `edges/` listing count before: `39`; after: `39`; unchanged: `True`.
- `evidence/` listing count before: `16`; after: `16`; unchanged: `True`.
- Forbidden feature-named probes under `edges/`/`evidence/` returned empty: `True`.

## Rollback

Prefer generation-checked rollback for exactly the object written by this task:

```bash
gsutil rm 'gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet#1782204703155462'
```

Fallback only after re-checking the object still has SHA `4d49fb6274445face5fadc52ad54d5d69877e5f121eafdd2cac187806672207a`:

```bash
gsutil rm 'gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet'
```

## Machine-readable outputs

- Manifest: `.omoc/reports/missing_node_feature_tables_official_promotion_manifest.json`
- Official readback: `.omoc/readback/official-missing-node-features-20260623-t_607adb48/molecule_fingerprint.parquet`
