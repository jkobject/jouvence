from __future__ import annotations

import io
import zipfile
from copy import copy
from dataclasses import replace

from fastapi.testclient import TestClient

from manage_db.viewer.app import create_app
from manage_db.viewer.bundle import FIXTURE_DATA

TEST_TOKEN = "test-session-token"
LOCAL_HEADERS = {
    "host": "127.0.0.1:8765",
    "x-jouvence-session": TEST_TOKEN,
}


def client() -> TestClient:
    return TestClient(
        create_app(session_token=TEST_TOKEN),
        base_url="http://127.0.0.1:8765",
        headers={"x-jouvence-session": TEST_TOKEN},
    )


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


def test_localhost_viewer_links_resolve_through_static_mount() -> None:
    c = client()
    homepage = c.get("/")
    assert homepage.status_code == 200
    for href in (
        "/static/index.html",
        "/static/viewer-install.html",
        "/static/viewer-proposal.md",
    ):
        assert f'href="{href}"' in homepage.text
        assert c.get(href).status_code == 200


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


def test_export_is_bounded_even_for_high_degree_bundle_nodes() -> None:
    source = copy(FIXTURE_DATA)
    source.EDGE_ROWS = FIXTURE_DATA.EDGE_ROWS * 100
    source.EVIDENCE_ROWS = FIXTURE_DATA.EVIDENCE_ROWS * 100
    source.FEATURE_ROWS = FIXTURE_DATA.FEATURE_ROWS * 100
    source.LONG_RANGE_ROWS = FIXTURE_DATA.LONG_RANGE_ROWS * 100
    source.PUTATIVE_ROWS = FIXTURE_DATA.PUTATIVE_ROWS * 100
    c = TestClient(
        create_app(data_source=source, session_token=TEST_TOKEN),
        base_url="http://127.0.0.1:8765",
        headers={"x-jouvence-session": TEST_TOKEN},
    )
    response = c.post(
        "/api/export",
        json={
            "node_type": "gene",
            "node_id": "ENSG00000012048",
            "format": "csv",
        },
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(archive.read("features.csv").decode().splitlines()) <= 101
        assert len(archive.read("edges.csv").decode().splitlines()) <= 51
        assert len(archive.read("evidence.csv").decode().splitlines()) <= 101
        assert len(archive.read("putative_links.csv").decode().splitlines()) <= 26
        assert len(archive.read("long_range.csv").decode().splitlines()) <= 21


def test_every_api_response_has_a_global_byte_ceiling() -> None:
    source = copy(FIXTURE_DATA)
    source.NODES = dict(FIXTURE_DATA.NODES)
    key = ("gene", "ENSG00000012048")
    source.NODES[key] = replace(
        source.NODES[key],
        aliases=tuple(
            {"kind": "external_id", "value": "x" * (64 * 1024), "source": "test"}
            for _ in range(100)
        ),
    )
    c = TestClient(
        create_app(data_source=source, session_token=TEST_TOKEN),
        base_url="http://127.0.0.1:8765",
        headers={"x-jouvence-session": TEST_TOKEN},
    )

    response = c.get("/api/nodes/gene/ENSG00000012048")

    assert response.status_code == 413
    assert response.json() == {"detail": "API response too large"}


def test_long_range_has_a_global_cap_across_distinct_target_types() -> None:
    source = copy(FIXTURE_DATA)
    template = FIXTURE_DATA.LONG_RANGE_ROWS[0]
    source.LONG_RANGE_ROWS = [
        {
            **template,
            "target_type": f"type-{index}",
            "target_id": f"target-{index}",
            "rank": 1,
        }
        for index in range(100)
    ]
    c = TestClient(
        create_app(data_source=source, session_token=TEST_TOKEN),
        base_url="http://127.0.0.1:8765",
        headers={"x-jouvence-session": TEST_TOKEN},
    )

    response = c.get("/api/nodes/gene/ENSG00000012048/long-range")

    assert response.status_code == 200
    assert len(response.json()["rows"]) <= 20
    assert response.json()["meta"]["truncated"] is True

    export = c.post(
        "/api/export",
        json={
            "node_type": "gene",
            "node_id": "ENSG00000012048",
            "format": "csv",
        },
    )
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert len(archive.read("long_range.csv").decode().splitlines()) <= 21


def test_export_rejects_oversized_and_unknown_trail_nodes() -> None:
    oversized_body = client().post(
        "/api/export",
        content=b"{" + b" " * (64 * 1024),
        headers={"content-type": "application/json"},
    )
    assert oversized_body.status_code == 413

    unexpected_field = client().post(
        "/api/export",
        json={
            "node_type": "gene",
            "node_id": "ENSG00000012048",
            "format": "markdown",
            "credential": "must-not-be-accepted",
        },
    )
    assert unexpected_field.status_code == 422

    oversized = client().post(
        "/api/export",
        json={
            "node_type": "gene",
            "node_id": "ENSG00000012048",
            "trail": [{"node_type": "gene", "node_id": "x" * 257, "via": "Direct"}],
            "format": "markdown",
        },
    )
    assert oversized.status_code == 422

    unknown = client().post(
        "/api/export",
        json={
            "node_type": "gene",
            "node_id": "ENSG00000012048",
            "trail": [{"node_type": "gene", "node_id": "NOPE", "via": "Direct"}],
            "format": "markdown",
        },
    )
    assert unknown.status_code == 422
