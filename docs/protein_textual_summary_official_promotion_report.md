# protein_textual_summary official promotion report

Task: `t_5fbd4051`
Date: `Tue Jun 23 11:13:36 CEST 2026`

## Scope

Promoted exactly one feature object:

- Source: `gs://jouvencekb/kg/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/features/protein_textual_summary.parquet`
- Destination: `gs://jouvencekb/kg/v2/features/protein_textual_summary.parquet`

No `edges/`, `evidence/`, ReMap, Reactome pathway-text, or other feature objects were written by this task.

## Pre-write guard

The task body named the staged prefix root, but the reviewed parquet was located under the staged `features/` subdirectory. Before writing, the exact official destination was listed and was absent:

```text
CommandException: One or more URLs matched no objects.
```

The official feature prefix contained 11 parquet objects before the write, including `molecule_fingerprint.parquet`, and did not contain `protein_textual_summary.parquet`.

The write used a destination generation precondition to avoid clobbering a concurrent object:

```bash
gcloud storage cp --if-generation-match=0   gs://jouvencekb/kg/staging/textual-summary-full-uniprot-20260623-t_0b0ca3cb/features/protein_textual_summary.parquet   gs://jouvencekb/kg/v2/features/protein_textual_summary.parquet
```

## GCS object parity

| Field | Staged source | Official destination | Match |
|---|---:|---:|---|
| Content-Length | 18040728 | 18040728 | True |
| CRC32C | `U+NYGg==` | `U+NYGg==` | True |
| MD5 | `kvIdtD+Xo9cy+lx8Ahw7DQ==` | `kvIdtD+Xo9cy+lx8Ahw7DQ==` | True |
| SHA256 after local download | `8f563232443a4034827c2630f64c298828016d642db33b8a23b293ad879ee22a` | `8f563232443a4034827c2630f64c298828016d642db33b8a23b293ad879ee22a` | True |
| Source generation | `1782169800671742` | n/a | n/a |
| Destination generation | n/a | `1782205935050909` | n/a |

Destination creation time from `gsutil ls -L`: `Tue, 23 Jun 2026 09:12:15 GMT`.

## Official feature-layer listing after write

The official `gs://jouvencekb/kg/v2/features/` prefix contains 12 parquet objects after the write:

```text
gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet
gs://jouvencekb/kg/v2/features/cell_type_textual_summary.parquet
gs://jouvencekb/kg/v2/features/disease_textual_summary.parquet
gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet
gs://jouvencekb/kg/v2/features/molecule_fingerprint.parquet
gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet
gs://jouvencekb/kg/v2/features/pathway_textual_summary.parquet
gs://jouvencekb/kg/v2/features/phenotype_textual_summary.parquet
gs://jouvencekb/kg/v2/features/protein_sequence.parquet
gs://jouvencekb/kg/v2/features/protein_textual_summary.parquet
gs://jouvencekb/kg/v2/features/tissue_textual_summary.parquet
gs://jouvencekb/kg/v2/features/transcript_sequence.parquet
```

## Schema and validation contract

Validation was run against the downloaded parquet and `.omoc/gcs-cache/kg-v2/nodes/protein.parquet`.

| Check | Result |
|---|---:|
| Schema columns match textual-summary contract | True |
| Rows | 162163 |
| Unique protein node IDs | 162163 |
| Endpoint protein nodes | 233995 |
| Coverage | 69.301908% |
| Duplicate policy keys | 0 |
| Duplicate feature keys | 0 |
| Endpoint anti-join misses | 0 |
| Missing summary text rows | 0 |
| Max summary text length | 5000 |
| Rows over 5000 chars | 0 |

Expected counts from the human decision were confirmed: 162,163 / 233,995 = 69.30% coverage.

## Distribution / provenance checks

- `feature_table`: `{'protein_textual_summary': 162163}`
- `node_type`: `{'protein': 162163}`
- `summary_kind`: `{'uniprot_function_location_ptm': 162163}`
- `source`: `{'UniProtKB': 162163}`
- `license`: `{'CC BY 4.0': 162163}`
- `release`: `{'2026-06-23-full-uniprot-local-cache': 162163}`
- Missing required provenance/license/citation/release fields: `{'citation': 0, 'license': 0, 'provenance': 0, 'release': 0, 'source': 0, 'source_dataset': 0, 'source_record_id': 0}`

## Rollback command

If reviewer acceptance fails and this task must be rolled back, remove only the promoted destination object:

```bash
gsutil rm gs://jouvencekb/kg/v2/features/protein_textual_summary.parquet
```

Do not remove the staged source prefix unless a separate cleanup task explicitly authorizes it.

## Evidence files

Local evidence for this promotion run is under:

```text
.omoc/tmp/protein_textual_summary_promotion_t_5fbd4051/
```

Key files:

- `source_ls_L.txt`
- `dest_pre_ls_L.txt` / `dest_pre_err.txt`
- `official_features_pre_ls_L.txt`
- `promotion_copy.log`
- `dest_post_verify_ls_L.txt`
- `official_features_post_list.txt`
- `official_features_post_ls_L.txt`
- `pre_promotion_validation.json`
- `post_promotion_verification.json`

## Workspace note

This task used the card workspace `/Users/jkobject/.openclaw/workspace/work/txgnn`, which is a project subdirectory rather than an isolated git worktree root. The durable deliverables are the report and manifest listed above plus the promoted GCS object.
