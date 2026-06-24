from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from manage_db import kg_queries


def _write_fixture_kg(root: Path) -> None:
    (root / "nodes").mkdir(parents=True)
    (root / "edges").mkdir(parents=True)
    (root / "evidence").mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "id": "NCBI:672",
                "ncbi_gene_id": "672",
                "hgnc_id": None,
                "uniprot_id": None,
                "gene_name": "BRCA1",
                "name": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "source": "NCBI",
            },
            {
                "id": "ENSMUSG00000017146",
                "ncbi_gene_id": None,
                "hgnc_id": None,
                "uniprot_id": None,
                "gene_name": "Brca1",
                "name": "Brca1",
                "description": "Mouse ortholog of BRCA1",
                "source": "OpenTargets/target.homologues",
            },
        ]
    ).to_parquet(root / "nodes" / "gene.parquet", index=False)

    pd.DataFrame(
        [
            {
                "id": "MONDO:0019391",
                "name": "Fanconi anemia",
                "description": "Fanconi anemia disease node",
                "mondo_id": "MONDO:0019391",
                "efo_id": None,
                "mesh_id": None,
                "hp_id": None,
                "omim_id": None,
                "doid_id": None,
                "icd10_code": None,
                "source": "MONDO",
            },
            {
                "id": "EFO:0000305",
                "name": "breast carcinoma",
                "description": None,
                "mondo_id": None,
                "efo_id": "EFO:0000305",
                "mesh_id": None,
                "hp_id": None,
                "omim_id": None,
                "doid_id": None,
                "icd10_code": None,
                "source": "EFO",
            },
        ]
    ).to_parquet(root / "nodes" / "disease.parquet", index=False)

    pd.DataFrame(
        [
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "MONDO:0019391",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "TxGNN",
                "credibility": 1,
                "score": None,
            },
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "OpenTargets",
                "credibility": 3,
                "score": 0.88,
            },
        ]
    ).to_parquet(root / "edges" / "disease_associated_gene.parquet", index=False)

    pd.DataFrame(
        [
            {
                "edge_key": "disease_associated_gene|NCBI:672|EFO:0000305",
                "relation": "disease_associated_gene",
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "evidence_type": "database_record",
                "source": "OpenTargets",
                "source_dataset": "evidence",
                "source_record_id": "fixture",
                "paper_id": None,
                "dataset_id": None,
                "study_id": None,
                "evidence_score": 0.88,
                "effect_size": None,
                "p_value": None,
                "direction": None,
                "confidence_interval": None,
                "predicate": "genetic_association",
                "text_span": None,
                "section": None,
                "extraction_method": None,
                "license": None,
                "release": None,
                "created_at": "2026-06-23",
            }
        ]
    ).to_parquet(root / "evidence" / "disease_associated_gene.parquet", index=False)


def test_resolve_gene_by_name_prefers_human_fixture(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_fixture_kg(root)

    result = kg_queries.resolve_gene(gene_name="BRCA1", kg_root=root)

    assert list(result["id"]) == ["NCBI:672"]
    assert result.loc[0, "gene_name"] == "BRCA1"
    assert result.loc[0, "match_kind"] == "gene_name"


def test_resolve_gene_by_canonical_id_allows_exact_non_human(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_fixture_kg(root)

    result = kg_queries.resolve_gene(gene_id="ENSMUSG00000017146", kg_root=root)

    assert list(result["id"]) == ["ENSMUSG00000017146"]
    assert result.loc[0, "match_kind"] == "id"


def test_diseases_for_gene_returns_stable_shape_and_evidence_summary(tmp_path: Path) -> None:
    root = tmp_path / "kg"
    _write_fixture_kg(root)

    result = kg_queries.diseases_for_gene(gene_name="BRCA1", kg_root=root)

    assert list(result.columns) == kg_queries.DISEASE_RESULT_COLUMNS
    assert set(result["disease_id"]) == {"MONDO:0019391", "EFO:0000305"}
    breast = result[result["disease_id"] == "EFO:0000305"].iloc[0]
    assert breast["gene_id"] == "NCBI:672"
    assert breast["gene_name"] == "BRCA1"
    assert breast["disease_name"] == "breast carcinoma"
    assert breast["evidence_count"] == 1
    assert breast["evidence_sources"] == "OpenTargets"


def test_cli_diseases_for_gene_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "kg"
    _write_fixture_kg(root)

    code = kg_queries.main(
        [
            "--kg-root",
            str(root),
            "diseases-for-gene",
            "--gene-name",
            "BRCA1",
            "--format",
            "json",
            "--limit",
            "1",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    records = json.loads(out)
    assert records[0]["gene_id"] == "NCBI:672"
    assert "disease_id" in records[0]
    assert "NaN" not in out


def test_canonical_fuse_brca1_smoke_if_available() -> None:
    root = kg_queries.DEFAULT_KG_ROOT
    gene_path = root / "nodes" / "gene.parquet"
    try:
        if not gene_path.exists():
            pytest.skip(f"canonical KG root not mounted: {root}")
    except OSError as exc:
        pytest.skip(f"canonical KG root unavailable: {root} ({exc})")

    try:
        result = kg_queries.diseases_for_gene(gene_name="BRCA1", kg_root=root, limit=5)
    except OSError as exc:
        pytest.skip(f"canonical KG root unavailable during query: {root} ({exc})")

    assert list(result.columns) == kg_queries.DISEASE_RESULT_COLUMNS
    assert not result.empty
    assert {"gene_id", "disease_id", "disease_name"} <= set(result.columns)
