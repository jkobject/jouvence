from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from manage_db.viewer.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_session_and_search_are_fixture_bounded() -> None:
    c = client()
    session = c.get("/api/session").json()
    assert session["source"]["mode"] == "fixture"
    assert session["source"]["localhost_only"] is True

    found = c.get("/api/search", params={"q": "BRCA1", "limit": 5}).json()
    assert found["meta"]["snapshot_id"] == "fixture-v1"
    assert found["meta"]["data_mode"] == "fixture"
    assert found["results"][0]["node_id"] == "ENSG00000012048"
    assert found["results"][0]["alias_kind"] in {"display_name", "symbol"}

    malformed = c.get("/api/search", params={"q": "BRCA", "limit": 26})
    assert malformed.status_code == 422


def test_node_dossier_sections_and_empty_unknown_states() -> None:
    c = client()
    node = c.get("/api/nodes/gene/ENSG00000012048").json()
    assert node["node"]["display_name"] == "BRCA1"
    assert node["meta"]["data_mode"] == "fixture"

    features = c.get("/api/nodes/gene/ENSG00000012048/features").json()
    assert {row["epistemic_kind"] for row in features["rows"]} >= {"source-backed", "model/fallback"}

    edges = c.get("/api/nodes/gene/ENSG00000012048/edges", params={"limit": 1}).json()
    assert edges["meta"]["truncated"] is True
    assert edges["meta"]["next_cursor"] == "1"
    assert {row["row_kind"] for row in edges["rows"]} == {"observed"}

    evidence = c.get("/api/edges/fixture:edge:nope/evidence").json()
    assert evidence["rows"] == []
    assert evidence["meta"]["truncated"] is False

    assert c.get("/api/nodes/gene/NOPE").status_code == 404
    assert c.get("/api/nodes/unknown/NOPE").status_code == 404
    assert c.get("/api/nodes/gene/ENSG00000012048/edges", params={"cursor": "bad"}).status_code == 422


def test_long_range_putative_and_exports_label_row_kinds() -> None:
    c = client()
    long_range = c.get("/api/nodes/gene/ENSG00000012048/long-range").json()
    assert long_range["rows"]
    assert {row["row_kind"] for row in long_range["rows"]} == {"ranked"}

    putative = c.get("/api/nodes/gene/ENSG00000012048/putative").json()
    assert putative["rows"][0]["row_kind"] == "inferred"
    assert putative["rows"][0]["policy_class"] == "inferred_weak"

    payload = {
        "node_type": "gene",
        "node_id": "ENSG00000012048",
        "trail": [
            {"node_type": "gene", "node_id": "ENSG00000012048", "via": "Search start"},
            {"node_type": "disease", "node_id": "EFO:0000305", "via": "disease_associated_gene"},
        ],
        "format": "markdown",
    }
    md = c.post("/api/export", json=payload)
    assert md.status_code == 200
    text = md.text
    assert "observed `disease_associated_gene`" in text
    assert "ranked disease:EFO:0000305" in text
    assert "inferred disease:EFO:0000616" in text
    assert "Navigation trail" in text

    payload["format"] = "csv"
    csv_bundle = c.post("/api/export", json=payload)
    assert csv_bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(csv_bundle.content)) as zf:
        assert {"node.csv", "features.csv", "edges.csv", "evidence.csv", "long_range.csv", "putative_links.csv", "history.csv", "manifest.json"}.issubset(set(zf.namelist()))
        manifest = zf.read("manifest.json").decode()
        assert "observed" in manifest and "ranked" in manifest and "inferred" in manifest


def test_no_arbitrary_file_or_sql_surface() -> None:
    c = client()
    assert c.get("/api/sql").status_code == 404
    assert c.post("/api/sql", json={"sql": "select 1"}).status_code == 404
    assert c.get("/api/files", params={"path": "/etc/passwd"}).status_code == 404
