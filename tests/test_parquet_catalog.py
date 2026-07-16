from __future__ import annotations

import json
from pathlib import Path

from scripts.parquet_catalog import CATALOG_DIR, INVENTORY_PATH, schema_hash


REPO_ROOT = Path(__file__).resolve().parents[1]


def _inventory() -> dict:
    return json.loads((REPO_ROOT / INVENTORY_PATH).read_text())


def test_catalog_covers_every_logical_dataset() -> None:
    inventory = _inventory()
    datasets = inventory["datasets"]
    ids = [dataset["id"] for dataset in datasets]
    pages = {path.stem for path in (REPO_ROOT / CATALOG_DIR / "datasets").glob("*.md")}

    assert len(ids) == len(set(ids)) == inventory["dataset_count"] == 112
    assert inventory["documented_count"] == 112
    assert inventory["undocumented_count"] == 0
    assert pages == set(ids)


def test_every_schema_hash_reproduces() -> None:
    for dataset in _inventory()["datasets"]:
        assert dataset["schema_hash"] == schema_hash(dataset["fields"]), dataset["id"]


def test_text_embedding_leaves_use_per_node_type_denominators() -> None:
    leaves = [
        dataset
        for dataset in _inventory()["datasets"]
        if dataset["id"].startswith("planned_embedding__text__")
    ]

    assert len(leaves) == 9
    assert sum(dataset["rows"] for dataset in leaves) == 490_336
    assert {dataset["semantics"]["node_type"] for dataset in leaves} == {
        "cell_line",
        "cell_type",
        "disease",
        "gene",
        "molecule",
        "pathway",
        "phenotype",
        "protein",
        "tissue",
    }


def test_sharded_remap_is_two_logical_datasets_not_25_pages() -> None:
    datasets = {dataset["id"]: dataset for dataset in _inventory()["datasets"]}
    summary = datasets["feature__remap_crm_tf_enhancer_support_full_summary"]
    global_tf = datasets["feature__remap_crm_tf_enhancer_support_full_tf_global"]

    assert len(summary["objects"]) == 24
    assert summary["rows"] == 48_768_788
    assert len(global_tf["objects"]) == 1
    assert global_tf["rows"] == 1_179


def test_catalog_has_no_private_local_paths() -> None:
    paths = [
        REPO_ROOT / INVENTORY_PATH,
        REPO_ROOT / CATALOG_DIR / "embedding-release-inventory.json",
        REPO_ROOT / CATALOG_DIR / "index.md",
        *(REPO_ROOT / CATALOG_DIR / "datasets").glob("*.md"),
    ]
    forbidden = ("/Users/", "/home/ubuntu", ".omoc/")
    for path in paths:
        text = path.read_text()
        assert not any(token in text for token in forbidden), path
