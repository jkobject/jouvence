from __future__ import annotations

import json

import pandas as pd

import manage_db.stage_clinicaltrials_gov_production_candidate as prod
from manage_db.stage_clinicaltrials_gov_production_candidate import (
    TEXT_EMBEDDING_DIM,
    build_evidence_rows,
    build_trial_index,
    build_trial_text_embeddings,
    build_trial_text_features,
    load_source_edge_trials,
)


def _sample_study() -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345678",
                "briefTitle": "Production Candidate Study",
                "officialTitle": "Official Production Candidate Study for Example Disease",
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
                ]
            },
            "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria: adults."},
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
            }
        },
    }


def test_load_source_edge_trials_expands_all_nct_ids(tmp_path) -> None:
    evidence = pd.DataFrame(
        [
            {
                "edge_key": "molecule_treats_disease|DB00001|MONDO:0000001",
                "relation": "molecule_treats_disease",
                "x_id": "DB00001",
                "x_type": "molecule",
                "y_id": "MONDO:0000001",
                "y_type": "disease",
                "predicate": "known treatment",
                "study_id": "NCT12345678; NCT87654321; NCT12345678",
                "text_span": "seed text",
                "source": "OpenTargets",
                "source_dataset": "known_drug",
                "source_record_id": "row1",
                "evidence_score": 0.7,
                "release": "test",
            }
        ]
    )
    path = tmp_path / "evidence.parquet"
    evidence.to_parquet(path, index=False)

    links = load_source_edge_trials(path)

    assert links["nct_id"].tolist() == ["NCT12345678", "NCT87654321"]
    assert set(links["mapping_confidence"]) == {"source_asserted_edge_nct_reference"}


def test_build_trial_index_features_embeddings_and_evidence_keyed_to_snapshot() -> None:
    source_release = "ClinicalTrials.gov API v2 raw query.id snapshot; test"
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
                "mapping_confidence": "source_asserted_edge_nct_reference",
            }
        ]
    )
    trial_index = build_trial_index({"NCT12345678": _sample_study()}, ["NCT12345678"], source_release)
    features = build_trial_text_features(trial_index, source_release)
    embeddings = build_trial_text_embeddings(features, source_release)
    evidence = build_evidence_rows(edge_trials, trial_index, source_release)

    assert trial_index.loc[0, "nct_id"] == "NCT12345678"
    assert trial_index.loc[0, "source_release"] == source_release
    assert trial_index.loc[0, "trajectory_class"] == "failed_efficacy_or_endpoint"
    assert len(trial_index.loc[0, "raw_response_sha256"]) == 64

    assert features.loc[0, "source_feature_key"] == "NCT12345678"
    assert "result_summary_text" in json.loads(features.loc[0, "source_field_inventory"])
    assert features.loc[0, "source_release"] == source_release

    assert embeddings.loc[0, "nct_id"] == "NCT12345678"
    assert embeddings.loc[0, "embedding_dim"] == TEXT_EMBEDDING_DIM
    assert len(embeddings.loc[0, "embedding"]) == TEXT_EMBEDDING_DIM
    assert embeddings.loc[0, "source_feature_hash"] == features.loc[0, "source_text_hash"]

    assert evidence.loc[0, "source_record_id"] == "ClinicalTrials.gov:NCT12345678"
    assert evidence.loc[0, "study_id"] == "NCT12345678"
    assert evidence.loc[0, "direction"] == "failed_efficacy_or_endpoint"
    assert evidence.loc[0, "release"] == source_release


def test_fetch_or_load_raw_snapshot_uses_cached_chunk(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    chunk_root = raw_root / "ctgov_api_v2_query_id_chunks"
    chunk_root.mkdir(parents=True)
    (chunk_root / "chunk_00000.json").write_text(
        json.dumps(
            {
                "studies": [_sample_study()],
                "_txgnn_request": {"nct_ids": ["NCT12345678"]},
            }
        )
    )

    studies, errors, manifest = prod.fetch_or_load_raw_snapshot(
        ["NCT12345678"], raw_root, batch_size=1, refresh=False
    )

    assert set(studies) == {"NCT12345678"}
    assert errors == {}
    assert manifest["requested_nct_count"] == 1
    assert manifest["fetched_nct_count"] == 1
    assert manifest["manifest_sha256"]
    assert (raw_root / "ctgov_api_v2_raw_manifest.json").exists()
