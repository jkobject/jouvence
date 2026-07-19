from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from manage_db.build_staged_prism_20q2 import PrismConfig, build_prism_20q2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True)
    paths = {
        "curve": root / "curve.csv", "treatment": root / "treatment.csv", "lfc": root / "lfc.csv",
        "cell_line": root / "cell_line.parquet", "molecule": root / "molecule.parquet",
    }
    pd.DataFrame([{"id": "ACH-1"}, {"id": "ACH-2"}]).to_parquet(paths["cell_line"], index=False)
    pd.DataFrame(
        [
            {"id": "CHEMBL1", "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "smiles": "CCO", "name": "ethanol"},
            {"id": "CHEMBL2", "inchikey": "WEVYAHXRMPXWCK-UHFFFAOYSA-N", "smiles": "CC#N", "name": "acetonitrile"},
            {"id": "CHEMBL3", "inchikey": "WEVYAHXRMPXWCK-UHFFFAOYSA-N", "smiles": "CC#N", "name": "duplicate structure"},
            {"id": "CHEMBL4", "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "name": "name-only must not map"},
        ]
    ).to_parquet(paths["molecule"], index=False)
    pd.DataFrame(
        [
            {"column_name": "redo-dose", "broad_id": "BRD-REDO", "dose": 1.0, "screen_id": "MTS010", "compound_plate": "P1", "name": "ethanol", "smiles": "CCO", "phase": "Launched"},
            {"column_name": "old-dose", "broad_id": "BRD-OLD", "dose": 1.0, "screen_id": "HTS002", "compound_plate": "P2", "name": "ethanol", "smiles": "CCO", "phase": "Launched"},
            {"column_name": "ambiguous-dose", "broad_id": "BRD-AMB", "dose": 1.0, "screen_id": "HTS002", "compound_plate": "P3", "name": "acetonitrile", "smiles": "CC#N", "phase": ""},
            {"column_name": "name-only-dose", "broad_id": "BRD-NAME", "dose": 1.0, "screen_id": "HTS002", "compound_plate": "P4", "name": "name-only must not map", "smiles": "", "phase": ""},
        ]
    ).to_csv(paths["treatment"], index=False)
    pd.DataFrame(
        [
            {"broad_id": "BRD-REDO", "depmap_id": "ACH-1", "ccle_name": "A", "screen_id": "MTS010", "upper_limit": 1.0, "lower_limit": 0.1, "slope": 1.2, "r2": 0.9, "auc": 0.4, "ec50": 0.5, "ic50": 0.6, "passed_str_profiling": True, "row_name": "row-a", "name": "ethanol", "smiles": "CCO"},
            {"broad_id": "BRD-OLD", "depmap_id": "ACH-1", "ccle_name": "A", "screen_id": "HTS002", "upper_limit": 1.0, "lower_limit": 0.2, "slope": 1.0, "r2": 0.95, "auc": 0.3, "ec50": 0.4, "ic50": 0.5, "passed_str_profiling": True, "row_name": "row-a", "name": "ethanol", "smiles": "CCO"},
            {"broad_id": "BRD-REDO", "depmap_id": "ACH-2", "ccle_name": "B", "screen_id": "MTS010", "upper_limit": 1.0, "lower_limit": 0.5, "slope": 1.0, "r2": 0.4, "auc": 0.2, "ec50": 0.4, "ic50": 0.5, "passed_str_profiling": True, "row_name": "row-b", "name": "ethanol", "smiles": "CCO"},
        ]
    ).to_csv(paths["curve"], index=False)
    pd.DataFrame([
        {"row-a": "PR500_ACH-1", "redo-dose": -2.0, "old-dose": -1.0, "ambiguous-dose": -3.0, "name-only-dose": -4.0},
        {"row-a": "ACH-1", "redo-dose": -1.5, "old-dose": -0.5, "ambiguous-dose": None, "name-only-dose": None},
    ]).rename(columns={"row-a": ""}).to_csv(paths["lfc"], index=False)
    return paths


def test_prism_build_maps_only_unique_structure_and_prefers_mts010(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path / "raw")
    out = tmp_path / "out"

    report = build_prism_20q2(
        curve_path=paths["curve"],
        treatment_path=paths["treatment"],
        lfc_path=paths["lfc"],
        cell_line_path=paths["cell_line"],
        molecule_path=paths["molecule"],
        output_dir=out,
        config=PrismConfig(auc_threshold=0.7, min_r2=0.8, dose_batch_size=1),
    )

    crosswalk = pd.read_parquet(out / "mapping" / "broad_id_to_molecule.parquet")
    assert crosswalk.set_index("broad_id").loc["BRD-REDO", "molecule_id"] == "CHEMBL1"
    assert crosswalk.set_index("broad_id").loc["BRD-AMB", "mapping_status"] == "ambiguous_inchikey"
    assert crosswalk.set_index("broad_id").loc["BRD-NAME", "mapping_status"] == "missing_structure"

    features = pd.read_parquet(out / "features" / "cell_line_molecule_viability_response.parquet")
    assert set(features["record_type"]) == {"curve_fit", "dose_observation"}
    assert "convergence" not in features.columns
    dose = features[(features["record_type"] == "dose_observation") & (features["broad_id"] == "BRD-REDO")].iloc[0]
    assert dose["logfold_change"] == -2.0
    assert dose["viability"] == 0.25
    assert pd.isna(dose["passed_str_profiling"])
    assert set(features["source_row_name"]) >= {"row-a", "PR500_ACH-1", "ACH-1"}
    assert features["record_id"].is_unique

    edges = pd.read_parquet(out / "edges" / "cell_line_responds_to_molecule.parquet")
    evidence = pd.read_parquet(out / "evidence" / "cell_line_responds_to_molecule.parquet")
    assert edges[["x_id", "y_id"]].to_dict("records") == [{"x_id": "ACH-1", "y_id": "CHEMBL1"}]
    assert evidence.iloc[0]["screen_id"] == "MTS010"
    assert report["quarantined_broad_ids"] == 2
    assert report["feature_rows"] == 7
    assert report["validation"]["all_passed"] is True
    assert report["validation"]["duplicate_edge_count"] == 0
    assert report["validation"]["duplicate_evidence_record_count"] == 0
    assert report["validation"]["evidence_without_edge_count"] == 0
    assert report["validation"]["feature_endpoint_antijoin_count"] == 0
    assert report["validation"]["duplicate_feature_record_count"] == 0
    assert report["validation"]["curve_feature_parity"] is True
    assert any("convergence field is documented but absent" in item for item in report["source_limitations"])


def test_prism_build_is_byte_deterministic(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path / "raw")
    outputs = []
    for name in ("first", "second"):
        out = tmp_path / name
        build_prism_20q2(
            curve_path=paths["curve"], treatment_path=paths["treatment"], lfc_path=paths["lfc"],
            cell_line_path=paths["cell_line"], molecule_path=paths["molecule"], output_dir=out,
        )
        outputs.append(out)
    for relative in (
        "features/cell_line_molecule_viability_response.parquet",
        "mapping/broad_id_to_molecule.parquet",
        "mapping/quarantine.parquet",
        "edges/cell_line_responds_to_molecule.parquet",
        "evidence/cell_line_responds_to_molecule.parquet",
    ):
        assert _sha256(outputs[0] / relative) == _sha256(outputs[1] / relative)