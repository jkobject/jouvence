from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_storage
from manage_db.credibility import Credibility


def _sample_node_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "id": ["ENSG000001"],
            "ncbi_gene_id": ["1234"],
            "hgnc_id": ["HGNC:5"],
            "uniprot_id": ["P12345"],
            "gene_name": ["TP53"],
        }
    )
    return df.convert_dtypes(dtype_backend="pyarrow")


def _sample_edge_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "x_id": ["ENSG000001"],
            "x_type": ["gene"],
            "y_id": ["EFO:0000305"],
            "y_type": ["disease"],
            "relation": ["disease_associated_gene"],
            "display_relation": ["associated"],
            "source": ["test"],
            "credibility": [1],
        }
    )
    return df.convert_dtypes(dtype_backend="pyarrow")


def test_open_local_root_creates_layout(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))

    kg_storage.write_nodes(root, "gene", _sample_node_df())
    kg_storage.write_edges(root, "disease_associated_gene", _sample_edge_df())

    node_file = tmp_path / "kg" / "nodes" / "gene.parquet"
    edge_file = tmp_path / "kg" / "edges" / "disease_associated_gene.parquet"

    assert node_file.exists()
    assert edge_file.exists()


def test_round_trip_nodes(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    df = _sample_node_df()
    kg_storage.write_nodes(root, "gene", df)

    result = kg_storage.read_nodes(root, "gene").convert_dtypes(dtype_backend="pyarrow")
    pd.testing.assert_frame_equal(result[df.columns], df)


def test_round_trip_edges(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    df = _sample_edge_df()
    kg_storage.write_edges(root, "disease_associated_gene", df)

    result = kg_storage.read_edges(root, "disease_associated_gene").convert_dtypes(
        dtype_backend="pyarrow"
    )
    pd.testing.assert_frame_equal(result[df.columns], df)


def test_atomic_write_no_tmp_left_on_success(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    kg_storage.write_nodes(root, "gene", _sample_node_df())

    tmp_files = list((tmp_path / "kg" / "nodes").glob("*.tmp.*"))
    assert not tmp_files


def test_atomic_write_cleans_tmp_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))

    original_write = kg_storage.pq.write_table

    def _boom(*args, **kwargs):  # pragma: no cover - intentional failure
        raise RuntimeError("boom")

    monkeypatch.setattr(kg_storage.pq, "write_table", _boom)

    with pytest.raises(RuntimeError):
        kg_storage.write_nodes(root, "gene", _sample_node_df())

    monkeypatch.setattr(kg_storage.pq, "write_table", original_write)

    tmp_dir = tmp_path / "kg" / "nodes"
    assert not list(tmp_dir.glob("*.tmp.*"))


def test_append_dedups_edges(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    base = _sample_edge_df()
    dup = base.copy()
    dup["credibility"] = [3]

    kg_storage.write_edges(root, "disease_associated_gene", base)
    kg_storage.write_edges(root, "disease_associated_gene", dup, mode="append")

    result = kg_storage.read_edges(root, "disease_associated_gene")
    assert len(result) == 1
    assert {"x_id", "y_id", "relation"} <= set(result.columns)


def test_append_preserves_existing_rows(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))

    batch_one = pd.DataFrame(
        {
            "x_id": ["ENSG000001", "ENSG000002", "ENSG000003"],
            "x_type": ["gene", "gene", "gene"],
            "y_id": ["EFO:0000305", "EFO:0000306", "EFO:0000307"],
            "y_type": ["disease", "disease", "disease"],
            "relation": ["disease_associated_gene"] * 3,
            "display_relation": ["associated"] * 3,
            "source": ["test"] * 3,
            "credibility": [1, 1, 1],
        }
    ).convert_dtypes(dtype_backend="pyarrow")

    batch_two = pd.DataFrame(
        {
            "x_id": ["ENSG000001"],
            "x_type": ["gene"],
            "y_id": ["EFO:0000305"],
            "y_type": ["disease"],
            "relation": ["disease_associated_gene"],
            "display_relation": ["associated"],
            "source": ["test"],
            "credibility": [1],
        }
    ).convert_dtypes(dtype_backend="pyarrow")

    kg_storage.write_edges(root, "disease_associated_gene", batch_one)
    kg_storage.write_edges(root, "disease_associated_gene", batch_two, mode="append")

    result = kg_storage.read_edges(root, "disease_associated_gene")
    assert len(result) == 3
    pairs = set(zip(result["x_id"], result["y_id"]))
    expected_pairs = {
        ("ENSG000001", "EFO:0000305"),
        ("ENSG000002", "EFO:0000306"),
        ("ENSG000003", "EFO:0000307"),
    }
    assert pairs == expected_pairs


def test_append_recomputes_credibility_across_batches(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))

    base = _sample_edge_df()
    curated = base.copy()
    curated["source"] = ["drugbank"]
    curated["credibility"] = [Credibility.ESTABLISHED_FACT]

    kg_storage.write_edges(root, "disease_associated_gene", base)
    kg_storage.write_edges(root, "disease_associated_gene", curated, mode="append")

    result = kg_storage.read_edges(root, "disease_associated_gene").convert_dtypes(
        dtype_backend="pyarrow"
    )
    assert len(result) == 1
    assert result.loc[0, "credibility"] == Credibility.ESTABLISHED_FACT
    assert "drugbank" in result.loc[0, "source"]


def test_provenance_json_roundtrip(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    sources = {"test": {"version": "v1", "uri": "local", "sha256": "abc", "row_counts": {}}}
    path = kg_storage.write_provenance(
        root,
        sources=sources,
        code_sha="deadbeef",
        code_version="0.1.0",
    )
    assert Path(path).name == "provenance.json"
    loaded = kg_storage.read_provenance(root)
    assert loaded["sources"] == sources


def test_schema_mismatch_raises_clear_error(tmp_path: Path) -> None:
    root = kg_storage.open_kg_root(str(tmp_path / "kg"))
    bad_nodes = pd.DataFrame({"ncbi_gene_id": ["123"]})
    with pytest.raises(ValueError, match="missing required columns"):
        kg_storage.write_nodes(root, "gene", bad_nodes)


ADC_ENV = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
ADC_DEFAULT = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
GCS_AVAILABLE = bool(ADC_ENV and Path(ADC_ENV).exists()) or ADC_DEFAULT.exists()


@pytest.mark.skipif(not GCS_AVAILABLE, reason="no ADC")
def test_gcs_round_trip_smoke() -> None:
    unique = f"kg/_clawd_w3_probe/{int(time.time())}_{os.getpid()}"
    dst_uri = f"gs://jouvencekb/{unique}"
    root = kg_storage.open_kg_root(dst_uri)

    df = _sample_node_df()
    kg_storage.write_nodes(root, "gene", df)

    result = kg_storage.read_nodes(root, "gene").convert_dtypes(dtype_backend="pyarrow")
    pd.testing.assert_frame_equal(result[df.columns], df)

    # Cleanup
    if root.fs.exists(root._node_internal("gene")):
        root.fs.rm(root._node_internal("gene"))
    for sub in ("nodes", "edges", "metadata"):
        rel = root._join(sub)
        if rel and root.fs.exists(rel):
            root.fs.rm(rel, recursive=True)
    if root._path and root.fs.exists(root._path):
        root.fs.rm(root._path, recursive=True)
