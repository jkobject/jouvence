# Missing node feature tables validation report

Task: `t_0cc11b0f`
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Validation date: 2026-06-23
Validator output: `.omoc/reports/missing_node_feature_tables_validation.json`

## Verdict

PASS for the staged `molecule_fingerprint` feature table.

PASS for the `gene_sequence` deferral decision: no `gene_sequence` or raw gene sequence payload was staged, which matches the source audit requirement that coordinate/reference-build/mapping/length policy must be reviewed before any raw gene genomic sequence feature exists.

Official feature inclusion recommendation:

- Include `molecule_fingerprint` after reviewer approval.
- Do not include `gene_sequence` yet. Keep it deferred until a reviewed gene coordinate/reference-build/mapping/length policy exists; a `gene_genomic_interval` precursor is the safer next artifact.

No canonical writes were performed by this validation.

## Source audit and builder handoffs read

Read and used:

- `docs/node_feature_missing_gene_sequence_molecule_fingerprint_sources.md`
- `manage_db/build_node_missing_features.py`
- `manage_db/kg_molecule_fingerprint_features.py`
- `manage_db/kg_gene_interval_features.py`
- `tests/test_node_missing_features.py`
- parent handoff for `t_d6c55414`, which states the staged local and GCS roots and that canonical promotion remains separate.

The source audit explicitly says:

- feature tables live under `features/`, not `edges/` or `evidence/`;
- `gene_sequence` must not be transcript-derived or a placeholder;
- raw gene genomic sequence needs reviewed coordinate/source/reference-build/strand/length policy first;
- `molecule_fingerprint` should be derived from `nodes/molecule.parquet.smiles` using deterministic RDKit Morgan parameters;
- no ReMap dependency exists for these features.

## Commands run

From `/Users/jkobject/.openclaw/workspace/work/txgnn`:

```bash
uv run --group dev pytest tests/test_node_missing_features.py -q
```

Result: `5 passed in 0.74s`.

```bash
uv run python .omoc/scripts/validate_missing_node_feature_tables.py
```

Result summary:

```json
{
  "verdict": "pass",
  "issues": [],
  "report": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/reports/missing_node_feature_tables_validation.json",
  "molecule_rows": 18614,
  "recompute_mismatches": 0,
  "gcs_objects": 5
}
```

RDKit emitted five warnings of the form `not removing hydrogen atom without neighbors` during full-table recomputation. These warnings did not produce any parse failures or recomputation mismatches.

## Staged artifact existence

Local staging root:

`/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/node-missing-features-20260623-t_d6c55414`

GCS staging root:

`gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414`

Expected local artifacts verified:

| artifact | exists | size bytes | sha256 |
|---|---:|---:|---|
| `.omoc/staging/node-missing-features-20260623-t_d6c55414/features/molecule_fingerprint.parquet` | yes | 4,719,133 | `4d49fb6274445face5fadc52ad54d5d69877e5f121eafdd2cac187806672207a` |
| `.omoc/staging/node-missing-features-20260623-t_d6c55414/reports/node_missing_features_summary.json` | yes | 1,610 | `fde479bf6a7a97b37d0fa0a9f484d57ee8aa3e79a1f655b69c6589c2c5d47e61` |
| `.omoc/staging/node-missing-features-20260623-t_d6c55414/reports/molecule_fingerprint_source_policy.csv` | yes | 382 | `554b3c57210fd452d2817230bd16169dd4a4d7aa0cdd2813c13107f90d4c85d0` |
| `.omoc/staging/node-missing-features-20260623-t_d6c55414/reports/molecule_fingerprint_invalid_smiles.csv` | yes | 1 | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` |

GCS objects verified by `gsutil ls -r`:

- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/features/molecule_fingerprint.parquet`
- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/reports/molecule_fingerprint_invalid_smiles.csv`
- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/reports/molecule_fingerprint_source_policy.csv`
- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/reports/molecule_fingerprint_validation.json`
- `gs://jouvencekb/kg/staging/node-missing-features-20260623-t_d6c55414/reports/node_missing_features_summary.json`

## `molecule_fingerprint` validation

Path:

`/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/staging/node-missing-features-20260623-t_d6c55414/features/molecule_fingerprint.parquet`

Schema columns verified exactly:

`feature_key`, `feature_table`, `node_id`, `node_type`, `fingerprint_kind`, `fingerprint_format`, `on_bits`, `n_bits`, `radius`, `use_chirality`, `use_bond_types`, `input_smiles`, `canonical_smiles_rdkit`, `input_smiles_field`, `inchikey`, `source`, `source_dataset`, `source_record_id`, `source_release`, `rdkit_version`, `invalid_smiles_policy`, `salt_mixture_policy`, `component_count`, `provenance`, `license`, `citation`, `created_at`, `fingerprint_sha256`.

Measured results:

| check | result |
|---|---:|
| endpoint molecule nodes | 31,007 |
| source records with non-empty SMILES | 18,614 |
| feature rows | 18,614 |
| unique feature nodes | 18,614 |
| coverage fraction | 0.6003160576643983 |
| duplicate `feature_key` rows | 0 |
| node IDs outside endpoint table | 0 |
| empty/all-zero payload rows | 0 |
| out-of-range on-bit rows | 0 |
| unsorted on-bit rows | 0 |
| checksum mismatches | 0 |
| source SMILES mismatches vs `nodes/molecule.parquet.smiles` | 0 |
| full RDKit recomputation rows | 18,614 |
| full RDKit recomputation mismatches | 0 |
| missing source SMILES count | 12,393 |
| invalid SMILES report rows | 0 |
| multi-component rows | 1,918 |
| min on-bit count | 1 |
| max on-bit count | 242 |

Fixed parameter values verified:

- `feature_table`: `molecule_fingerprint`
- `node_type`: `molecule`
- `fingerprint_kind`: `morgan_binary`
- `fingerprint_format`: `sparse_on_bits_uint16_list`
- `n_bits`: `2048`
- `radius`: `2`
- `use_chirality`: `True`
- `use_bond_types`: `True`
- `input_smiles_field`: `nodes/molecule.parquet.smiles`
- `rdkit_version`: `2026.03.3`
- `invalid_smiles_policy`: `skip_with_report`
- `salt_mixture_policy`: `fingerprint_input_as_is_record_component_count`

Required provenance/license/citation/release fields had zero blank values for:

`source`, `source_dataset`, `source_record_id`, `source_release`, `rdkit_version`, `invalid_smiles_policy`, `salt_mixture_policy`, `provenance`, `license`, `citation`, `created_at`.

Source policy rows verified:

- ChEMBL: `allow_with_attribution`, license `CC BY-SA 3.0`.
- OpenTargets: `allow_with_attribution_if_upstream_source_clear`, license `CC BY 4.0 / upstream source attribution`.

## `gene_sequence` validation

No raw `gene_sequence` feature table was staged:

- `features/gene_sequence.parquet`: absent.
- `features/gene_genomic_interval.parquet`: absent.
- builder summary: `gene_genomic_interval` is deferred with reason `No reviewed GTF/GFF coordinate source supplied; raw gene_sequence remains deferred.`
- builder summary: `raw_gene_sequence_written=false`.

This is the correct validation outcome for this tranche. The source audit says a bare `gene_sequence` table must not be created until the following are reviewed and pinned:

- source coordinate table and KG gene ID mapping;
- coordinate system and reference build;
- strand orientation policy;
- sequence alphabet policy;
- sequence checksum policy;
- large-sequence exclusion/limit policy;
- alternative contig/PAR/haplotype/readthrough handling.

Because no sequence payload was emitted, sequence alphabet/checksum/large-sequence content checks are not applicable to staged data. The validation confirms there is no placeholder table and no raw sequence payload.

## Forbidden outputs and ReMap dependency

Local staging checks:

- local `edges/` paths under staging: none.
- local `evidence/` paths under staging: none.
- local ReMap-named paths under staging: none.

GCS staging checks:

- object count: 5.
- GCS `edges/` or `evidence/` objects: none.
- GCS ReMap-named objects: none.

Code-level search for `ReMap|remap|REMAP` in `manage_db/*.py` found only an unrelated comment in `manage_db/backfill_edge_evidence.py`: `do not remap to ENSP`. No ReMap dependency appears in the missing-feature builder or helper modules.

## Recommendation

Promote/review `molecule_fingerprint` as the official feature candidate.

Do not promote or synthesize `gene_sequence` from this tranche. The correct next work is a reviewed coordinate/mapping artifact, preferably named `gene_genomic_interval`, followed later by a bounded `gene_genomic_sequence` only if reference-build, strand, checksum, alphabet, and maximum-length policies are accepted.
