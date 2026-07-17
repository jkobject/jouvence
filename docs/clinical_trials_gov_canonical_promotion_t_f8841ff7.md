# ClinicalTrials.gov canonical support promotion — t_f8841ff7

Status: `canonical promoted` / `review-required`.

This card promoted the reviewed staged CTGov/ClinicalTrials.gov production candidate from `t_c4f67957` into canonical KG support/evidence/feature namespaces for the existing canonical `molecule_treats_disease` graph assertions. It did not modify `edges/molecule_treats_disease.parquet` and did not create clinical-trial negative edges.

## Scope

Promoted scope is the bounded, source-backed OpenTargets/ClinicalTrials.gov NCT seed reviewed by `t_d03b9af1`:

- 6,092 requested and fetched NCT IDs from the frozen ClinicalTrials.gov API v2 `query.id` raw snapshot.
- 7,804 edge-NCT evidence/link rows.
- 377 supported canonical `molecule_treats_disease` edge keys.
- 6,092 NCT-keyed trial text feature rows.
- 6,092 deterministic 384-d HashingVectorizer embedding scaffold rows.

This is not global all-ClinicalTrials.gov coverage and not an all drug/disease clinical trial map.

## Canonical paths

| Artifact | Canonical path | Rows | SHA-256 |
| --- | --- | ---: | --- |
| Evidence rows | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_treats_disease.parquet` | 7,804 | `91e0b42685b32f00e4ddabb014df672ad607bea01fd56633bd3a60390bbc1dc9` |
| Trial index metadata | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet` | 6,092 | `71225856ab5eeec76a271d2bc0891b467ca78e9c5fc018ed66868fc7d638d9e0` |
| Molecule-disease trial links | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` | 7,804 | `60cabb54d8d36f700b7b18da05535cc2a6e2094a04ecf57f972ba0e973f605b8` |
| Trial text features | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet` | 6,092 | `b032da787626fa331e4f7dfc01c23755bc75fd62f7f9523183981f3a1e228beb` |
| Text embedding scaffold | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet` | 6,092 | `f14b111f99f3ed8a59ae15dcd40dd5c334c4cbf4d3748039831b75c47b5f8862` |
| Raw snapshot manifest copy | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_api_v2_raw_manifest_t_c4f67957.json` | n/a | `edab419bcb76f8511c12d627d4ab76427ec4417539b758b30c6bbb7b0562c13c` |
| Canonical promotion validation report | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_canonical_promotion_t_f8841ff7.json` | n/a | `60158e53062f35d7253255b84b10b3e694f7088f9a0c404e5180e2beb28cc7f4` |

The repo-local validation/report copy is `artifacts/reports/t_f8841ff7_ctgov_canonical_promotion_validation.json` with the same SHA-256 as the canonical promotion report.

## Validation

Pre-write manifest validation recomputed the ClinicalTrials.gov raw manifest checksum and every raw chunk checksum:

- Manifest expected/computed SHA-256: `fbcb5b03a7577c0cc357983c7bc65d8699d0dd4e551924ddb653ba47478a8804`.
- Raw chunk count: 61.
- Bad chunk hashes: 0.
- Fetch errors: 0.

Post-write canonical validation passed with no blocking failures:

- Wrong relation/type rows: 0.
- Duplicate evidence edge-NCT rows: 0.
- Duplicate link edge-NCT rows: 0.
- Duplicate trial-index NCT IDs: 0.
- Blank/bad NCT study IDs: 0.
- Missing molecule endpoints: 0.
- Missing disease endpoints: 0.
- Links without canonical `molecule_treats_disease` edge: 0.
- Links without trial index: 0.
- Trial index without links: 0.
- Evidence without links: 0.
- Links without evidence: 0.
- Features without trial index: 0.
- Embeddings without features: 0.
- Embedding dimensions/vector lengths: `[384]` / `[384]`.
- Non-finite embedding values: 0.
- All-zero embedding rows: 0.

Commands run:

```bash
uv run python artifacts/reports/t_f8841ff7_promote_ctgov_canonical.py --dry-run
uv run python artifacts/reports/t_f8841ff7_promote_ctgov_canonical.py
uv run python -m py_compile artifacts/reports/t_f8841ff7_promote_ctgov_canonical.py manage_db/kg_evidence.py manage_db/kg_schema.py
uv run --group dev pytest tests/test_kg_evidence.py tests/test_kg_schema_cleanup.py -q
shasum -a 256 /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_treats_disease.parquet /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_api_v2_raw_manifest_t_c4f67957.json /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_canonical_promotion_t_f8841ff7.json
```

Targeted test output:

```text
14 passed in 0.28s
```

## Policy notes / residual risks

- Clinical trial status, phase, endpoint, outcome, and `why_stopped` fields are evidence/features/weights only. They are not negative graph edges.
- `COMPLETED` means `completed_outcome_unknown`, not positive efficacy.
- HashingVectorizer embeddings are deterministic scaffold features for schema/key validation and downstream wiring, not final/foundation clinical text embeddings.
- Source snapshot is a frozen ClinicalTrials.gov API v2 raw cache, not an AACT relational export. AACT remains preferred for future all-CTGov mirror work.
- Coverage is complete only for the selected reviewed OpenTargets clinicalReportIds/NCT seed; do not claim global CTGov coverage.
- Promotion was performed from the shared artifact workspace, not a PR-ready TxGNN worktree diff.
