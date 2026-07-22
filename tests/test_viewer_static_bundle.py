from __future__ import annotations

import json
import re
from pathlib import Path

from manage_db.viewer import fixture
from manage_db.viewer.app import _full_dossier
from manage_db.viewer.bundle import FIXTURE_DATA


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = ROOT / "docs" / "viewer-data"


def _entity_filename(node_type: str, node_id: str) -> str:
    return f"{node_type}--{node_id.replace(':', '_')}.json"


def test_static_manifest_and_entity_shards_match_backend_fixture() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
    search = json.loads((BUNDLE_ROOT / manifest["search_shard"]).read_text())

    assert manifest["snapshot_id"] == fixture.SNAPSHOT_ID
    assert manifest["bundle_version"] == fixture.BUNDLE_VERSION
    assert manifest["data_mode"] == "fixture-static-bundle"
    assert manifest["entity_count"] == len(fixture.NODES)
    assert {(row["node_type"], row["node_id"]) for row in search["nodes"]} == set(fixture.NODES)

    for (node_type, node_id), node in fixture.NODES.items():
        static_dossier = json.loads((BUNDLE_ROOT / "entities" / _entity_filename(node_type, node_id)).read_text())
        assert static_dossier == _full_dossier(FIXTURE_DATA, node)


def test_embedded_file_fallback_is_generated_from_same_bundle() -> None:
    source = (BUNDLE_ROOT / "fixture.js").read_text()
    match = re.fullmatch(r"window\.JOUVENCE_FIXTURE_BUNDLE = (.*);\n", source, flags=re.DOTALL)
    assert match is not None
    embedded = json.loads(match.group(1))
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
    search = json.loads((BUNDLE_ROOT / "search.json").read_text())
    assert embedded["manifest"] == manifest
    assert embedded["search"] == search

    for key, dossier in embedded["entities"].items():
        node_type, node_id = key.split(":", 1)
        assert dossier == _full_dossier(FIXTURE_DATA, fixture.NODES[(node_type, node_id)])


def test_static_fixture_does_not_promote_ranked_gefitinib_link_to_observed() -> None:
    dossier = json.loads((BUNDLE_ROOT / "entities" / "gene--ENSG00000012048.json").read_text())
    assert all(row["neighbor_id"] != "CHEMBL1201585" for row in dossier["edges"])
    assert any(
        row["target_id"] == "CHEMBL1201585" and row["row_kind"] == "ranked"
        for row in dossier["long_range"]
    )