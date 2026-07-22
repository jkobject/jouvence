from __future__ import annotations

from pathlib import Path
import re
import hashlib
import os

import nbformat
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from manage_db import public_notebooks as public
from scripts import build_public_notebooks, check_public_notebooks


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
PUBLIC_NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))


def test_read_bounded_parquet_seeks_row_groups(tmp_path: Path) -> None:
    path = tmp_path / "rows.parquet"
    pq.write_table(pa.table({"id": list(range(12)), "value": [f"v{i}" for i in range(12)]}), path, row_group_size=3)

    result = public.read_bounded_parquet(path, columns=["id"], offset=4, limit=5)

    assert result["id"].tolist() == [4, 5, 6, 7, 8]
    with pytest.raises(ValueError, match="between 1"):
        public.read_bounded_parquet(path, limit=public.MAX_SAMPLE_ROWS + 1)


def test_requester_pays_requires_caller_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOUVENCE_BILLING_PROJECT", raising=False)
    with pytest.raises(ValueError, match="JOUVENCE_BILLING_PROJECT"):
        public._storage_options("gs://jouvencekb/kg/v2/nodes/gene.parquet", None)
    assert public._storage_options("gs://bucket/object", "consumer-project") == {
        "requester_pays": "consumer-project",
        "token": "google_default",
    }

    monkeypatch.setattr(
        "gcsfs.credentials.gauth.default",
        lambda **_kwargs: (object(), "adc-default-project"),
    )
    fs, path = public.url_to_fs(
        "gs://bucket/object",
        **public._storage_options("gs://bucket/object", "consumer-project"),
        skip_instance_cache=True,
    )
    assert path == "bucket/object"
    assert fs.project == "adc-default-project"
    assert fs.requester_pays == "consumer-project"

    with pytest.raises(ValueError, match="exact instance"):
        public.query_lamindb_edges(relation="x", instance="other/instance")
    with pytest.raises(ValueError, match="unsupported exact-ID"):
        public.query_lamindb_node("unknown", "id")


def test_fixture_catalog_queries_and_embeddings(tmp_path: Path) -> None:
    root = public.build_public_fixture(tmp_path / "kg")

    catalog = public.parquet_catalog(root)
    assert {"nodes", "edges", "evidence", "features"}.issubset(set(catalog["layer"]))
    assert catalog["rows"].gt(0).all()

    diseases = public.diseases_with_gene_evidence(root, "ENSG00000141510", limit=10)
    assert diseases["disease_id"].tolist() == ["EFO:0000616", "MONDO:0007254"]
    assert diseases["evidence_rows"].tolist() == [1, 1]

    neighbors = public.nearest_embeddings(
        root / "features" / "embeddings" / "text" / "fixture.parquet",
        "ENSG00000012048",
        limit=2,
    )
    assert neighbors.iloc[0]["node_id"] == "ENSG00000139618"
    assert np.isfinite(neighbors["cosine_similarity"]).all()

    joined = public.bounded_edge_evidence_join(
        root,
        "disease_associated_gene",
        edge_limit=5,
        evidence_limit=10,
    )
    assert len(joined) == 5
    assert {
        "source_assertion",
        "source_evidence",
        "source_record_id",
    }.issubset(joined.columns)


def test_public_notebooks_are_substantial_chaptered_and_output_free() -> None:
    assert len(PUBLIC_NOTEBOOKS) == 6
    for path in PUBLIC_NOTEBOOKS:
        notebook = nbformat.read(path, as_version=4)
        markdown = [cell for cell in notebook.cells if cell.cell_type == "markdown"]
        code = [cell for cell in notebook.cells if cell.cell_type == "code"]
        headings = [
            line
            for cell in markdown
            for line in cell.source.splitlines()
            if re.match(r"^##(?:#)?\s+\S", line)
        ]

        assert len(notebook.cells) >= 30, path.name
        assert len(markdown) >= 12, path.name
        assert len(code) >= 10, path.name
        assert len(headings) >= 5, path.name
        assert all(cell.source.strip() for cell in notebook.cells), path.name
        assert all(len(cell.source.split()) >= 5 for cell in markdown), path.name
        assert all(cell.execution_count is None and not cell.outputs for cell in code), path.name


def test_static_checker_rejects_an_undersized_notebook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell("# Tiny notebook")],
        metadata={"jouvence": {"bounded": True}},
    )
    path = tmp_path / "tiny.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    assert any("at least 30 meaningful cells" in failure for failure in result["failures"])


def test_static_checker_rejects_writes_unbounded_reads_and_false_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cells = [
        nbformat.v4.new_markdown_cell(f"## Chapter {index}\n\nSubstantial explanatory content for chapter {index}.")
        if index % 2 == 0
        else nbformat.v4.new_code_cell("value = 1 + 1\nprint(value)")
        for index in range(30)
    ]
    cells[1] = nbformat.v4.new_code_cell(
        "Path('/tmp/escape').write_text('unsafe')\n"
        "frame = pd.read_parquet(dynamic_root)"
    )
    notebook = nbformat.v4.new_notebook(
        cells=cells,
        metadata={"jouvence": {"bounded": True, "read_only": False}},
    )
    path = tmp_path / "unsafe.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    failures = "\n".join(result["failures"])
    assert "read_only=true" in failures
    assert "write operation" in failures
    assert "unbounded Parquet read" in failures


def test_notebook_execution_forces_isolated_fixture_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JOUVENCE_DATA_MODE", "live")
    monkeypatch.setenv("JOUVENCE_BILLING_PROJECT", "should-not-leak")
    monkeypatch.setenv("JOUVENCE_LAMIN_LIVE", "1")
    monkeypatch.setenv("JOUVENCE_EMBEDDING_MANIFEST_URI", "gs://should-not-leak/manifest.json")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/should/not/leak.json")
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "import os\n"
                "assert os.environ['JOUVENCE_DATA_MODE'] == 'fixture'\n"
                "assert os.environ['JOUVENCE_NOTEBOOK_CACHE'].startswith(" + repr(str(tmp_path)) + ")\n"
                "for name in ['JOUVENCE_BILLING_PROJECT', 'JOUVENCE_LAMIN_LIVE', "
                "'JOUVENCE_EMBEDDING_MANIFEST_URI', 'GOOGLE_APPLICATION_CREDENTIALS']:\n"
                "    assert name not in os.environ\n"
                "print('isolated fixture pass')"
            )
        ]
    )
    path = tmp_path / "environment.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.execute_notebook(path, tmp_path)

    executed = nbformat.read(result["executed_copy"], as_version=4)
    assert "isolated fixture pass" in executed.cells[0].outputs[0]["text"]
    assert os.environ["JOUVENCE_DATA_MODE"] == "live"


def test_notebook_generation_is_byte_deterministic() -> None:
    build_public_notebooks.main()
    first = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in PUBLIC_NOTEBOOKS}
    build_public_notebooks.main()
    second = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in PUBLIC_NOTEBOOKS}
    assert first == second


def test_course_covers_setup_release_discovery_and_visual_interpretation() -> None:
    texts = {
        path.name: "\n".join(cell.source for cell in nbformat.read(path, as_version=4).cells).lower()
        for path in PUBLIC_NOTEBOOKS
    }
    setup = texts["01_data_model_and_use_cases.ipynb"]
    for phrase in (
        "uv sync",
        "application default credentials",
        "requester-pays",
        "serviceusage.services.use",
        "authentication",
        "authorization",
        "billing",
        "quota",
        "proof/",
        "edge key",
    ):
        assert phrase in setup

    embeddings = texts["02_nodes_features_and_embeddings.ipynb"]
    for phrase in (
        "accepted immutable",
        "manifest",
        "coverage",
        "missingness",
        "license",
        "leakage",
        "cosine",
        "nearest",
        "umap",
        "pca fallback",
        "colorblind",
        "not functional equivalence",
        "sequence modality",
    ):
        assert phrase in embeddings


def test_embedding_helpers_preserve_alignment_and_fail_closed(tmp_path: Path) -> None:
    root = public.build_public_fixture(tmp_path / "kg")
    manifest = root / "features" / "embeddings" / "manifest.json"
    releases = public.discover_embedding_releases(manifest, modality="text")
    assert releases["release_id"].tolist() == ["fixture-text-v1"]
    assert releases["state"].tolist() == ["accepted"]

    sample = public.load_bounded_embedding_sample(releases.iloc[0]["shard_uri"], limit=4)
    matrix, metadata = public.extract_embedding_matrix(sample)
    assert matrix.shape == (4, 8)
    assert metadata["node_id"].tolist() == sample["node_id"].tolist()
    assert "embedding" not in metadata
    assert public.lookup_embedding_id(metadata, "ENSG00000141510") == 2

    similarities = public.pairwise_cosine(matrix)
    assert similarities.shape == (4, 4)
    assert np.allclose(np.diag(similarities), 1.0)
    neighbors = public.cosine_neighbors(matrix, metadata, "ENSG00000012048", limit=2)
    assert neighbors.iloc[0]["node_id"] == "ENSG00000139618"

    with pytest.raises(KeyError, match="missing-id"):
        public.lookup_embedding_id(metadata, "missing-id")
    with pytest.raises(ValueError, match="required columns"):
        public.extract_embedding_matrix(pd.DataFrame({"node_id": ["x"]}))
    with pytest.raises(ValueError, match="same dimension"):
        public.extract_embedding_matrix(
            pd.DataFrame({"node_id": ["x", "y"], "embedding": [[1.0], [1.0, 2.0]]})
        )
    with pytest.raises(ValueError, match="finite"):
        public.extract_embedding_matrix(
            pd.DataFrame({"node_id": ["x"], "embedding": [[float("nan"), 1.0]]})
        )


def test_embedding_projection_has_deterministic_pca_fallback() -> None:
    matrix = np.asarray(
        [[1.0, 0.0, 0.2], [0.9, 0.1, 0.2], [0.0, 1.0, 0.3], [0.1, 0.9, 0.4]],
        dtype=np.float32,
    )
    first, method = public.project_embedding_matrix(matrix, method="pca", random_state=17)
    second, repeated_method = public.project_embedding_matrix(matrix, method="pca", random_state=17)
    assert method == repeated_method == "pca"
    assert first.shape == (4, 2)
    assert np.allclose(first, second)


def test_release_discovery_filters_unaccepted_and_requires_immutable(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        """{
          "releases": [
            {"release_id": "accepted-v1", "state": "accepted", "immutable": true,
             "modality": "text", "model": "encoder-v1", "license": "CC-BY-4.0", "coverage": "partial",
             "shards": ["accepted.parquet"]},
            {"release_id": "rejected-v1", "state": "rejected", "immutable": true,
             "modality": "text", "model": "encoder-v1", "license": "unknown", "coverage": "partial",
             "shards": ["rejected.parquet"]},
            {"release_id": "mutable-v1", "state": "accepted", "immutable": false,
             "modality": "text", "model": "encoder-v1", "license": "CC-BY-4.0", "coverage": "partial",
             "shards": ["mutable.parquet"]}
          ]
        }"""
    )
    releases = public.discover_embedding_releases(manifest)
    assert releases["release_id"].tolist() == ["accepted-v1"]


@pytest.mark.parametrize(
    "release",
    [
        {
            "release_id": "missing-model-v1",
            "state": "accepted",
            "immutable": True,
            "modality": "text",
            "license": "CC-BY-4.0",
            "coverage": "partial",
            "shards": ["part.parquet"],
        },
        {
            "release_id": "",
            "state": "accepted",
            "immutable": True,
            "modality": "",
            "model": "",
            "license": "",
            "coverage": "",
            "shards": ["part.parquet"],
        },
    ],
)
def test_release_discovery_rejects_incomplete_identity(
    tmp_path: Path, release: dict[str, object]
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(__import__("json").dumps({"releases": [release]}))

    with pytest.raises(ValueError, match="required|non-empty"):
        public.discover_embedding_releases(manifest)


def test_sampled_pyg_and_ml_reuse_existing_pipeline(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    root = public.build_public_fixture(tmp_path / "kg")
    export = tmp_path / "pyg"

    result = public.build_sampled_pyg(root, export)
    smoke = public.run_sampled_ml(export, seed=13)

    assert result.node_counts == {"gene": 4, "disease": 3, "molecule": 3}
    assert result.edge_counts == {"disease_associated_gene": 5, "molecule_targets_gene": 4}
    assert smoke["status"] == "pass"
    assert smoke["validation"]["checks"]["nonempty_splits"] is True
