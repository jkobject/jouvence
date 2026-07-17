# Clinical trials structured text pilot — t_a52976cf

Status: pilot artifact `staged-only` / `review-required`; canonical status resolved by `t_957a3640`.

Resolution note: see `docs/clinical_trials_canonical_features_resolution_t_957a3640.md`. The 512-row compact pilot table stays staged-only, but the underlying full ClinicalTrials.gov sidecars it sampled are canonical: structured trial fields in `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet`, edge/NCT support in `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` and `evidence/molecule_treats_disease.parquet`, and text summaries/outcomes/eligibility/why_stopped in `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet`. These are sidecar metadata/features, not clinical-trial graph nodes and not default PyG/training topology.

This card builds a compact clinical-trials sidecar artifact for Jouvence KG from already-present ClinicalTrials.gov/OpenTargets trial sidecars. It does not write canonical KG paths and does not add clinical trials as default PyG training graph edges.

## Source inventory

Inventory manifest: `artifacts/staged/t_clinical_trials_structured_text_pilot/manifests/source_inventory.json`.

| Source | Exact path | Rows | SHA-256 / version note |
| --- | --- | ---: | --- |
| ClinicalTrials.gov trial index | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet` | 6,092 | `71225856ab5eeec76a271d2bc0891b467ca78e9c5fc018ed66868fc7d638d9e0` |
| OpenTargets/ClinicalTrials.gov molecule-disease trial links | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` | 7,804 | `60cabb54d8d36f700b7b18da05535cc2a6e2094a04ecf57f972ba0e973f605b8` |
| ClinicalTrials.gov text features | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet` | 6,092 | `b032da787626fa331e4f7dfc01c23755bc75fd62f7f9523183981f3a1e228beb` |
| Existing deterministic text embedding scaffold | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet` | 6,092 | `f14b111f99f3ed8a59ae15dcd40dd5c334c4cbf4d3748039831b75c47b5f8862` |
| Frozen CTGov API raw manifest copy | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_api_v2_raw_manifest_t_c4f67957.json` | n/a | `edab419bcb76f8511c12d627d4ab76427ec4417539b758b30c6bbb7b0562c13c` |
| Source staged candidate | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/` | n/a | ClinicalTrials.gov API v2 `query.id` frozen chunks from production candidate. |

Version/scope: the ClinicalTrials.gov rows come from the frozen API v2 `query.id` snapshot built by `t_c4f67957` and canonically copied by `t_f8841ff7`. The OpenTargets link seed is the prior molecule_treats_disease `clinicalReportIds`/NCT support layer. This is bounded source-backed coverage, not all ClinicalTrials.gov and not all possible molecule/disease clinical trials.

## New staged artifacts

All artifacts are under `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_clinical_trials_structured_text_pilot/`.

| Artifact | Path | Rows | Purpose |
| --- | --- | ---: | --- |
| Structured + text pilot table | `metadata/clinical_trials_structured_text_pilot.parquet` | 512 | One row per selected molecule-disease edge/NCT link with trial identifier, molecule and disease IDs, structured trial fields, source text fields, and embedding linkage hashes. |
| Smoke text embedding artifact | `features/embeddings/clinical_trials_text/hashing_vectorizer/smoke_v1/part-000.parquet` | 32 | Deterministic 384-d HashingVectorizer smoke embeddings keyed to the pilot text rows. |
| Source inventory | `manifests/source_inventory.json` | n/a | Exact source paths, row counts, hashes, and scope/version notes. |
| Embedding-ready manifest | `manifests/embedding_ready_manifest.json` | n/a | Exact rerun command, input columns, smoke embedding config, and foundation embedding output contract. |
| Validation checks | `reports/validation_checks.json` | n/a | Row-count/key/readability/embedding checks. |
| Machine report | `reports/clinical_trials_structured_text_pilot_report.json` | n/a | Counts, distributions, missingness, schema columns, policy notes. |
| Build script | `build_clinical_trials_structured_text_pilot.py` | n/a | Reproducible local builder; writes only under this staged root. |

Rerun command:

```bash
uv run python artifacts/staged/t_clinical_trials_structured_text_pilot/build_clinical_trials_structured_text_pilot.py
```

Observed output summary:

```text
status: PASS
prototype_rows: 512
distinct_trials: 417
distinct_molecule_disease_edges: 161
distinct_molecules: 125
distinct_diseases: 49
gene_link_rows: 0
smoke_embedding_rows: 32
```

## Pilot table schema

Required/linkage columns:

- `trial_link_key` — unique `edge_key|nct_id` key for this sidecar row.
- `trial_id`, `nct_id` — ClinicalTrials.gov NCT accession.
- `edge_key`, `relation` — current molecule_treats_disease edge key and relation.
- `molecule_id`, `molecule_type`, `disease_id`, `disease_type` — source-native OpenTargets/ClinicalTrials.gov-supported endpoints from the current molecule-disease trial link sidecar.
- `gene_id`, `gene_type`, `gene_link_policy` — deliberately empty for this source because the available ClinicalTrials.gov/OpenTargets clinicalReportIds sidecar does not expose a source-native gene endpoint.
- `mapping_source`, `mapping_method`, `mapping_confidence` — source-native mapping audit from OpenTargets clinicalReportIds/NCT links.

Structured trial fields:

- `overall_status`, `trajectory_class`, `phase`, `study_type`.
- `start_date`, `primary_completion_date`, `completion_date`.
- `enrollment_count`, `enrollment_type`.
- `condition_text`, `intervention_names`, `intervention_types`.
- `lead_sponsor`, `lead_sponsor_class`, `publication_ids`.

Text fields modeled for downstream encoders:

- `brief_title`, `official_title`, `brief_summary`, `detailed_description`.
- `primary_endpoints`, `secondary_endpoints`.
- `primary_outcome_text`, `secondary_outcome_text`.
- `eligibility_criteria`, `why_stopped`, `result_summary_text`.
- `source_text`, `source_text_hash`, `source_text_length`, `source_field_inventory`.

Embedding linkage/status fields:

- `source_feature_key`, `source_text_hash`.
- `text_embedding_status` notes the emitted smoke embedding and existing full-source HashingVectorizer scaffold.
- `staging_policy` records that this is metadata/provenance/features only.

## Counts and distributions

Pilot coverage:

| Metric | Value |
| --- | ---: |
| Prototype rows | 512 |
| Distinct NCT trials | 417 |
| Distinct molecule-disease edges | 161 |
| Distinct molecules | 125 |
| Distinct diseases | 49 |
| Source-native gene links | 0 |
| Smoke embedding rows | 32 |

Selected distributions:

| Field | Distribution |
| --- | --- |
| `overall_status` | `TERMINATED`: 410; `WITHDRAWN`: 95; `SUSPENDED`: 7 |
| `trajectory_class` | `terminated_business_funding_or_feasibility`: 252; `terminated_unknown_reason`: 122; `safety_failure_or_harm`: 54; `withdrawn_unknown_reason`: 44; `failed_efficacy_or_endpoint`: 40 |
| `phase` | `PHASE3`: 168; `PHASE2`: 152; `PHASE4`: 82; `PHASE1; PHASE2`: 34; `PHASE1`: 25; `NA`: 23; `PHASE2; PHASE3`: 19; blank: 8; `EARLY_PHASE1`: 1 |
| `mapping_confidence` | `source_asserted_edge_nct_reference`: 512 |

The row selection intentionally prioritizes rows with non-empty `why_stopped`, then non-empty `result_summary_text`, then longer serialized text, so this pilot stresses fields beyond phase/status.

## Missingness

| Column | Non-empty | Empty | Empty fraction |
| --- | ---: | ---: | ---: |
| `trial_id` | 512 | 0 | 0.000 |
| `molecule_id` | 512 | 0 | 0.000 |
| `disease_id` | 512 | 0 | 0.000 |
| `gene_id` | 0 | 512 | 1.000 |
| `overall_status` | 512 | 0 | 0.000 |
| `phase` | 504 | 8 | 0.016 |
| `start_date` | 510 | 2 | 0.004 |
| `completion_date` | 501 | 11 | 0.021 |
| `enrollment_count` | 512 | 0 | 0.000 |
| `brief_summary` | 512 | 0 | 0.000 |
| `primary_outcome_text` | 509 | 3 | 0.006 |
| `secondary_outcome_text` | 436 | 76 | 0.148 |
| `eligibility_criteria` | 512 | 0 | 0.000 |
| `why_stopped` | 512 | 0 | 0.000 |
| `result_summary_text` | 269 | 243 | 0.475 |
| `source_text` | 512 | 0 | 0.000 |

## Embedding artifact

The emitted smoke embedding artifact is a real deterministic text vectorization using the repository dependency stack (`sklearn.feature_extraction.text.HashingVectorizer`, scikit-learn 1.8.0). It is not a fabricated embedding table and not a foundation/LLM clinical text model.

Configuration:

- model: `sklearn.feature_extraction.text.HashingVectorizer`
- version label: `scikit-learn-hashing-vectorizer@1.8.0+clinical_trials_structured_text_pilot_smoke_v1`
- dimensions: 384
- analyzer: word unigrams+bigrams
- alternate sign: false
- normalization: L2
- rows: 32, keyed by `trial_id`/`source_feature_hash`

The embedding-ready manifest records the same command and required input/output contract for replacing or augmenting this smoke scaffold with a reviewed foundation/LLM clinical-trial text encoder. No foundation embedding was run in this card because no accepted clinical text model/runtime was selected in the repo config for this task.

## Validation

Build/validation commands run:

```bash
uv run python artifacts/staged/t_clinical_trials_structured_text_pilot/build_clinical_trials_structured_text_pilot.py
uv run python -m py_compile artifacts/staged/t_clinical_trials_structured_text_pilot/build_clinical_trials_structured_text_pilot.py manage_db/stage_clinicaltrials_gov_production_candidate.py manage_db/stage_clinicaltrials_gov_evidence_layer.py
uv run --group dev pytest tests/test_stage_clinicaltrials_gov_production_candidate.py tests/test_stage_clinicaltrials_gov_evidence_layer.py -q
uv run python - <<'PY'
import duckdb, json
root='artifacts/staged/t_clinical_trials_structured_text_pilot'
proto=f'{root}/metadata/clinical_trials_structured_text_pilot.parquet'
emb=f'{root}/features/embeddings/clinical_trials_text/hashing_vectorizer/smoke_v1/part-000.parquet'
con=duckdb.connect()
out={
 'prototype_rows': con.execute(f"select count(*) from read_parquet('{proto}')").fetchone()[0],
 'distinct_trial_link_keys': con.execute(f"select count(distinct trial_link_key) from read_parquet('{proto}')").fetchone()[0],
 'blank_trial_ids': con.execute(f"select count(*) from read_parquet('{proto}') where trial_id is null or trial_id='' ").fetchone()[0],
 'blank_molecule_ids': con.execute(f"select count(*) from read_parquet('{proto}') where molecule_id is null or molecule_id='' ").fetchone()[0],
 'blank_disease_ids': con.execute(f"select count(*) from read_parquet('{proto}') where disease_id is null or disease_id='' ").fetchone()[0],
 'smoke_embedding_rows': con.execute(f"select count(*) from read_parquet('{emb}')").fetchone()[0],
 'embedding_dims': [r[0] for r in con.execute(f"select distinct embedding_dim from read_parquet('{emb}') order by 1").fetchall()],
 'embedding_vector_lengths': [r[0] for r in con.execute(f"select distinct array_length(embedding) from read_parquet('{emb}') order by 1").fetchall()],
}
print(json.dumps(out, indent=2, sort_keys=True))
PY
```

Observed targeted test output:

```text
11 passed in 0.99s
```

Validation summary from `validation_checks.json`:

```text
passed: true
prototype_rows: 512
smoke_embedding_rows: 32
duplicate_trial_link_keys: 0
blank_trial_ids: 0
blank_required_molecule_ids: 0
blank_required_disease_ids: 0
blank_source_text_hashes: 0
non_empty_text_rows: 512
gene_links_non_empty_rows: 0
embedding_dim_values: [384]
embedding_vector_length_values: [384]
embedding_nonfinite_values: 0
embedding_all_zero_rows: 0
blocking_failures: []
```

Additional DuckDB readability check:

```text
prototype_rows: 512
distinct_trial_link_keys: 512
blank_trial_ids: 0
blank_molecule_ids: 0
blank_disease_ids: 0
smoke_embedding_rows: 32
embedding_dims: [384]
embedding_vector_lengths: [384]
```

## Privacy, leakage, and modeling policy

- ClinicalTrials.gov rows are public aggregate trial metadata; this artifact does not contain participant-level data. Eligibility and outcome text can still encode sensitive disease/population criteria, so treat it as clinical public-source text with attribution/redistribution review before external release.
- `clinicalReportIds`, phase, status, trajectory, endpoints, outcomes, and `why_stopped` can leak indication/evidence labels for `molecule_treats_disease`. Mask or partition these sidecar features when evaluating held-out treatment edges.
- `COMPLETED` must not be interpreted as positive efficacy; this pilot emphasizes terminated/withdrawn/suspended rows and explicit stop text, but even explicit stop reasons remain metadata/evidence features unless a downstream clinical semantics policy accepts a target label.
- Clinical trial records remain metadata/provenance/feature sidecars. They are not canonical biomedical graph edges and not default PyG training topology.
- No canonical path under `gs://jouvencekb/kg/v2` or `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` was written by this task.

## Residual risks

- Coverage is bounded to the reviewed OpenTargets/ClinicalTrials.gov NCT seed already present in the project, not global CTGov/AACT coverage.
- Gene links are explicitly absent because the inspected source-native sidecar has molecule-disease/NCT support, not gene endpoints.
- The smoke embeddings are deterministic HashingVectorizer vectors. They validate keying/storage and provide an embedding-ready artifact, but should be replaced or augmented with a reviewed clinical text/foundation encoder for production modeling.
- Source text comes from a ClinicalTrials.gov API v2 snapshot, not an AACT relational snapshot. AACT remains preferable for a future all-CTGov mirror if exact snapshot selection and terms are recorded.
