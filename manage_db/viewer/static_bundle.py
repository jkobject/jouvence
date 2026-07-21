"""Build the deterministic static viewer bundle from the Phase 1 fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import fixture
from .app import _full_dossier, _node_payload
from .bundle import FIXTURE_DATA

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "viewer-data"


def entity_filename(node_type: str, node_id: str) -> str:
    """Return a stable, URL-safe-enough fixture shard name."""
    return f"{node_type}--{node_id.replace(':', '_')}.json"


def build_bundle() -> dict[str, Any]:
    """Return the in-memory equivalent of the manifest and all fixture shards."""
    search_nodes = []
    entities: dict[str, dict[str, Any]] = {}
    entity_shards: dict[str, str] = {}
    for (node_type, node_id), node in sorted(fixture.NODES.items()):
        key = f"{node_type}:{node_id}"
        payload = _node_payload(node)
        payload["entity_shard"] = f"entities/{entity_filename(node_type, node_id)}"
        search_nodes.append(payload)
        entities[key] = _full_dossier(FIXTURE_DATA, node)
        entity_shards[key] = payload["entity_shard"]

    manifest = {
        "schema_version": "jouvence-viewer-static-v1",
        "snapshot_id": fixture.SNAPSHOT_ID,
        "bundle_version": fixture.BUNDLE_VERSION,
        "data_mode": "fixture-static-bundle",
        "fixture_only": True,
        "search_shard": "search.json",
        "entity_shards": entity_shards,
        "entity_count": len(entities),
        "row_kinds": ["observed", "ranked", "inferred"],
    }
    search = {
        "meta": {
            "snapshot_id": fixture.SNAPSHOT_ID,
            "bundle_version": fixture.BUNDLE_VERSION,
            "data_mode": "fixture-static-bundle",
            "truncated": False,
        },
        "nodes": search_nodes,
    }
    return {"manifest": manifest, "search": search, "entities": entities}


def write_bundle(output: Path = DEFAULT_OUTPUT) -> list[Path]:
    """Write reviewed static assets and return every generated path."""
    bundle = build_bundle()
    entities_dir = output / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    expected_entity_files = {
        entity_filename(dossier["node"]["node_type"], dossier["node"]["node_id"])
        for dossier in bundle["entities"].values()
    }
    for existing in entities_dir.glob("*.json"):
        if existing.name not in expected_entity_files:
            existing.unlink()

    written = []
    for name, payload in (("manifest.json", bundle["manifest"]), ("search.json", bundle["search"])):
        path = output / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        written.append(path)

    for dossier in bundle["entities"].values():
        node = dossier["node"]
        path = entities_dir / entity_filename(node["node_type"], node["node_id"])
        path.write_text(json.dumps(dossier, indent=2, sort_keys=True) + "\n")
        written.append(path)

    embedded = output / "fixture.js"
    embedded.write_text(
        "window.JOUVENCE_FIXTURE_BUNDLE = "
        + json.dumps(bundle, separators=(",", ":"), sort_keys=True)
        + ";\n"
    )
    written.append(embedded)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the deterministic Jouvence viewer static bundle.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    for path in write_bundle(args.output):
        print(path)


if __name__ == "__main__":
    main()
