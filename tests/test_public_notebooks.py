from __future__ import annotations

from pathlib import Path
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
        code = [cell for cell in notebook.cells if cell.cell_type == "code"]
        check = check_public_notebooks.check_notebook(path)

        assert check["failures"] == [], path.name
        assert check["cells"] == len(notebook.cells)
        assert check["commented_chapters"] == check["chapter_headings"], path.name
        assert all(cell.source.strip() for cell in notebook.cells), path.name
        assert all(cell.execution_count is None and not cell.outputs for cell in code), path.name


def test_static_checker_accepts_a_compact_complete_course_with_placeholder_discussion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Focused lesson\n\nThis lesson answers one bounded scientific question."
            ),
            nbformat.v4.new_markdown_cell(
                "## Inspect one relation\n\nUse a stable identifier and retain source provenance."
            ),
            nbformat.v4.new_code_cell(
                "# Inspect the bounded rows before interpreting them.\nrows = [1, 2, 3]\nprint(rows)"
            ),
            nbformat.v4.new_markdown_cell(
                "### Interpretation and limitations\n\n"
                "This illustrates execution but does not prove biological completeness."
            ),
            nbformat.v4.new_markdown_cell(
                "### Checkpoint\n\nExplain which conclusion the bounded rows support before continuing."
            ),
            nbformat.v4.new_markdown_cell(
                "## Troubleshoot misleading lesson labels\n\n"
                "Discussing the words placeholder and smoke test is legitimate pedagogical prose, "
                "not evidence that this complete lesson is unfinished."
            ),
            nbformat.v4.new_code_cell(
                "# Summarize the exact bounded result for the checkpoint.\n"
                "summary = {'rows': len(rows), 'bounded': True}\nprint(summary)"
            ),
            nbformat.v4.new_markdown_cell(
                "### Interpretation and limitations\n\n"
                "The summary describes this example but does not establish source completeness."
            ),
            nbformat.v4.new_markdown_cell(
                "### Troubleshooting checkpoint\n\n"
                "Check the selected identifier and bounded input before increasing scope."
            ),
            nbformat.v4.new_markdown_cell(
                "### Next lesson\n\nContinue only after recording the supported claim and its boundary."
            ),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "focused.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    assert result["cells"] == 10
    assert result["failures"] == []


def test_static_checker_rejects_a_two_cell_keyword_stuffed_notebook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Relations\n\n"
                "## Everything at once\n\n"
                "### Interpretation and limitations\n\n"
                "edge key source_record_id observed inferred provenance bounded. "
                "This does not prove completeness, but it merely lists the required vocabulary."
            ),
            nbformat.v4.new_code_cell("value = 1\nprint(value)"),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "03_relations_evidence_and_questions.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    failures = "\n".join(str(failure) for failure in result_failures)
    assert "coherent chapter" in failures
    assert "multiple chapters" in failures


def test_static_checker_rejects_a_structurally_dressed_keyword_stuffed_non_lesson(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Relations shell\n\nThis shell distributes required words across a formal course shape."
            ),
            nbformat.v4.new_markdown_cell(
                "## A\n\nEdge key source_record_id observed are the first required concepts."
            ),
            nbformat.v4.new_code_cell("# Set a value without producing an interpretable result.\nx = 1"),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nThe value is bounded and does not prove completeness."
            ),
            nbformat.v4.new_markdown_cell(
                "### Checkpoint\n\nConfirm the generic statement before continuing."
            ),
            nbformat.v4.new_markdown_cell(
                "## B\n\nInferred provenance bounded are the remaining required concepts."
            ),
            nbformat.v4.new_code_cell("# Set another value without a meaningful output.\ny = 2"),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nThe second value is partial and has a limitation."
            ),
            nbformat.v4.new_markdown_cell(
                "### Checkpoint\n\nRepeat the generic conclusion to finish."
            ),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "03_relations_evidence_and_questions.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    failures = "\n".join(str(failure) for failure in result["failures"])
    assert "descriptive chapter heading" in failures
    assert "observable output" in failures


def test_static_checker_rejects_repeated_cell_padding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repeated_chapter = (
        "## Repeated chapter\n\n"
        "edge key source_record_id observed inferred provenance bounded are listed without a lesson."
    )
    repeated_code = "value = 1\nprint(value)"
    repeated_interpretation = (
        "### Interpretation\n\nThis repeated text does not prove pedagogical completeness."
    )
    repeated_checkpoint = (
        "### Checkpoint\n\nRepeat the same material instead of developing the question."
    )
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Padded relations lesson\n\nRepeated cells must not substitute for coherent progression."
            ),
            nbformat.v4.new_markdown_cell(repeated_chapter),
            nbformat.v4.new_code_cell(repeated_code),
            nbformat.v4.new_markdown_cell(repeated_interpretation),
            nbformat.v4.new_markdown_cell(repeated_checkpoint),
            nbformat.v4.new_markdown_cell(repeated_chapter),
            nbformat.v4.new_code_cell(repeated_code),
            nbformat.v4.new_markdown_cell(repeated_interpretation),
            nbformat.v4.new_markdown_cell(repeated_checkpoint),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "03_relations_evidence_and_questions.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    assert "contains repeated cell padding" in result_failures


def test_static_checker_rejects_a_placeholder_without_course_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell("# Tiny notebook\n\nComing soon with examples.")],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "placeholder.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    failures = "\n".join(str(failure) for failure in result_failures)
    assert "missing chapter heading" in failures
    assert "missing subsection heading" in failures
    assert "missing executable example" in failures
    assert "missing interpretation or limitations" in failures
    assert "placeholder marker" in failures


@pytest.mark.parametrize("marker", ["TBD: add analysis", "Stub — replace me", "Lorem ipsum", "To be completed"])
def test_static_checker_rejects_explicit_unfinished_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Structured shell\n\nThe shape is complete so the unfinished marker is tested directly."
            ),
            nbformat.v4.new_markdown_cell(
                "## First chapter\n\nInspect one bounded relation and retain its provenance."
            ),
            nbformat.v4.new_code_cell("rows = [1, 2]\nprint(rows)"),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nThese rows do not prove biological completeness."
            ),
            nbformat.v4.new_markdown_cell(
                "### Checkpoint\n\nState the supported conclusion before continuing."
            ),
            nbformat.v4.new_markdown_cell(f"## Second chapter\n\n{marker}"),
            nbformat.v4.new_code_cell("summary = len(rows)\nprint(summary)"),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nThe summary has a bounded interpretation and limitation."
            ),
            nbformat.v4.new_markdown_cell(
                "### Troubleshooting\n\nCheck the selected identifier before increasing scope."
            ),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "unfinished.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    assert "contains placeholder marker" in result_failures


def test_static_checker_rejects_a_known_notebook_missing_its_topic_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Generic lesson\n\nThis is substantial prose about a bounded example."
            ),
            nbformat.v4.new_markdown_cell(
                "## Generic chapter\n\nInspect the input before drawing conclusions."
            ),
            nbformat.v4.new_code_cell("values = [1, 2]\nprint(values)"),
            nbformat.v4.new_markdown_cell(
                "### Interpretation and limitations\n\nThe result does not prove completeness."
            ),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "03_relations_evidence_and_questions.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    assert any("missing required curriculum concepts" in str(failure) for failure in result_failures)


def test_static_checker_rejects_writes_unbounded_reads_and_false_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cells = [
        nbformat.v4.new_markdown_cell(
            "# Unsafe lesson\n\nA deliberately unsafe example for checker validation."
        ),
        nbformat.v4.new_code_cell(
            "Path('/tmp/escape').write_text('unsafe')\n"
            "frame = pd.read_parquet(dynamic_root)"
        ),
        nbformat.v4.new_markdown_cell(
            "## Inspect behavior\n\nThe checker should reject unsafe data access."
        ),
        nbformat.v4.new_markdown_cell(
            "### Interpretation and limitations\n\nThis example must not execute or authorize writes."
        ),
    ]
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


@pytest.mark.parametrize(
    ("unsafe_code", "expected_failure"),
    [
        ("open('/tmp/jouvence-escape', 'w').write('unsafe')", "write operation"),
        (
            "from pathlib import Path\nPath('/tmp/jouvence-escape').open('a').write('unsafe')",
            "write operation",
        ),
        ("from subprocess import run as launch\nlaunch(['whoami'])", "process operation"),
        ("import requests as client\nclient.get('https://example.com')", "network operation"),
        ("import os\nprint(os.environ.get('PRIVATE_TOKEN'))", "environment access"),
    ],
)
def test_static_checker_rejects_aliased_or_indirect_runtime_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_code: str,
    expected_failure: str,
) -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Capability boundary\n\nThis bounded course demonstrates why execution stays contained."
            ),
            nbformat.v4.new_markdown_cell(
                "## Inspect the safe input\n\nUse fixture rows and retain stable identifiers."
            ),
            nbformat.v4.new_code_cell(
                "# Inspect the fixture rows without external capabilities.\n"
                "rows = [1, 2, 3]\nprint(rows)"
            ),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nThe fixture output does not prove biological completeness."
            ),
            nbformat.v4.new_markdown_cell(
                "### Checkpoint\n\nConfirm that the selected rows support the stated conclusion."
            ),
            nbformat.v4.new_markdown_cell(
                "## Test the capability boundary\n\nThe checker must reject access beyond fixture computation."
            ),
            nbformat.v4.new_code_cell(
                "# This operation must be rejected before notebook execution.\n" + unsafe_code
            ),
            nbformat.v4.new_markdown_cell(
                "### Interpretation\n\nRejecting the operation preserves the read-only boundary."
            ),
            nbformat.v4.new_markdown_cell(
                "### Troubleshooting\n\nMove external operations outside the executable public course."
            ),
        ],
        metadata={"jouvence": {"bounded": True, "read_only": True}},
    )
    path = tmp_path / "capability_boundary.ipynb"
    nbformat.write(notebook, path)
    monkeypatch.setattr(check_public_notebooks, "ROOT", tmp_path)

    result = check_public_notebooks.check_notebook(path)

    result_failures = result["failures"]
    assert isinstance(result_failures, list)
    assert expected_failure in "\n".join(str(failure) for failure in result_failures)


@pytest.mark.parametrize(
    ("unsafe_code", "expected_failure"),
    [
        ("import subprocess\nlaunch = subprocess.run\nlaunch(['whoami'])", "process operation"),
        ("import requests\nfetch = requests.get\nfetch('https://example.com')", "network operation"),
        ("client = __import__('requests')\nclient.get('https://example.com')", "network operation"),
    ],
)
def test_capability_analysis_tracks_assignment_aliases_and_dynamic_imports(
    unsafe_code: str, expected_failure: str
) -> None:
    failures = check_public_notebooks._code_capability_failures(unsafe_code)

    assert expected_failure in "\n".join(failures)


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
