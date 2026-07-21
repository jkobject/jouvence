from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from reproduce.generate_source_reproduction_notebooks import GROUPS, build_notebook

REPO_ROOT = Path(__file__).resolve().parents[1]
REPRODUCE = REPO_ROOT / "reproduce"
INVENTORY_PATH = REPRODUCE / "source_family_inventory.json"
EXPECTED_NOTEBOOKS = {
    "26_source_reproduction_index.ipynb",
    "27_source_native_protein_context_reproduction.ipynb",
    "28_cell_line_pharmacology_clinical_reproduction.ipynb",
    "29_official_features_exports_reproduction.ipynb",
}
EXPECTED_CANONICAL_FAMILIES = {
    "biogrid_5_0_258",
    "cellosaurus",
    "cellxgene",
    "depmap_ccle",
    "encode_re2g",
    "ensembl",
    "gtex",
    "hpa_25_1",
    "hpo_ontology",
    "opentargets_26_03",
    "reactome_go",
    "txgnn_legacy_sources",
}
EXPECTED_OFFICIAL_FEATURE_SOURCES = {
    "cell_line_textual_summary": "cellosaurus",
    "cell_type_textual_summary": "cell_ontology",
    "molecule_fingerprint": "rdkit_fingerprints",
    "protein_textual_summary": "uniprotkb",
    "tissue_textual_summary": "uberon",
}
EXPECTED_OFFICIAL_FAMILIES = set(EXPECTED_OFFICIAL_FEATURE_SOURCES.values())
REQUIRED_FIELDS = {
    "id",
    "source_dataset",
    "status",
    "release",
    "source_url",
    "license",
    "access_method",
    "historical_acquisition",
    "cache_template",
    "preprocessing_entrypoint",
    "mapping_rules",
    "rejection_rules",
    "outputs",
    "validation_evidence",
    "reproduction_notebook",
    "anchor",
    "explanatory_complete",
    "bounded_fixture_available",
    "gap",
}
FORBIDDEN_CODE_TOKENS = {
    "subprocess",
    "os.system",
    "shell=True",
    "requests",
    "urllib",
    "http.client",
    "ftplib",
    "socket",
    "gcsfs",
    "google.cloud",
    "lamindb",
    "gs://",
    "/mnt/gcs",
    "/Users/jkobject/mnt/gcs",
    "SAFE_MODE_COMPLETE",
}


def inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text())


def notebook_code(path: Path) -> list[str]:
    nb = nbformat.read(path, as_version=4)
    return [cell.source for cell in nb.cells if cell.cell_type == "code"]


def test_inventory_reconciles_the_canonical_denominator_from_durable_evidence() -> None:
    payload = inventory()
    rows = payload["sources"]
    assert payload["schema_version"] == 2
    assert set(payload["canonical_source_ids"]) == EXPECTED_CANONICAL_FAMILIES
    assert set(payload["official_source_ids"]) == EXPECTED_OFFICIAL_FAMILIES
    assert {row["id"] for row in rows if row["status"] == "canonical"} == EXPECTED_CANONICAL_FAMILIES
    assert {row["id"] for row in rows if row["status"] == "official"} == (
        EXPECTED_OFFICIAL_FAMILIES - EXPECTED_CANONICAL_FAMILIES
    )
    assert len(rows) == len({row["id"] for row in rows})
    assert payload["denominator_evidence"]
    for evidence in payload["denominator_evidence"]:
        assert (REPO_ROOT / evidence).exists(), evidence


def test_official_feature_denominator_is_derived_from_durable_feature_evidence() -> None:
    """Guard against circular inventory tests that omit official feature sources."""
    evidence = nbformat.read(REPRODUCE / "19_node_sequence_text_features_summary.ipynb", as_version=4)
    text = "\n".join(cell.source for cell in evidence.cells)
    for feature_table, source_id in EXPECTED_OFFICIAL_FEATURE_SOURCES.items():
        assert feature_table in text, feature_table
        assert source_id in set(inventory()["official_source_ids"]), source_id


def test_validation_evidence_is_human_followable_and_local_when_it_names_a_repo_artifact() -> None:
    allowed_bare_notebooks = EXPECTED_NOTEBOOKS | {
        "06_build_core_edges_and_evidence.ipynb",
        "07_opentargets_edges_and_evidence.ipynb",
    }
    for row in inventory()["sources"]:
        evidence = row["validation_evidence"]
        assert "['" not in evidence and "']" not in evidence, row["id"]
        for token in evidence.replace("`", "").replace(":", " ").split():
            cleaned = token.strip(".,;()")
            if cleaned.startswith(("docs/", "reproduce/", "tests/")):
                assert (REPO_ROOT / cleaned).exists(), (row["id"], cleaned)
            elif cleaned.endswith(".ipynb"):
                assert cleaned in allowed_bare_notebooks, (row["id"], cleaned)


def test_known_release_and_status_semantics_are_not_overstated() -> None:
    rows = {row["id"]: row for row in inventory()["sources"]}
    assert "55.0" in rows["cellosaurus"]["release"]
    assert "56" not in rows["cellosaurus"]["release"]
    biogrid_outputs = "\n".join(rows["biogrid_5_0_258"]["outputs"])
    assert "canonical protein_interacts_protein" in biogrid_outputs
    assert "staged protein_has_ptm_site" in biogrid_outputs
    assert "staged protein_interacts_protein" not in biogrid_outputs


def test_every_inventory_row_has_explanatory_fields_or_an_honest_gap() -> None:
    for row in inventory()["sources"]:
        assert REQUIRED_FIELDS <= row.keys(), row["id"]
        for field in REQUIRED_FIELDS - {"explanatory_complete", "bounded_fixture_available"}:
            assert row[field] not in (None, "", []), (row["id"], field)
        assert row["status"] in {"canonical", "official", "staged", "deferred", "not_reproducible_yet"}
        if row["explanatory_complete"]:
            for field in (
                "release",
                "source_url",
                "license",
                "access_method",
                "preprocessing_entrypoint",
                "outputs",
                "validation_evidence",
            ):
                assert not str(row[field]).lower().startswith("unknown"), (row["id"], field)
        if not row["bounded_fixture_available"]:
            assert len(row["gap"]) >= 20, row["id"]


def test_inventory_does_not_claim_removed_or_rejected_builders_as_current() -> None:
    rendered = json.dumps(inventory(), sort_keys=True)
    assert "t_11705f3d" not in rendered
    assert "scripts/stage_biogrid_categorized.py" not in rendered
    assert "scripts/acquire_reproduction_sources.py" not in rendered
    for row in inventory()["sources"]:
        entrypoints = row["preprocessing_entrypoint"]
        if entrypoints.startswith("honest gap:"):
            continue
        for value in entrypoints.split(";"):
            assert (REPO_ROOT / value.strip()).exists(), (row["id"], value)


def test_every_source_maps_to_an_existing_notebook_anchor() -> None:
    for row in inventory()["sources"]:
        path = REPRODUCE / row["reproduction_notebook"]
        assert path.name in EXPECTED_NOTEBOOKS, row["id"]
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        markdown = "\n".join(cell.source for cell in nb.cells if cell.cell_type == "markdown")
        assert f'<a id="{row["anchor"]}"></a>' in markdown, row["id"]
        assert row["source_dataset"] in markdown, row["id"]


def test_generated_notebook_sources_are_deterministic() -> None:
    payload = inventory()
    for name, group in GROUPS.items():
        actual = nbformat.read(REPRODUCE / name, as_version=4)
        expected = build_notebook(group, payload)
        assert actual == expected


def test_notebook_code_is_bounded_local_and_never_dispatches_production_work() -> None:
    allowed_import_roots = {
        "json",
        "pathlib",
        "tempfile",
        "pandas",
        "manage_db",
    }
    for name in EXPECTED_NOTEBOOKS:
        for source in notebook_code(REPRODUCE / name):
            lowered = source.lower()
            assert not source.lstrip().startswith(("!", "%", "%%")), name
            for token in FORBIDDEN_CODE_TOKENS:
                assert token.lower() not in lowered, (name, token)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                    assert roots <= allowed_import_roots, (name, roots)
                elif isinstance(node, ast.ImportFrom):
                    assert node.module
                    assert node.module.split(".", 1)[0] in allowed_import_roots, (name, node.module)
            assert ".main(" not in source
            assert "parse_args(" not in source


def test_notebooks_execute_offline_from_a_temporary_working_directory(tmp_path: Path) -> None:
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        for name in sorted(EXPECTED_NOTEBOOKS):
            nb = nbformat.read(REPRODUCE / name, as_version=4)
            executed = NotebookClient(
                nb,
                timeout=120,
                kernel_name="python3",
                resources={"metadata": {"path": str(tmp_path)}},
            ).execute()
            code_cells = [cell for cell in executed.cells if cell.cell_type == "code"]
            assert code_cells
            assert all(cell.execution_count is not None for cell in code_cells)
            assert any(cell.outputs for cell in code_cells)
    finally:
        os.chdir(old_cwd)


def test_bounded_demonstrations_use_real_repository_functions() -> None:
    combined = "\n".join(
        source for name in EXPECTED_NOTEBOOKS for source in notebook_code(REPRODUCE / name)
    )
    assert "parse_endpoint" in combined
    assert "map_endpoint" in combined
    assert "_parse_crispr_gene_column" in combined
    assert "parse_cellosaurus_obo" in combined
    assert "fingerprint_sha256" in combined
    assert "molecule_fingerprint_schema" in combined
