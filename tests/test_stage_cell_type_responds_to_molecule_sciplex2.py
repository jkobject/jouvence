import json

import pandas as pd

from artifacts.scripts.stage_cell_type_responds_to_molecule_sciplex2 import build


def test_sciplex2_stage_filters_and_validates(tmp_path):
    obs = pd.DataFrame(
        [
            {
                "pert_type": "compound",
                "pert_name": "nutlin-3a",
                "pert_compound": "Nutlin-3",
                "pert_target": "unknown",
                "pert_dose": "1μM",
                "dose_value": "1",
                "pert_time": "24h",
                "cell_type": "pneumocyte",
                "cell_line": "A549",
                "tissue": "lung",
                "assay": "sci-Plex",
                "suspension_type": "nucleus",
                "chembl-ID": "CHEMBL407632;CHEMBL191334",
            },
            {
                "pert_type": "compound",
                "pert_name": "nutlin-3a",
                "pert_compound": "Nutlin-3",
                "pert_target": "unknown",
                "pert_dose": "0μM",
                "dose_value": "0",
                "pert_time": "24h",
                "cell_type": "pneumocyte",
                "cell_line": "A549",
                "tissue": "lung",
                "assay": "sci-Plex",
                "suspension_type": "nucleus",
                "chembl-ID": "CHEMBL407632",
            },
            {
                "pert_type": "compound",
                "pert_name": "BMS-345541",
                "pert_compound": "BMS-345541",
                "pert_target": "unknown",
                "pert_dose": "1μM",
                "dose_value": "1",
                "pert_time": "24h",
                "cell_type": "pneumocyte",
                "cell_line": "A549",
                "tissue": "lung",
                "assay": "sci-Plex",
                "suspension_type": "nucleus",
                "chembl-ID": "",
            },
            {
                "pert_type": "compound",
                "pert_name": "unknown compound",
                "pert_compound": "unknown compound",
                "pert_target": "unknown",
                "pert_dose": "1μM",
                "dose_value": "1",
                "pert_time": "24h",
                "cell_type": "unmapped source cell",
                "cell_line": "X",
                "tissue": "",
                "assay": "sci-Plex",
                "suspension_type": "nucleus",
                "chembl-ID": "CHEMBL1",
            },
        ]
    )
    obs_path = tmp_path / "obs.parquet"
    obs.to_parquet(obs_path)

    summary = build(obs_path, tmp_path / "out", min_cells=1)
    validation = summary["validation"]

    assert validation["candidate_context_rows"] == 2
    assert validation["edge_rows"] == 0
    assert validation["evidence_rows"] == 0
    assert validation["edge_without_evidence"] == 0
    assert validation["evidence_without_edge"] == 0
    assert validation["edge_x_cell_type_antijoin"] == 0
    assert validation["edge_y_molecule_antijoin"] == 0

    candidates = pd.read_parquet(summary["paths"]["candidates"])
    assert set(candidates["molecule_id"]) == {"CHEMBL191334", "CHEMBL407632"}
    assert set(candidates["cell_type_id"]) == {"CL:0000322"}
    assert set(candidates["response_metric_name"]) == {"not_available_in_obs_metadata"}
    assert candidates["response_metric_value"].isna().all()
    assert not candidates["source_record_id"].str.contains(":0μM:").any()

    edges = pd.read_parquet(summary["paths"]["edges"])
    evidence = pd.read_parquet(summary["paths"]["evidence"])
    assert edges.empty
    assert evidence.empty

    rejected = pd.read_parquet(summary["paths"]["rejected"])
    reasons = set(";".join(rejected["reject_reason"]).split(";"))
    assert "zero_or_missing_dose_value" in reasons
    assert "missing_source_chembl_id" in reasons
    assert "cell_type_label_not_mapped_to_CL_by_exact_label_or_synonym" in reasons

    report = json.loads((tmp_path / "out" / "reports" / "cell_type_responds_to_molecule_sciplex2_pilot_report.json").read_text())
    assert report["validation"] == validation
    assert report["artifact_status"] == "candidate_context_only_no_edges_emitted"
    assert report["response_metric"]["available"] is False
    assert report["promotion_recommendation"].startswith("do_not_promote")
    assert "missing_source_chembl_id" in report["rejection_reason_counts"]
