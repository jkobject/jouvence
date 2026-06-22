from __future__ import annotations

import pandas as pd

from manage_db.stage_opentargets_clinical_drug_evidence import _norm_disease, _to_evidence_frame


def test_norm_disease_opentargets_underscore_ids() -> None:
    assert _norm_disease("MONDO_0008903") == "MONDO:0008903"
    assert _norm_disease("EFO_0000544") == "EFO:0000544"
    assert _norm_disease("MONDO:0008903") == "MONDO:0008903"


def test_clinical_indication_evidence_frame_preserves_stage_and_ids() -> None:
    matches = pd.DataFrame(
        [
            {
                "x_id": "DB00001",
                "y_id": "MONDO:0000565",
                "clinical_indication_id": "abc123",
                "maxClinicalStage": "PHASE_3",
                "chembl_id": "CHEMBL1",
                "ot_disease_id": "MONDO_0000565",
                "nct_ids": "nct00000001",
                "clinical_report_ids": "nct00000001;report-1",
            }
        ]
    )

    evidence = _to_evidence_frame(matches)

    assert len(evidence) == 1
    row = evidence.iloc[0]
    assert row["edge_key"] == "molecule_treats_disease|DB00001|MONDO:0000565"
    assert row["relation"] == "molecule_treats_disease"
    assert row["source"] == "OpenTargets"
    assert row["source_dataset"] == "clinical_indication"
    assert row["source_record_id"] == "OpenTargets:clinical_indication:abc123"
    assert row["study_id"] == "nct00000001"
    assert row["direction"] == "positive_indication"
    assert row["predicate"] == "clinical indication; stage=PHASE_3"
    assert row["evidence_score"] == 0.85
    assert "clinical_stage=PHASE_3" in row["text_span"]
