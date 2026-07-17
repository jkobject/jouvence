# Clinical trials text embedding full staged artifact — t_1bf3fb33

Status: originally `staged fallback` / `review-required`; superseded by `t_957a3640` as `canonical promoted fallback sidecar` for the same full fallback table, while still not foundation/production embeddings.

Resolution note: see `docs/clinical_trials_canonical_features_resolution_t_957a3640.md`. The full 6,092-row HashingVectorizer fallback table from this card was promoted byte-identically to `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet` with SHA-256 `eb710df550f3442195800e9374acd57b4f70d70d74f88d89a089b856520ac264`. It remains explicitly labelled fallback because no accepted clinical/scientific foundation text encoder runtime/model/tokenizer is pinned in the repo.

This card builds the full staged trial-level text embedding feature table for the already reviewed ClinicalTrials.gov trial text sidecar. It writes only under `artifacts/staged/t_clinical_trials_text_embed_full/`; it does not write canonical KG paths and does not inject clinical-trial features into the default PyG/training graph.

## Source inventory

Inventory manifest: `artifacts/staged/t_clinical_trials_text_embed_full/manifests/source_inventory.json`.

| Source | Exact path | Rows | SHA-256 |
| --- | --- | ---: | --- |
| ClinicalTrials.gov text features | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet` | 6,092 | `b032da787626fa331e4f7dfc01c23755bc75fd62f7f9523183981f3a1e228beb` |
| ClinicalTrials.gov trial index | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_trial_index.parquet` | 6,092 | `71225856ab5eeec76a271d2bc0891b467ca78e9c5fc018ed66868fc7d638d9e0` |
| OpenTargets/ClinicalTrials.gov molecule-disease trial links | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/molecule_treats_disease_clinical_trials_gov_trial_links.parquet` | 7,804 | `60cabb54d8d36f700b7b18da05535cc2a6e2094a04ecf57f972ba0e973f605b8` |
| Existing canonical HashingVectorizer scaffold | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/scaffold_v1/part-000.parquet` | 6,092 | `f14b111f99f3ed8a59ae15dcd40dd5c334c4cbf4d3748039831b75c47b5f8862` |
| Frozen CTGov API raw manifest copy | `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/metadata/clinical_trials_gov_api_v2_raw_manifest_t_c4f67957.json` | n/a | `edab419bcb76f8511c12d627d4ab76427ec4417539b758b30c6bbb7b0562c13c` |

The source text feature hash was verified before processing against the accepted pilot/validator anchor: `b032da787626fa331e4f7dfc01c23755bc75fd62f7f9523183981f3a1e228beb` with 6,092 rows.

## New staged artifacts

All new artifacts are under `/Users/jkobject/.openclaw/workspace/work/txgnn/artifacts/staged/t_clinical_trials_text_embed_full/`.

| Artifact | Path | Rows | SHA-256 / purpose |
| --- | --- | ---: | --- |
| Full staged trial text embedding table | `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet` | 6,092 | `eb710df550f3442195800e9374acd57b4f70d70d74f88d89a089b856520ac264` |
| Build script | `build_clinical_trials_text_embed_full.py` | n/a | Reproducible local builder; validates source hash and writes only under staged root. |
| Source inventory | `manifests/source_inventory.json` | n/a | Exact paths, row counts, hashes, and schemas. |
| Embedding manifest | `manifests/embedding_manifest.json` | n/a | Rerun command, key contract, embedding config, runtime inventory, and blocker to foundation embeddings. |
| Machine report | `reports/clinical_trials_text_embedding_full_report.json` | n/a | Counts, field coverage, validation summary, policy notes. |
| Validation checks | `reports/validation_checks.json` | n/a | Readability/key/vector/reconciliation checks. |

Rerun command:

```bash
uv run python artifacts/staged/t_clinical_trials_text_embed_full/build_clinical_trials_text_embed_full.py
```

Observed builder output:

```text
status: PASS
embedding_status: staged fallback
embedding_rows: 6092
distinct_nct_ids: 6092
artifact_sha256: eb710df550f3442195800e9374acd57b4f70d70d74f88d89a089b856520ac264
blocking_failures: []
```

## Embedding artifact schema and status

The output is keyed one row per source NCT trial:

- `trial_id`, `nct_id` — ClinicalTrials.gov accession.
- `source_feature_key`, `source_feature_hash`, `source_text_hash` — join/hash linkage to `features/clinical_trials_gov_trial_text_features.parquet`.
- `source_text_hash_recomputed`, `source_text_hash_matches` — row-level integrity check against the serialized source text.
- `has_<field>` and `modeled_has_<field>` coverage flags for source text fields.
- `embedding_status` — always `staged fallback` for this run.
- `embedding_blocker` — explicit reason a foundation/LLM clinical text encoder was not used.
- `embedding_model`, `embedding_version`, `embedding_dim`, `embedding`, `pooling`, `normalization`.
- `staging_policy` — states this is a staged sidecar and not default PyG/training graph input.

Embedding configuration:

- model: `sklearn.feature_extraction.text.HashingVectorizer`
- version: `scikit-learn-hashing-vectorizer@1.8.0+clinical_trials_gov_trial_text_full_staged_fallback_v1`
- dimensions: 384
- analyzer: word unigrams+bigrams
- alternate sign: false
- normalization: L2
- dtype/storage: `float32` list column
- batching/device: single local sklearn sparse transform over 6,092 rows on CPU

This is a real deterministic vectorization artifact over all trial source-text rows, but it is not a production/full foundation embedding. The blocker to true clinical/scientific foundation embeddings is recorded in the manifest/report: the project env has `torch` but not `sentence_transformers` or `transformers`, and `pyproject.toml` declares sklearn but no accepted/configured clinical text encoder runtime. Cached HuggingFace model files alone were not treated as a usable production runtime.

## Text field coverage

The source text was built from ClinicalTrials.gov titles/summaries/outcomes/eligibility/why-stopped/result summaries and related source text fields, not phase/status alone.

| Field | Non-empty rows | Empty rows | Non-empty fraction |
| --- | ---: | ---: | ---: |
| `brief_title` | 6,092 | 0 | 1.000 |
| `official_title` | 5,988 | 104 | 0.983 |
| `brief_summary` | 6,092 | 0 | 1.000 |
| `detailed_description` | 3,476 | 2,616 | 0.571 |
| `condition_text` | 6,092 | 0 | 1.000 |
| `intervention_text` | 6,092 | 0 | 1.000 |
| `primary_outcome_text` | 5,807 | 285 | 0.953 |
| `secondary_outcome_text` | 5,019 | 1,073 | 0.824 |
| `eligibility_criteria` | 6,092 | 0 | 1.000 |
| `why_stopped` | 572 | 5,520 | 0.094 |
| `result_summary_text` | 2,162 | 3,930 | 0.355 |

## Validation

Commands run:

```bash
uv run python artifacts/staged/t_clinical_trials_text_embed_full/build_clinical_trials_text_embed_full.py
uv run python -m py_compile artifacts/staged/t_clinical_trials_text_embed_full/build_clinical_trials_text_embed_full.py manage_db/stage_clinicaltrials_gov_production_candidate.py manage_db/stage_clinicaltrials_gov_evidence_layer.py
uv run --group dev pytest tests/test_stage_clinicaltrials_gov_production_candidate.py tests/test_stage_clinicaltrials_gov_evidence_layer.py -q
uv run python - <<'PY'
import duckdb, json, pyarrow.parquet as pq, numpy as np
emb='artifacts/staged/t_clinical_trials_text_embed_full/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet'
source='/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/clinical_trials_gov_trial_text_features.parquet'
con=duckdb.connect()
out={
 'source_rows': con.execute(f"select count(*) from read_parquet('{source}')").fetchone()[0],
 'embedding_rows': con.execute(f"select count(*) from read_parquet('{emb}')").fetchone()[0],
 'distinct_nct_ids': con.execute(f"select count(distinct nct_id) from read_parquet('{emb}')").fetchone()[0],
 'blank_nct_ids': con.execute(f"select count(*) from read_parquet('{emb}') where nct_id is null or trim(nct_id)='' ").fetchone()[0],
 'embedding_dims': [r[0] for r in con.execute(f"select distinct embedding_dim from read_parquet('{emb}') order by 1").fetchall()],
 'embedding_vector_lengths': [r[0] for r in con.execute(f"select distinct array_length(embedding) from read_parquet('{emb}') order by 1").fetchall()],
 'embedding_status': [r[0] for r in con.execute(f"select distinct embedding_status from read_parquet('{emb}') order by 1").fetchall()],
 'hash_mismatches': con.execute(f"select count(*) from read_parquet('{emb}') where not source_text_hash_matches").fetchone()[0],
 'fallback_without_blocker': con.execute(f"select count(*) from read_parquet('{emb}') where embedding_status='staged fallback' and (embedding_blocker is null or trim(embedding_blocker)='')").fetchone()[0],
 'staging_policy_not_default_pyg_rows': con.execute(f"select count(*) from read_parquet('{emb}') where staging_policy like '%not default PyG/training graph%'").fetchone()[0],
}
vecs=pq.read_table(emb, columns=['embedding']).column('embedding').to_pylist()
out['nonfinite_values']=sum(int((~np.isfinite(np.asarray(v,dtype=np.float32))).sum()) for v in vecs)
out['all_zero_rows']=sum(int(np.allclose(np.asarray(v,dtype=np.float32),0.0)) for v in vecs)
out['sample_norms']=[float(np.linalg.norm(np.asarray(v,dtype=np.float32))) for v in vecs[:5]]
print(json.dumps(out, indent=2, sort_keys=True))
PY
```

Observed targeted test output:

```text
11 passed in 1.10s
```

Independent artifact validation output:

```text
source_rows: 6092
embedding_rows: 6092
distinct_nct_ids: 6092
blank_nct_ids: 0
embedding_dims: [384]
embedding_vector_lengths: [384]
embedding_status: ['staged fallback']
hash_mismatches: 0
fallback_without_blocker: 0
nonfinite_values: 0
all_zero_rows: 0
sample_norms: [1.0, 1.0, 1.0, 1.0, 1.0]
staging_policy_not_default_pyg_rows: 6092
```

Producer validation summary from `reports/validation_checks.json`:

```text
passed: true
artifact_rows: 6092
source_rows: 6092
row_count_matches_source: true
distinct_nct_ids: 6092
distinct_embedding_keys: 6092
blank_nct_ids: 0
duplicate_nct_ids: 0
duplicate_embedding_keys: 0
source_text_hash_mismatch_rows: 0
embedding_dim_values: [384]
embedding_vector_length_values: [384]
embedding_nonfinite_values: 0
embedding_all_zero_rows: 0
blocking_failures: []
```

## Privacy, leakage, and downstream masking guidance

- ClinicalTrials.gov rows are public aggregate trial records, not participant-level records. Eligibility criteria, outcome text, stop reasons, and result summaries may still encode sensitive disease/population context; keep attribution and redistribution review before external release.
- Trial text can leak treatment indication/evidence for `molecule_treats_disease`, especially through outcomes, why-stopped text, result summaries, conditions, and intervention names. Downstream held-out treatment-edge evaluations should mask or partition these features so clinical evidence text for the target edge is not available to the model when assessing zero-shot prediction.
- `COMPLETED`, phase, and overall status are not used alone as efficacy labels. These embeddings remain clinical metadata/provenance/features, not truth labels.
- Clinical trial text features remain disconnected from default PyG/training graph topology unless a later reviewed task opts in.

## Next promotion criteria

Before any canonical or production/full embedding promotion:

1. Select and pin an accepted clinical/scientific text embedding runtime, model, tokenizer, and dependency set (for example a reviewed BioBERT/S-BioBERT/SapBERT-style encoder if appropriate for trial prose).
2. Run the encoder with recorded batching/device/version details and sample vector sanity checks.
3. Preserve this same one-row-per-NCT key contract, source hash checks, field coverage flags, and no-default-PyG policy.
4. Run independent reviewer/tester validation of readability, key uniqueness, vector finite/nonzero checks, row reconciliation, and leakage guidance.
5. Promote only after reviewer acceptance; this task performs no canonical write.

## Residual risks

- The emitted table is a deterministic full-row HashingVectorizer fallback, not semantic/foundation clinical embeddings.
- Coverage is bounded to the accepted 6,092-row ClinicalTrials.gov source sidecar, not global CTGov/AACT.
- The feature table contains trial metadata that can leak drug/disease evidence if used naively in edge prediction benchmarks.
- No default graph integration was performed; consumers must opt in deliberately after review.
