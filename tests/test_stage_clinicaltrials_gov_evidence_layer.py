from __future__ import annotations

import json

import pandas as pd

import manage_db.stage_clinicaltrials_gov_evidence_layer as ctgov
from manage_db.stage_clinicaltrials_gov_evidence_layer import (
    TEXT_EMBEDDING_DIM,
    build_trial_text_embeddings,
    build_trial_text_features,
    classify_trial_outcome,
    extract_nct_ids,
    flatten_study,
    run,
)


def test_extract_nct_ids_preserves_order_and_deduplicates() -> None:
    assert extract_nct_ids("nct00000001; NCT00000002; nct00000001; other") == [
        "NCT00000001",
        "NCT00000002",
    ]


def test_classify_trial_outcome_safety_before_business() -> None:
    assert (
        classify_trial_outcome("TERMINATED", "Terminated for safety after slow enrollment")
        == "safety_failure_or_harm"
    )


def test_classify_trial_outcome_business_funding() -> None:
    assert (
        classify_trial_outcome("TERMINATED", "Sponsor decision due to funding and recruitment feasibility")
        == "terminated_business_funding_or_feasibility"
    )


def test_classify_trial_outcome_failed_efficacy() -> None:
    assert (
        classify_trial_outcome("TERMINATED", "Stopped for futility after failing primary endpoint")
        == "failed_efficacy_or_endpoint"
    )


def test_classify_trial_outcome_completed_is_unknown_not_positive() -> None:
    assert classify_trial_outcome("COMPLETED", "") == "completed_outcome_unknown"


def _sample_study() -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "briefTitle": "Pilot Treatment Study",
                "officialTitle": "Official Pilot Treatment Study for Example Disease",
            },
            "statusModule": {"overallStatus": "TERMINATED", "whyStopped": "Stopped for futility"},
            "descriptionModule": {
                "briefSummary": "This study evaluates whether the treatment improves symptoms.",
                "detailedDescription": "Detailed rationale, visit schedule, and endpoint context.",
            },
            "conditionsModule": {"conditions": ["Example Disease"]},
            "armsInterventionsModule": {
                "interventions": [
                    {"type": "DRUG", "name": "Example Drug", "description": "Oral active treatment"}
                ]
            },
            "outcomesModule": {
                "primaryOutcomes": [
                    {
                        "measure": "Change in symptom score",
                        "description": "Mean change from baseline",
                        "timeFrame": "12 weeks",
                    }
                ],
                "secondaryOutcomes": [
                    {"measure": "Responder fraction", "description": "At least 50 percent improvement"}
                ],
            },
            "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria: adults with example disease."},
            "designModule": {"phases": ["PHASE2"], "studyType": "INTERVENTIONAL"},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Example Sponsor", "class": "OTHER"}},
            "referencesModule": {"references": [{"pmid": "12345"}]},
        },
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "title": "Result symptom score",
                        "description": "Observed endpoint result summary text",
                        "timeFrame": "12 weeks",
                        "type": "PRIMARY",
                    }
                ]
            },
            "moreInfoModule": {"limitationsAndCaveats": "Small bounded sample."},
        },
    }


def test_flatten_study_includes_trial_free_text_fields() -> None:
    row = flatten_study(_sample_study(), "NCT12345678")
    assert row["brief_summary"] == "This study evaluates whether the treatment improves symptoms."
    assert row["detailed_description"] == "Detailed rationale, visit schedule, and endpoint context."
    assert "description=Oral active treatment" in row["intervention_details"]
    assert "time_frame=12 weeks" in row["primary_outcome_text"]
    assert "Inclusion Criteria" in row["eligibility_criteria"]
    assert "Observed endpoint result summary text" in row["result_summary_text"]


def test_text_feature_and_embedding_rows_keyed_by_nct() -> None:
    trial_index = pd.DataFrame([flatten_study(_sample_study(), "NCT12345678")])
    features = build_trial_text_features(trial_index)
    embeddings = build_trial_text_embeddings(features)

    assert len(features) == 1
    assert features.loc[0, "nct_id"] == "NCT12345678"
    assert features.loc[0, "source_feature_key"] == "NCT12345678"
    assert "brief_summary" in json.loads(features.loc[0, "source_field_inventory"])
    assert "overall_status" not in json.loads(features.loc[0, "source_field_inventory"])
    assert features.loc[0, "source_text_length"] > 100

    assert len(embeddings) == 1
    assert embeddings.loc[0, "nct_id"] == "NCT12345678"
    assert embeddings.loc[0, "source_feature_key"] == "NCT12345678"
    assert embeddings.loc[0, "source_feature_hash"] == features.loc[0, "source_text_hash"]
    assert embeddings.loc[0, "embedding_model"] == "sklearn.feature_extraction.text.HashingVectorizer"
    assert embeddings.loc[0, "embedding_dim"] == TEXT_EMBEDDING_DIM
    assert len(embeddings.loc[0, "embedding"]) == TEXT_EMBEDDING_DIM


def test_run_writes_text_feature_and_embedding_artifacts(tmp_path, monkeypatch) -> None:
    edge_trials = pd.DataFrame(
        [
            {
                "edge_key": "molecule_treats_disease|DB00001|MONDO:0000001",
                "relation": "molecule_treats_disease",
                "x_id": "DB00001",
                "x_type": "molecule",
                "y_id": "MONDO:0000001",
                "y_type": "disease",
                "predicate": "known treatment",
                "study_id": "NCT12345678",
                "text_span": "seed text",
                "nct_id": "NCT12345678",
            }
        ]
    )
    monkeypatch.setattr(ctgov, "_load_source_edges", lambda *_args, **_kwargs: edge_trials)
    monkeypatch.setattr(ctgov, "fetch_study", lambda _nct_id: _sample_study())

    report = run(tmp_path / "unused.parquet", tmp_path, max_edges=1, max_ncts_per_edge=1, max_studies=1)
    feature_path = tmp_path / "features" / "clinical_trials_gov_trial_text_features.parquet"
    embedding_path = tmp_path / "features" / "embeddings" / "clinical_trials_gov_trial_text" / "hashing_vectorizer" / "prototype_v1" / "part-000.parquet"

    assert report["counts"]["trial_text_feature_rows"] == 1
    assert report["counts"]["trial_text_embedding_rows"] == 1
    assert report["artifacts"]["trial_text_features"] == str(feature_path)
    assert report["artifacts"]["trial_text_embeddings"] == str(embedding_path)
    assert feature_path.exists()
    assert embedding_path.exists()

    features = pd.read_parquet(feature_path)
    embeddings = pd.read_parquet(embedding_path)
    assert set(features["nct_id"]) == {"NCT12345678"}
    assert set(embeddings["nct_id"]) == {"NCT12345678"}
    assert embeddings.loc[0, "source_feature_hash"] == features.loc[0, "source_text_hash"]
    assert embeddings.loc[0, "embedding_dim"] == TEXT_EMBEDDING_DIM
