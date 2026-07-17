# ClinicalTrials.gov evidence + text-feature production candidate — t_c4f67957

Status: `staged production candidate`; canonical support/evidence/feature promotion was later performed by `t_f8841ff7` and is documented in `docs/clinical_trials_gov_canonical_promotion_t_f8841ff7.md`.

This card scales the accepted bounded prototype from `t_f65a077a`/`t_d3be70e8` into a reproducible staged candidate for the existing staged OpenTargets `molecule_treats_disease` clinical evidence seed. The build covers all NCT IDs referenced by that selected source evidence, not all possible ClinicalTrials.gov drug/disease trials.

## Source snapshot

Preferred AACT snapshot selection was not available inside this card, so the reproducibility strategy is a frozen ClinicalTrials.gov API v2 raw-response cache:

- API: `https://clinicaltrials.gov/api/v2/studies`, `query.id` batches.
- Raw cache root: `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/raw/`.
- Raw chunk files: `raw/ctgov_api_v2_query_id_chunks/chunk_*.json`.
- Manifest: `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/raw/ctgov_api_v2_raw_manifest.json`.
- Manifest checksum: `fbcb5b03a7577c0cc357983c7bc65d8699d0dd4e551924ddb653ba47478a8804`.
- Checksum semantics: SHA-256 of the canonical manifest payload excluding `manifest_path`/`manifest_sha256` fields; each raw chunk also has a direct file SHA-256 in the manifest.
- Requested NCT manifest checksum: `255e581bebbe713e79fc20a3ee83dcbc765a8fd5290d3aedda9286e0cb80af89`.
- Input staged OpenTargets evidence: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/staging/opentargets-clinical-drug-evidence-20260622-t_ceee5d53/evidence/molecule_treats_disease.parquet`.
- Input staged OpenTargets evidence SHA-256: `a11e496fd82aa17d3b873301035db14c35090e6e9082500d5412cfbf7d8692df`.

License/terms note: ClinicalTrials.gov/NLM public API material is used here for staging. Review ClinicalTrials.gov/NLM redistribution/attribution terms before canonical promotion or external redistribution. AACT remains preferred for a future relational all-CTGov mirror.

## Artifact outputs

All paths are repo-relative under `/Users/jkobject/.openclaw/workspace/work/txgnn`.

| Artifact | Path | Purpose |
| --- | --- | --- |
| Raw manifest | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/raw/ctgov_api_v2_raw_manifest.json` | Frozen source snapshot manifest, chunk checksums, requested/returned NCT IDs. |
| Trial index | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/metadata/clinical_trials_gov_trial_index.parquet` | One row per fetched NCT with source-native trial metadata. |
| Molecule-disease trial links | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/metadata/molecule_disease_trial_links.parquet` | Edge-key to NCT link table seeded by staged OpenTargets clinicalReportIds. |
| Evidence rows | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/evidence/molecule_treats_disease.clinical_trials_gov.production_candidate.parquet` | Evidence-schema-compatible `molecule_treats_disease` support rows keyed by edge and NCT. |
| Trial text features | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/features/clinical_trials_gov_trial_text_features.parquet` | NCT-keyed free-text serialization with field inventory and SHA-256 text hash. |
| Trial text embeddings | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/production_candidate_v1/part-000.parquet` | 384-dim deterministic HashingVectorizer scaffold keyed to text features. |
| Validation JSON | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/reports/validation_checks.json` | Endpoint/evidence/key/vector validation. |
| Machine report | `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/reports/clinical_trials_gov_production_candidate_report.json` | Counts, distributions, source metadata, rerun command, artifact map. |

Total staged directory size after build: about 445M, 69 files.

## Counts

| Metric | Value |
| --- | ---: |
| Source edge-NCT links | 7,804 |
| Distinct supported canonical `molecule_treats_disease` edge keys | 377 |
| Requested NCT IDs | 6,092 |
| Fetched trial rows | 6,092 |
| Fetch errors | 0 |
| Evidence rows | 7,804 |
| Trial text feature rows | 6,092 |
| Trial text embedding rows | 6,092 |
| Non-empty trial text rows | 6,092 |

Selected distributions:

- Overall status: `COMPLETED` 4,213; `UNKNOWN` 655; `TERMINATED` 498; `RECRUITING` 276; `ACTIVE_NOT_RECRUITING` 186; `WITHDRAWN` 174; smaller classes include `NOT_YET_RECRUITING`, `SUSPENDED`, `APPROVED_FOR_MARKETING`, `AVAILABLE`, `NO_LONGER_AVAILABLE`, `ENROLLING_BY_INVITATION`.
- Phase: `PHASE3` 2,121; `PHASE2` 1,547; `PHASE4` 852; `PHASE1` 594; `NA` 298; blank 295; mixed/early phases 385 total.
- Trajectory class: `completed_outcome_unknown` 4,213; `unknown_trial_trajectory` 678; `active_or_recruiting_unknown_outcome` 519; `terminated_business_funding_or_feasibility` 274; `terminated_unknown_reason` 216; `withdrawn_unknown_reason` 101; `safety_failure_or_harm` 54; `failed_efficacy_or_endpoint` 37.

## Staged schemas

### `metadata/clinical_trials_gov_trial_index.parquet`

Source-native trial fields include:

- Identifiers/provenance: `nct_id`, `source_record_id`, `source_url`, `source_dataset`, `source_release`, `raw_response_sha256`, `fetched_at`.
- Trial status/trajectory: `overall_status`, `why_stopped`, `trajectory_class`.
- Design: `phase`, `study_type`, `allocation`, `masking`, `enrollment_count`, `enrollment_type`.
- Dates: `start_date`, `primary_completion_date`, `completion_date`.
- Source text/metadata: `brief_title`, `official_title`, `brief_summary`, `detailed_description`, `conditions`, `intervention_names`, `intervention_types`, `intervention_details`, `primary_endpoints`, `secondary_endpoints`, `primary_outcome_text`, `secondary_outcome_text`, `eligibility_criteria`, `result_summary_text`.
- Sponsor/publications: `lead_sponsor`, `lead_sponsor_class`, `collaborators`, `publication_ids`.

### `metadata/molecule_disease_trial_links.parquet`

Key columns:

- `edge_key`, `relation`, `x_id`, `x_type`, `y_id`, `y_type`, `nct_id`.
- Source seed fields from staged OpenTargets evidence: `predicate`, `study_id`, `text_span`, `source`, `source_dataset`, `source_record_id`, `evidence_score`, `release`.
- Mapping audit fields: `mapping_source`, `mapping_method`, `mapping_confidence`, `source_study_id_raw`, `source_text_span_hash`.

### Evidence rows

Evidence rows conform to `manage_db.kg_evidence.evidence_schema()` and preserve:

- `edge_key`, `relation=molecule_treats_disease`, `x_id/x_type=molecule`, `y_id/y_type=disease`.
- `evidence_type=clinical_trial_metadata`, `source=ClinicalTrials.gov`, `source_dataset=ClinicalTrials.gov API v2 raw query.id snapshot`.
- `source_record_id=ClinicalTrials.gov:<NCT_ID>`, `study_id=<NCT_ID>`, PMIDs in `paper_id` when CTGov exposes references.
- `direction=<trajectory_class>` and `predicate=clinical trial metadata; <trajectory_class>`.
- `text_span` summarizes NCT, status, phase, trajectory, sponsor, conditions, interventions, primary endpoints, stop reason, and mapping confidence.

### Text feature / embedding tables

Text features are keyed by `nct_id`/`source_feature_key`, include deterministic `source_text`, `source_field_inventory`, `source_text_hash`, `source_text_length`, and field-preserving text columns. Text length range: min 370, median 5,853, max 44,782 characters.

Embedding scaffold:

- Model: `sklearn.feature_extraction.text.HashingVectorizer`.
- Version: `scikit-learn-hashing-vectorizer@1.8.0+clinical_trials_gov_trial_text_production_candidate_v1`.
- Dimension/vector length: 384.
- Dtype/format: float32 list, L2-normalized hashing vectorizer.
- Keyed to the text features through `source_feature_key` and `source_feature_hash`.

These embeddings are deterministic local surrogate feature artifacts for schema/key validation and downstream wiring. They are not foundation clinical text embeddings.

## Validation

Validation file: `artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate/reports/validation_checks.json`.

Result: PASS, no blocking failures.

Checks:

- Duplicate trial-index NCT IDs: 0.
- Duplicate edge-NCT links: 0.
- Duplicate evidence edge-NCT rows: 0.
- Links without trial index: 0.
- Trial index without link: 0.
- Features without trial index: 0.
- Embeddings without features: 0.
- Feature rows match trial rows: true.
- Embedding rows match feature rows: true.
- Link x anti-join against canonical molecule nodes: 0 missing.
- Link y anti-join against canonical disease nodes: 0 missing.
- Links without canonical `molecule_treats_disease` edge: 0.
- Evidence without link: 0.
- Links without evidence: 0.
- Wrong relation/type rows: 0.
- Blank NCT/study IDs: 0.
- Embedding dim values: `[384]`.
- Embedding vector length values: `[384]`.
- Non-finite embedding values: 0.
- All-zero embedding rows: 0.

## Trial trajectory semantics and training policy

The staged `trajectory_class` is conservative. `COMPLETED` means `completed_outcome_unknown`, not positive efficacy. Active/recruiting trials are unknown outcome. Terminated/withdrawn/suspended trials are only classified as safety/business/efficacy failure when `whyStopped` text explicitly supports that class; otherwise they remain unknown-reason trajectory classes.

Training-use policy:

1. Keep `molecule_treats_disease` as the deduplicated graph assertion relation.
2. Use clinical trial phase/status/trajectory/endpoint/sponsor/enrollment/date/text features as leakage-aware evidence features or edge weights.
3. Do not convert failed, terminated, withdrawn, completed, or unknown trials into direct negative biomedical graph edges by default.
4. For held-out `molecule_treats_disease` labels, mask evidence features that directly reveal the target label.
5. Treat endpoint mismatch and condition/intervention mismatch as metadata/features until a source-native assertion policy is accepted.

## Rerun commands

Production candidate build:

```bash
uv run python -m manage_db.stage_clinicaltrials_gov_production_candidate \
  --out-root artifacts/staged/t_c4f67957_clinical_trials_gov_production_candidate \
  --opentargets-evidence /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/staging/opentargets-clinical-drug-evidence-20260622-t_ceee5d53/evidence/molecule_treats_disease.parquet \
  --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --batch-size 100
```

Code/test validation:

```bash
uv run python -m py_compile manage_db/stage_clinicaltrials_gov_production_candidate.py
uv run --group dev pytest tests/test_stage_clinicaltrials_gov_production_candidate.py tests/test_stage_clinicaltrials_gov_evidence_layer.py -q
```

Observed targeted test output after final code patch:

```text
11 passed in 1.21s
```

## Limitations / residual risks

- Staged-only production candidate, not canonical promotion.
- Source snapshot is frozen CTGov API v2 JSON cache, not an AACT relational export. The raw cache is reproducible for this card, but AACT is still preferred for future full ClinicalTrials.gov mirror work.
- Coverage is complete for the selected existing staged OpenTargets `molecule_treats_disease` NCT seed, not all CTGov trials and not all possible molecule/disease mappings.
- CTGov intervention/condition strings are not canonical molecule/disease mapping by themselves; mapping confidence remains source-edge + source NCT reference.
- Endpoint outcome interpretation remains conservative. Structured results and publications are preserved as text where exposed but not interpreted as positive/negative efficacy labels.
- HashingVectorizer text embeddings are deterministic scaffolds, not final foundation embeddings.
- This was produced in the shared artifact workspace, which the project context says is not a TxGNN-scoped PR checkout. Review should consider the artifacts and code paths directly; do not treat the shared workspace diff as PR-ready.
