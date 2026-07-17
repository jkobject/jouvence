# Clinical trials evidence layer prototype — t_f65a077a

Status: `review-required` staged prototype; no canonical KG files were written.

## Goal

Current Jouvence KG has clinical/pharmacology topology (`molecule_treats_disease`, `molecule_contraindicates_disease`, indications, warnings), but it does not represent trial trajectory detail: phase reached, status, endpoints, termination/failure reason, sponsor context, comparator/intervention context, dates, enrollment, NCT IDs, publications, and mismatch between trial endpoint and KG mechanism/indication hypotheses.

This task audits the current state and stages a bounded ClinicalTrials.gov metadata layer as evidence/sidecar material, not default biomedical graph topology.

## Current KG clinical/pharmacology inventory

Source of truth inspected: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2` and current docs.

| Item | Current state |
| --- | --- |
| `edges/molecule_treats_disease.parquet` | canonical+validated; 14,135 rows; base edge columns only (`x_id`, `x_type`, `y_id`, `y_type`, `relation`, `display_relation`, `source`, `credibility`). |
| `evidence/molecule_treats_disease.parquet` | absent in canonical evidence root. |
| Staged OpenTargets positive indication evidence | 481 staged evidence rows in `v2/staging/opentargets-clinical-drug-evidence-20260622-t_ceee5d53/evidence/molecule_treats_disease.parquet`; supports 481/14,135 canonical edge keys; stages positive indication only. |
| `edges/molecule_contraindicates_disease.parquet` | canonical+validated; 30,675 rows; base edge columns only. |
| `evidence/molecule_contraindicates_disease.parquet` | absent in canonical evidence root. |
| OpenTargets `drug_warning` | previously audited as warning/withdrawal/toxicity-class material, not clean `molecule_contraindicates_disease` support. |
| Molecule node clinical fields | `nodes/molecule.parquet` has columns including `max_clinical_trial_phase`, `is_approved`, `has_been_withdrawn`, `black_box_warning`, but sampled canonical DrugBank rows were mostly null; this is node metadata, not trial-level trajectory. |

Existing relation coverage already says: promote positive indication evidence only for `molecule_treats_disease`; find a contraindication-specific source for `molecule_contraindicates_disease`; do not reuse positive indication as contraindication evidence.

## Source availability audit

| Source | Access checked | Useful fields | Constraints / decision |
| --- | --- | --- | --- |
| ClinicalTrials.gov API v2 | Live GET to `https://clinicaltrials.gov/api/v2/studies/NCT00496197?format=json` returned HTTP 200 JSON. Prototype used this API. | NCT ID, overall status, why stopped, phase, design, arms/interventions, conditions, primary/secondary endpoints, sponsor/collaborators, dates, enrollment, PMIDs, brief/detailed descriptions, eligibility criteria, intervention descriptions, outcome descriptions/timeframes, and result modules when present. | Good bounded prototype source. CTGov does not provide a universal success/failure label; completion is not positive efficacy. `result_summary_text` is available only for fetched rows with API v2 results modules. Verify NLM/ClinicalTrials.gov redistribution terms before canonical promotion. |
| AACT / CTTI | Root and data dictionary pages returned HTTP 200; a guessed `/download` endpoint returned 404. | Relational bulk CTGov mirror; better for full-scale reproducible extraction. | Use for next full build only after selecting snapshot/download URL and recording snapshot date. |
| OpenTargets clinical indication | Existing staged evidence and script inspected; source has `maxClinicalStage` and `clinicalReportIds` including NCT IDs. | Drug/disease mappings, max clinical stage, clinical report IDs/NCT IDs, ChEMBL drug IDs. | Positive indication/trial-stage support only. It is not endpoint/outcome/failure evidence and not contraindication support. |
| ChEMBL drug indication API | Live GET to `https://www.ebi.ac.uk/chembl/api/data/drug_indication.json?limit=1` returned HTTP 200 JSON with `drugind_id`, `efo_id`, `efo_term`, `indication_refs` including NCT IDs. | Indication rows, max phase/phase metadata, EFO terms, reference IDs. | Good source for independent indication/phase cross-check and NCT seeds. It still does not by itself encode trial endpoint success/failure. |
| FDA openFDA drug label API | Live GET to `https://api.fda.gov/drug/label.json?limit=1` returned HTTP 200 JSON. | Label sections including indications/contraindications/warnings when present. | Useful for label/approval/contraindication text, but requires disease/molecule mapping and label-section parsing; not used in this bounded prototype. openFDA warns not to rely on it for medical decisions. |
| EMA labels/EPAR | Not fetched in prototype. | EPAR status/withdrawal/therapeutic indication metadata. | Candidate for later label/withdrawal layer; needs source-specific license/terms and mapping work. |
| PubMed/PMC/OpenAlex publications | CTGov API references may expose PMIDs; prototype preserves PMIDs as evidence metadata only. | Publication IDs and possible results papers. | Literature should remain evidence metadata/catalog sidecar, not default graph topology. |

## Prototype artifacts

Command run:

```bash
uv run python -m manage_db.stage_clinicaltrials_gov_evidence_layer \
  --max-edges 12 \
  --max-ncts-per-edge 2 \
  --max-studies 20 \
  --out-root artifacts/staged/t_f65a077a_clinical_trials_evidence_layer
```

Outputs:

| Artifact | Purpose |
| --- | --- |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/metadata/clinical_trials_gov_trial_index.parquet` | One row per fetched NCT ID with trial-level metadata. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/metadata/molecule_disease_trial_links.parquet` | Link table from current `molecule_treats_disease` edge key to NCT IDs seeded by staged OpenTargets evidence. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/evidence/molecule_treats_disease.clinical_trials_gov.prototype.parquet` | Evidence-schema-compatible rows keyed by current `molecule_treats_disease` edge and ClinicalTrials.gov NCT ID. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/features/clinical_trials_gov_trial_text_features.parquet` | NCT-keyed free-text feature table with serialized trial text, source field inventory, SHA-256 text hash, extraction version, and source/license metadata. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/prototype_v1/part-000.parquet` | NCT-keyed deterministic local surrogate text embedding scaffold, 384-dimensional `sklearn.HashingVectorizer` vectors keyed to the text feature rows. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/reports/clinical_trials_gov_evidence_layer_report.json` | Machine-readable counts, distributions, example rows, source decisions. |
| `artifacts/staged/t_f65a077a_clinical_trials_evidence_layer/reports/validation_checks.json` | Support/shape validation against canonical edge keys. |

Prototype counts:

| Metric | Value |
| --- | ---: |
| candidate edge-NCT links | 20 |
| requested NCT IDs | 20 |
| fetched trials | 20 |
| fetch errors | 0 |
| prototype evidence rows | 20 |
| distinct supported `molecule_treats_disease` edge keys | 12 |
| NCT-keyed text feature rows | 20 |
| NCT-keyed text embedding rows | 20 |
| non-empty text feature rows | 20 |
| evidence keys without canonical edge | 0 |
| wrong relation/type rows | 0 |
| blank NCT/study IDs | 0 |

Text feature non-empty field coverage in the bounded sample:

| Field | Non-empty rows |
| --- | ---: |
| `brief_summary` | 20 |
| `detailed_description` | 11 |
| `intervention_text` | 20 |
| `primary_outcome_text` | 17 |
| `secondary_outcome_text` | 14 |
| `eligibility_criteria` | 20 |
| `why_stopped` | 1 |
| `result_summary_text` | 10 |

The staged text feature rows range from 1,276 to 30,974 characters. The embedding scaffold has 20 rows, exactly matching the text features, with model `sklearn.feature_extraction.text.HashingVectorizer`, version `scikit-learn-hashing-vectorizer@1.8.0+clinical_trials_gov_trial_text_prototype_v1`, dimension 384, and vector length 384 for every row. These are deterministic surrogate embeddings for staging/schema validation, not production foundation-model embeddings.

Observed distributions from the bounded sample:

| Field | Distribution |
| --- | --- |
| `overall_status` | `COMPLETED`: 17; `TERMINATED`: 1; `UNKNOWN`: 2 |
| `phase` | `PHASE4`: 14; `PHASE3`: 3; `PHASE2`: 3 |
| `trajectory_class` | `completed_outcome_unknown`: 17; `terminated_unknown_reason`: 1; `unknown_trial_trajectory`: 2 |
| `lead_sponsor_class` | `INDUSTRY`: 10; `OTHER`: 7; `NIH`: 3 |

Example prototype evidence rows include:

- `molecule_treats_disease|DB00196|MONDO:0002026` / `NCT00496197`: Pfizer phase 4 candidiasis trial; primary endpoint records global response success/failure; status `COMPLETED`; trajectory class `completed_outcome_unknown`; PMIDs preserved.
- `molecule_treats_disease|DB00201|MONDO:0005277` / `NCT01248468`: Novartis migraine phase 4 trial; interventions aspirin/acetaminophen/caffeine, sumatriptan, placebo; primary endpoint pain-free at 2 hours; trajectory `completed_outcome_unknown`.
- `molecule_treats_disease|DB00215|MONDO:0002009` / `NCT01460212`: depression phase 4 trial; status `UNKNOWN`; trajectory `unknown_trial_trajectory`.

## Candidate source-native schema

Do not add trial nodes to the default training graph. The source-native schema should be a sidecar metadata/evidence layer keyed by `NCT ID` and canonical edge keys.

### `metadata/clinical_trials_gov_trial_index.parquet`

Recommended columns:

- `nct_id` — stable trial accession and source record ID.
- `brief_title`, `official_title`.
- `overall_status`, `why_stopped`, `trajectory_class`.
- `phase`, `study_type`, `allocation`, `masking`.
- `enrollment_count`, `enrollment_type`.
- `start_date`, `primary_completion_date`, `completion_date`.
- `conditions` — CTGov condition text; not canonical disease IDs by itself.
- `intervention_names`, `intervention_types` — raw CTGov intervention names/types; not canonical molecule IDs by itself.
- `primary_endpoints`, `secondary_endpoints`, endpoint counts.
- Free text: `brief_summary`, `detailed_description`, `intervention_details`, `primary_outcome_text`, `secondary_outcome_text`, `eligibility_criteria`, and `result_summary_text` when API v2 results modules are present.
- `lead_sponsor`, `lead_sponsor_class`, `collaborators`.
- `publication_ids` — PMID list where CTGov exposes references.
- `source_url`, `fetched_at`.

### `features/clinical_trials_gov_trial_text_features.parquet`

Prototype columns:

- `nct_id`, `source_feature_key` — NCT-keyed join back to trial index and edge-trial links.
- `source_text` — deterministic newline-separated serialization of non-empty trial free-text fields.
- `source_field_inventory` — JSON list of text fields present for the row.
- `source_text_hash` — SHA-256 hash of `source_text` for downstream embedding reproducibility.
- `source_text_length`.
- Field-preserving text columns: `brief_title`, `official_title`, `brief_summary`, `detailed_description`, `condition_text`, `intervention_text`, `primary_outcome_text`, `secondary_outcome_text`, `eligibility_criteria`, `why_stopped`, `result_summary_text`.
- `extraction_version`, `source_dataset`, `source_release`, `license`, `created_at`.

### `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/prototype_v1/part-000.parquet`

Prototype columns:

- `embedding_key`, `nct_id`, `source_feature_table`, `source_feature_key`, `source_feature_hash`.
- `modality = clinical_trial_free_text`.
- `embedding_model = sklearn.feature_extraction.text.HashingVectorizer`.
- `embedding_version = scikit-learn-hashing-vectorizer@1.8.0+clinical_trials_gov_trial_text_prototype_v1`.
- `embedding_dim = 384`, `embedding_dtype = float32`, `embedding_format = list_float32`, `embedding`.
- `pooling`, `normalization`, `preprocessing`, `input_length`, `window_count`, `source_feature_release`, `provenance`, `license`, `citation`.

This scaffold validates keying, hash linkage, metadata, and storage layout for downstream feature consumers. It should be replaced or augmented by an accepted foundation-model clinical/trial text encoder before production/full KG use.

### `metadata/molecule_disease_trial_links.parquet`

Recommended columns:

- `edge_key`, `relation`, `x_id`, `x_type`, `y_id`, `y_type`.
- `nct_id`.
- `mapping_source` / `mapping_method` in the full build: e.g. OpenTargets `clinicalReportIds`, ChEMBL `indication_refs`, direct intervention+disease mapping, manual curation.
- `mapping_confidence` and mapping caveats: exact source edge match, intervention-name mismatch, condition-to-disease mismatch, combination therapy, comparator-only mention.

### Evidence row representation

For current KG compatibility, emit evidence-schema-compatible rows for supported `molecule_treats_disease` edges:

- `evidence_type`: `clinical_trial_metadata`.
- `source`: `ClinicalTrials.gov`.
- `source_dataset`: `ClinicalTrials.gov API v2` or AACT snapshot name.
- `source_record_id`: `ClinicalTrials.gov:<NCT_ID>`.
- `study_id`: `<NCT_ID>`.
- `paper_id`: semicolon-delimited PMID IDs when present.
- `direction`: use trajectory class, not a biomedical edge polarity.
- `predicate`: `clinical trial metadata; <trajectory_class>`.
- `text_span`: compact concatenation of NCT, status, phase, endpoint(s), sponsor, interventions, conditions, why stopped.

This preserves trial facts as source evidence while avoiding pollution of graph topology.

## Trial trajectory classes

The prototype classifier is deliberately conservative:

| Class | Meaning |
| --- | --- |
| `completed_outcome_unknown` | Trial completed, but CTGov status alone does not prove positive efficacy. |
| `active_or_recruiting_unknown_outcome` | Recruiting/active/not-yet-recruiting; no outcome direction. |
| `failed_efficacy_or_endpoint` | `whyStopped` explicitly mentions efficacy/futility/lack of effect/failed endpoint. |
| `safety_failure_or_harm` | `whyStopped` explicitly mentions safety/adverse/toxicity/harm. |
| `terminated_business_funding_or_feasibility` | `whyStopped` explicitly mentions funding/business/sponsor/resource/recruitment/accrual/feasibility. |
| `terminated_unknown_reason` | Terminated/suspended without classifiable stop reason. |
| `withdrawn_unknown_reason` | Withdrawn without classifiable reason. |
| `unknown_trial_trajectory` | Unknown or unhandled status. |

Positive efficacy should not be inferred from `COMPLETED`; it needs structured results, label approval evidence, endpoint-level interpretation, or reviewed literature/curation.

## Training / modeling recommendation

Use clinical-trial trajectory as evidence features or edge weights, not as direct positive/negative biomedical graph edges by default.

Recommended use:

1. Keep `molecule_treats_disease` as the deduplicated graph assertion relation.
2. Add trial metadata as per-edge evidence features: max reached phase, status/trajectory, endpoint type/text embedding, sponsor class, enrollment, dates, trial count, completed/terminated counts, explicit failure/safety/business counts.
3. For link prediction on `molecule_treats_disease`, mask target-label evidence for held-out edges. A held-out positive indication edge must not be embedded from positive indication/trial evidence that directly reveals the label.
4. Treat failed/terminated trials as task-specific negative/weak-negative features only after a leakage and clinical semantics policy. A failed trial can mean wrong endpoint, wrong population, dose, comparator, safety, business termination, or true lack of efficacy.
5. Model endpoint mismatch as metadata/feature: compare CTGov `conditions`, intervention names, primary endpoint text, and KG-supported mechanism/indication hypotheses; do not create a new topology relation until a source-native assertion is approved.

## Recommended next build card

Title: `CLINICAL-TRIALS-FULL: AACT/CTGov snapshot trial metadata evidence sidecar`

Assignee suggestion: `dev` builder, followed by independent `reviewer`/`tester` gate.

Acceptance sketch:

1. Select a reproducible AACT snapshot or ClinicalTrials.gov API snapshot strategy and record source terms.
2. Expand NCT seeds from OpenTargets `clinicalReportIds`, ChEMBL `drug_indication.indication_refs`, and source-native molecule/disease mappings.
3. Build full `clinical_trials_gov_trial_index` and `molecule_disease_trial_links` sidecars with mapping confidence and mismatch flags.
4. Parse structured results where available, but keep positive/negative endpoint interpretation conservative and auditable.
5. Produce leakage-aware feature aggregation proposal for PyG/HeteroData export.
6. Validate endpoint anti-joins against canonical molecule/disease nodes and evidence support against `molecule_treats_disease` edge keys.
7. Require review before any canonical evidence promotion.

## Validation run

Commands run:

```bash
uv run --group dev pytest tests/test_stage_clinicaltrials_gov_evidence_layer.py tests/test_stage_opentargets_clinical_drug_evidence.py -q
# 7 passed in 0.43s

uv run python -m manage_db.stage_clinicaltrials_gov_evidence_layer --max-edges 12 --max-ncts-per-edge 2 --max-studies 20 --out-root artifacts/staged/t_f65a077a_clinical_trials_evidence_layer
# fetched 20/20 ClinicalTrials.gov trials; wrote 20 evidence rows, 20 text feature rows, and 20 text embedding rows
```

Additional validation commands run after adding the text/embedding gate:

```bash
uv run python -m py_compile manage_db/stage_clinicaltrials_gov_evidence_layer.py
# pass

uv run --group dev pytest tests/test_stage_clinicaltrials_gov_evidence_layer.py tests/test_stage_opentargets_clinical_drug_evidence.py -q
# 10 passed in 1.48s
```

Validation checks written to `validation_checks.json`:

- `evidence_rows`: 20
- `trial_rows`: 20
- `link_rows`: 20
- `trial_text_feature_rows`: 20
- `trial_text_embedding_rows`: 20
- `trial_text_rows_match_fetched_trials`: true
- `trial_text_embedding_rows_match_features`: true
- `trial_text_nonempty_rows`: 20
- `trial_text_features_without_trial_index`: 0
- `trial_text_embeddings_without_features`: 0
- `trial_text_embedding_dim_values`: `[384]`
- `trial_text_embedding_vector_length_values`: `[384]`
- `evidence_without_edge`: 0
- `wrong_relation_rows`: 0
- `nct_id_nulls`: 0

## Residual risks

- The prototype uses live ClinicalTrials.gov API responses, not a frozen AACT snapshot; full build needs reproducibility controls.
- NCT IDs are seeded from staged OpenTargets positive indication evidence, so this prototype covers only 12 current `molecule_treats_disease` edge keys and does not audit all clinical trials for all drugs/diseases.
- CTGov intervention/condition text is not itself canonical molecule/disease mapping; full build needs explicit mapping confidence and mismatch flags.
- Endpoint outcome interpretation is conservative and incomplete; structured results and publications require separate parser/reviewer policy.
- The text embeddings are a deterministic local HashingVectorizer scaffold for bounded staging validation only; they are not a production clinical text model.
- API v2 result-summary fields are not guaranteed for every NCT row; this bounded run populated `result_summary_text` for 10/20 fetched rows and records absent fields in `source_field_inventory`.
- ClinicalTrials.gov/NLM/openFDA/EMA redistribution and attribution terms should be reviewed before canonical promotion.
