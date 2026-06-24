from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from manage_db.build_embedding_pilot import run


def _write_fixture(root: Path) -> None:
    (root / "nodes").mkdir(parents=True)
    (root / "edges").mkdir(parents=True)
    (root / "evidence").mkdir(parents=True)
    pd.DataFrame([{"id": "CL:000001", "name": "T cell"}]).to_parquet(root / "nodes" / "cell_type.parquet", index=False)
    pd.DataFrame([{"id": "CHEMBL1", "name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"}]).to_parquet(
        root / "nodes" / "molecule.parquet", index=False
    )
    pd.DataFrame(
        [
            {
                "x_id": "CL:000001",
                "x_type": "cell_type",
                "y_id": "CHEMBL1",
                "y_type": "molecule",
                "relation": "cell_type_responds_to_molecule",
                "display_relation": "responds to",
                "source": "fixture",
                "credibility": 2,
            }
        ]
    ).to_parquet(root / "edges" / "cell_type_responds_to_molecule.parquet", index=False)
    pd.DataFrame(
        [
            {
                "edge_key": "cell_type_responds_to_molecule|CL:000001|CHEMBL1",
                "relation": "cell_type_responds_to_molecule",
                "x_id": "CL:000001",
                "x_type": "cell_type",
                "y_id": "CHEMBL1",
                "y_type": "molecule",
                "evidence_type": "fixture_response",
                "source": "fixture",
                "source_dataset": "unit_test",
                "source_record_id": "r1",
                "paper_id": "PMID:1",
                "dataset_id": "DS1",
                "study_id": "S1",
                "evidence_score": 0.75,
                "effect_size": None,
                "p_value": None,
                "direction": "up",
                "confidence_interval": None,
                "predicate": "response observed",
                "text_span": "T cell response to aspirin",
                "section": "fixture",
                "extraction_method": "unit_test",
                "license": "fixture",
                "release": "test",
                "created_at": "2026-06-23T00:00:00Z",
            }
        ]
    ).to_parquet(root / "evidence" / "cell_type_responds_to_molecule.parquet", index=False)


def test_embedding_pilot_outputs_manifest_and_one_edge_vector(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    _write_fixture(input_dir)

    manifest = run(input_dir, output_dir, clean=True)

    assert manifest["staged_only"] is True
    assert manifest["canonical_promotion"] is False
    assert "recompute_command" in manifest
    assert manifest["models"]["text_surrogate"]["embedding_dim"] == 384

    manifest_path = output_dir / "manifest.json"
    summary_path = output_dir / "embedding_pilot_summary.md"
    assert manifest_path.exists()
    assert summary_path.exists()
    assert "staged-only pilot" in summary_path.read_text()

    node_path = Path(manifest["outputs"]["node_text_embeddings"]["path"])
    edge_path = Path(manifest["outputs"]["edge_evidence_embeddings"]["path"])
    fp_path = Path(manifest["outputs"]["molecule_fingerprint_pilot"]["path"])
    assert pq.ParquetFile(node_path).metadata.num_rows == 2
    assert pq.ParquetFile(edge_path).metadata.num_rows == 1
    assert pq.ParquetFile(fp_path).metadata.num_rows == 1

    edge_df = pd.read_parquet(edge_path)
    assert edge_df.loc[0, "edge_key"] == "cell_type_responds_to_molecule|CL:000001|CHEMBL1"
    assert edge_df.loc[0, "n_evidence_rows_total"] == 1
    assert len(edge_df.loc[0, "embedding"]) == 384
    assert edge_df.loc[0, "source_feature_hash"]

    loaded_manifest = json.loads(manifest_path.read_text())
    assert loaded_manifest["source_table_hashes"]
    assert loaded_manifest["outputs"]["edge_evidence_embeddings"]["rows"] == 1
