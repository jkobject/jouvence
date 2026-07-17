# ClinicalTrials.gov canonical feature status resolution — t_957a3640

Status: `canonical promoted` for ClinicalTrials.gov evidence metadata, trial metadata, trial text feature sidecar, and the full HashingVectorizer fallback embedding sidecar; `blocked-with-resource` for foundation-model clinical text embeddings.

This task resolves the ambiguity left by the phrase "structured/text sidecar accepted". The accepted source material is not a new clinical-trial graph node layer and is not default PyG/training graph topology. It is a canonical source-backed evidence/metadata/feature sidecar keyed by canonical `molecule_treats_disease` edge keys and ClinicalTrials.gov NCT IDs.

## Decision table

| Material | Correct KG status | Canonical path / blocker | Label |
| --- | --- | --- | --- |
| ClinicalTrials.gov trial records and structured fields (`overall_status`, `phase`, dates, enrollment, status trajectory, sponsors, `why_stopped`, endpoints/outcomes, eligibility, summaries) | Canonical trial metadata sidecar, keyed by NCT ID. Not canonical node features because there is no accepted `clinical_trial` node type and no default graph adjacency. | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet` | `canonical promoted` |
| OpenTargets/ClinicalTrials.gov edge-to-NCT support | Canonical evidence/link metadata for existing `molecule_treats_disease` assertions. | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_treats_disease.parquet` plus `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` | `canonical promoted` |
| Trial text serialization (`brief_title`, `brief_summary`, `detailed_description`, condition/intervention text, primary/secondary outcomes, eligibility, `why_stopped`, result summaries) | Canonical feature sidecar keyed by NCT ID. It is not a graph label and must be masked or partitioned for held-out treatment-edge prediction because it can leak clinical support evidence. | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet` | `canonical promoted` |
| Deterministic HashingVectorizer embedding scaffold from `t_f8841ff7` | Canonical schema/key wiring scaffold; useful for consumers and validators, not a semantic/foundation embedding. | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet` | `canonical promoted scaffold` |
| Full 6,092-row fallback embedding from `t_1bf3fb33` | Promoted by this task as the full validated fallback embedding sidecar. It stays explicitly labeled `embedding_status = staged fallback` inside the table to avoid claiming foundation quality. | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet` | `canonical promoted fallback sidecar` |
| Foundation-model / clinical-text embeddings | Not produced by this task. The repo environment has no accepted pinned clinical text encoder runtime/model/tokenizer; `pyproject.toml` declares sklearn but not `sentence-transformers` or `transformers`, and runtime import checks still find those packages missing. | Resource/config blocker: select model, add dependency/runtime, record tokenizer/model/version/device, run vector validation and reviewer acceptance. | `blocked-with-resource` |

## Canonical artifacts and hashes

| Artifact | Rows | SHA-256 |
| --- | ---: | --- |
| `metadata/clinical_trials_gov_trial_index.parquet` | 6,092 | `71225856ab5eeec76a271d2bc0891b467ca78e9c5fc018ed66868fc7d638d9e0` |
| `metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` | 7,804 | `60cabb54d8d36f700b7b18da05535cc2a6e2094a04ecf57f972ba0e973f605b8` |
| `features/clinical_trials_gov_trial_text_features.parquet` | 6,092 | `b032da787626fa331e4f7dfc01c23755bc75fd62f7f9523183981f3a1e228beb` |
| `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet` | 6,092 | `f14b111f99f3ed8a59ae15dcd40dd5c334c4cbf4d3748039831b75c47b5f8862` |
| `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet` | 6,092 | `eb710df550f3442195800e9374acd57b4f70d70d74f88d89a089b856520ac264` |
| `metadata/clinical_trials_canonical_features_resolution_t_957a3640.json` | n/a | `e4a29313abd12d3c436ee19d5d888c4ded9deb4c0637349f52728448912a9856` |

Repo-local validation/report copy: `artifacts/reports/t_957a3640_clinical_trials_canonical_features_resolution.json` with the same SHA-256 as the canonical JSON report.

## What was promoted by this task

The only new canonical object written by this task is the full fallback embedding sidecar:

```text
/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet
```

It is byte-identical to the reviewed staged artifact from `t_1bf3fb33`:

```text
artifacts/staged/t_clinical_trials_text_embed_full/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet
```

A machine-readable decision and validation report was also written to:

```text
/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_canonical_features_resolution_t_957a3640.json
artifacts/reports/t_957a3640_clinical_trials_canonical_features_resolution.json
```

## Validation summary

Promotion/validation command:

```bash
uv run python artifacts/reports/t_957a3640_resolve_clinical_trials_canonical_features.py --dry-run
uv run python artifacts/reports/t_957a3640_resolve_clinical_trials_canonical_features.py
```

Observed output: `passed: true`, `blocking_failures: []`, `status: canonical promoted fallback sidecar`.

Targeted validation checks from the report:

```text
trial_index_distinct_nct_ids: 6092
text_features_distinct_nct_ids: 6092
trial_links_distinct_edge_nct: 7804
links_without_trial_index: 0
text_features_without_trial_index: 0
trial_index_without_text_features: 0
fallback_rows: 6092
fallback_distinct_nct_ids: 6092
fallback_duplicate_embedding_keys: 0
fallback_without_text_features: 0
text_features_without_fallback: 0
embedding_dim_values: [384]
embedding_vector_length_values: [384]
embedding_status_values: ['staged fallback']
fallback_without_blocker: 0
source_text_hash_mismatch_rows: 0
nonfinite_values: 0
all_zero_rows: 0
nonempty_eligibility_text_features: 6092
nonempty_why_stopped_text_features: 572
```

Additional hash check:

```text
eb710df550f3442195800e9374acd57b4f70d70d74f88d89a089b856520ac264  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet
e4a29313abd12d3c436ee19d5d888c4ded9deb4c0637349f52728448912a9856  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_canonical_features_resolution_t_957a3640.json
e4a29313abd12d3c436ee19d5d888c4ded9deb4c0637349f52728448912a9856  artifacts/reports/t_957a3640_clinical_trials_canonical_features_resolution.json
```

## Why the embeddings remain fallback

The promoted full table is a real deterministic vectorization over all 6,092 source text rows, not fabricated data. It is still a fallback because the model is `sklearn.feature_extraction.text.HashingVectorizer`, which has no pretrained biomedical/clinical semantic weights, no tokenizer/model checkpoint, and no contextual language-model pooling. It is useful for keying, feature wiring, reproducible baseline behavior, and validation, but it should not be described as production/full foundation embeddings.

A foundation embedding path is therefore not implemented here. The exact blocker is resource/configuration, not data availability: the source text and key contract exist, but the repo does not declare or install an accepted clinical/scientific text encoder runtime. A follow-up foundation task should select/pin the model and dependency set, then preserve the same one-row-per-NCT key contract, source hash checks, field coverage flags, vector finite/nonzero checks, and leakage policy.

## Leakage and modeling constraints

- ClinicalTrials.gov rows are public aggregate trial metadata, not participant-level records.
- Eligibility, outcome text, stop reasons, result summaries, conditions, and interventions can reveal evidence for `molecule_treats_disease`; mask or partition these sidecars for held-out treatment-edge evaluation.
- `COMPLETED`, phase, status, and `why_stopped` are metadata/evidence features, not positive/negative graph labels.
- No `clinical_trial` node type was introduced, no graph edges were created by this task, and no default PyG/HeteroData training topology was changed.

## Residual risks

- Coverage remains the accepted bounded 6,092-NCT OpenTargets/ClinicalTrials.gov seed, not global ClinicalTrials.gov/AACT coverage.
- The full fallback embedding is now canonical as a labelled fallback sidecar only; it is not `production/full done` for embeddings.
- External redistribution still needs normal source/license review before packaging outside the project.
