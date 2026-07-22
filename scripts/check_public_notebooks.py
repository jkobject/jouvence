#!/usr/bin/env python3
"""Static and execution smoke checks for the public Jouvence notebooks."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import json
import os
import re
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
EXPECTED = [
    "01_data_model_and_use_cases.ipynb",
    "02_nodes_features_and_embeddings.ipynb",
    "03_relations_evidence_and_questions.ipynb",
    "04_lamindb_equivalent_queries.ipynb",
    "05_sampled_pyg_heterodata.ipynb",
    "06_sampled_ml_use_cases.ipynb",
]
FORBIDDEN = [
    "/Users/jkobject/mnt/gcs",
    "/mnt/gcs/jouvencekb",
    "jkobject-1549353370965",
    "00_setup_requester_pays",
    "pq.read_table(PUBLIC_KG_ROOT",
    "pd.read_parquet(PUBLIC_KG_ROOT",
]
REQUIRED_PHRASES = [
    "what this means",
    "does not mean",
    "not prove",
    "leakage",
    "partial",
    "bounded",
]
REQUIRED_NOTEBOOK_CONCEPTS = {
    "01_data_model_and_use_cases.ipynb": (
        "application default credentials",
        "requester-pays",
        "serviceusage.services.use",
        "edge key",
        "proof/",
    ),
    "02_nodes_features_and_embeddings.ipynb": (
        "accepted immutable",
        "manifest",
        "cosine",
        "pca fallback",
        "sequence modality",
        "leakage",
    ),
    "03_relations_evidence_and_questions.ipynb": (
        "edge key",
        "source_record_id",
        "observed",
        "inferred",
        "provenance",
        "bounded",
    ),
    "04_lamindb_equivalent_queries.ipynb": (
        "canonical parquet",
        "jkobject/jouvencekb",
        "read-only",
        "partial",
        "exact-id",
        "troubleshoot",
    ),
    "05_sampled_pyg_heterodata.ipynb": (
        "heterodata",
        "node map",
        "edge_index",
        "fallback",
        "feature coverage",
        "reverse",
    ),
    "06_sampled_ml_use_cases.ipynb": (
        "negative samples",
        "split",
        "leakage",
        "error analysis",
        "metric",
        "link prediction",
    ),
}
PLACEHOLDER_PATTERNS = (
    r"(?im)^\s*(?:#{1,6}\s*)?coming soon\b",
    r"(?im)^\s*(?:#{1,6}\s*)?(?:todo|tbd|placeholder|stub)(?:\s*[:—-]|\s*$)",
    r"(?im)^\s*(?:#{1,6}\s*)?(?:lorem ipsum|to be completed)\b",
)
INTERPRETATION_HEADINGS = ("interpret", "limitation", "what this means", "boundary")
CHECKPOINT_HEADINGS = ("checkpoint", "troubleshoot", "practice", "takeaway", "next step")
WRITE_PATTERNS = (
    ".write_text(",
    ".write_bytes(",
    ".to_parquet(",
    ".to_csv(",
    ".unlink(",
    "shutil.rmtree(",
    "os.remove(",
    "write_nodes(",
    "write_edges(",
    "write_evidence(",
)
UNBOUNDED_PARQUET_PATTERNS = ("pd.read_parquet(", "pq.read_table(", "pyarrow.parquet.read_table(")
NETWORK_PATTERNS = ("requests.", "httpx.", "urllib.request", "subprocess.", "socket.")
ALLOWED_ENVIRONMENT_VARIABLES = (
    "JOUVENCE_BILLING_PROJECT",
    "JOUVENCE_DATA_MODE",
    "JOUVENCE_EMBEDDING_MANIFEST_URI",
    "JOUVENCE_LAMIN_LIVE",
    "JOUVENCE_NOTEBOOK_CACHE",
)
SCRUBBED_EXECUTION_ENV = (
    "JOUVENCE_BILLING_PROJECT",
    "JOUVENCE_LAMIN_LIVE",
    "JOUVENCE_EMBEDDING_MANIFEST_URI",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


@contextmanager
def fixture_execution_environment(cache_path: Path):
    """Force generated-notebook execution into a contained fixture environment."""

    previous = os.environ.copy()
    try:
        os.environ["JOUVENCE_DATA_MODE"] = "fixture"
        os.environ["JOUVENCE_NOTEBOOK_CACHE"] = str(cache_path)
        for name in SCRUBBED_EXECUTION_ENV:
            os.environ.pop(name, None)
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _leading_heading(source: str) -> tuple[int, str] | None:
    """Return the first Markdown heading only when it leads the cell."""

    first_line = next((line.strip() for line in source.splitlines() if line.strip()), "")
    match = re.fullmatch(r"(#{1,6})\s+(.+)", first_line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip().lower()


def _chapter_contracts(notebook: nbformat.NotebookNode) -> list[dict[str, object]]:
    """Describe chapter-level teaching progression without prescribing total cells."""

    chapter_starts = [
        index
        for index, cell in enumerate(notebook.cells)
        if cell.cell_type == "markdown"
        and (heading := _leading_heading(str(cell.source))) is not None
        and heading[0] == 2
    ]
    contracts: list[dict[str, object]] = []
    for position, start in enumerate(chapter_starts):
        end = chapter_starts[position + 1] if position + 1 < len(chapter_starts) else len(notebook.cells)
        cells = notebook.cells[start:end]
        headings = [
            heading[1]
            for cell in cells
            if cell.cell_type == "markdown"
            and (heading := _leading_heading(str(cell.source))) is not None
            and heading[0] == 3
        ]
        text = "\n".join(str(cell.source) for cell in cells).lower()
        chapter_heading = _leading_heading(str(notebook.cells[start].source))
        assert chapter_heading is not None
        contracts.append(
            {
                "heading": chapter_heading[1],
                "has_code": any(cell.cell_type == "code" and cell.source.strip() for cell in cells),
                "has_comment": any(
                    cell.cell_type == "code"
                    and re.search(r"(?m)^\s*#\s+\S", str(cell.source)) is not None
                    for cell in cells
                ),
                "has_interpretation": any(
                    term in heading for heading in headings for term in INTERPRETATION_HEADINGS
                ),
                "has_checkpoint": any(
                    term in heading for heading in headings for term in CHECKPOINT_HEADINGS
                ),
                "text": text,
            }
        )
    return contracts


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """Resolve a call target through direct and imported aliases."""

    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _code_capability_failures(code_text: str) -> list[str]:
    """Reject executable capabilities outside the fixture-only course contract."""

    try:
        tree = ast.parse(code_text)
    except SyntaxError as error:
        return [f"contains invalid Python code: {error.msg}"]

    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                aliases[imported.asname or imported.name.split(".")[0]] = imported.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for imported in node.names:
                aliases[imported.asname or imported.name] = f"{node.module}.{imported.name}"

    failures: set[str] = set()
    write_methods = {
        "open",
        "to_csv",
        "to_json",
        "to_parquet",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
        "writelines",
    }
    process_prefixes = ("multiprocessing.", "os.popen", "os.system", "subprocess.")
    network_prefixes = ("httpx.", "requests.", "socket.", "urllib.request.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _qualified_name(node.value, aliases) == "os.environ":
            key = _literal_string(node.slice)
            if key not in ALLOWED_ENVIRONMENT_VARIABLES:
                failures.add("contains undeclared environment access")
        if not isinstance(node, ast.Call):
            continue

        name = _qualified_name(node.func, aliases) or ""
        method = name.rsplit(".", 1)[-1]
        if name in {"os.getenv", "os.environ.get"}:
            key = _literal_string(node.args[0] if node.args else None)
            if key not in ALLOWED_ENVIRONMENT_VARIABLES:
                failures.add("contains undeclared environment access")
        if name == "open" or method == "open":
            mode_node = node.args[1] if len(node.args) > 1 else next(
                (keyword.value for keyword in node.keywords if keyword.arg == "mode"),
                None,
            )
            mode = _literal_string(mode_node)
            if mode is None or any(flag in mode for flag in "wax+"):
                failures.add("contains forbidden write operation")
        elif method in write_methods:
            failures.add("contains forbidden write operation")
        if name.startswith(process_prefixes):
            failures.add("contains direct process operation")
        if name.startswith(network_prefixes):
            failures.add("contains direct network operation")

    return sorted(failures)


def check_notebook(path: Path) -> dict[str, object]:
    notebook = nbformat.read(path, as_version=4)
    text = "\n".join(str(cell.source) for cell in notebook.cells)
    lower = text.lower()
    failures: list[str] = []
    markdown = [cell for cell in notebook.cells if cell.cell_type == "markdown"]
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    code_text = "\n".join(str(cell.source) for cell in code)
    title_headings = [
        line
        for cell in markdown
        for line in cell.source.splitlines()
        if re.match(r"^#\s+\S", line)
    ]
    chapter_headings = [
        line
        for cell in markdown
        for line in cell.source.splitlines()
        if re.match(r"^##\s+\S", line)
    ]
    subsection_headings = [
        line
        for cell in markdown
        for line in cell.source.splitlines()
        if re.match(r"^###\s+\S", line)
    ]
    leading_titles = [
        cell
        for cell in markdown
        if (heading := _leading_heading(str(cell.source))) is not None and heading[0] == 1
    ]
    chapter_contracts = _chapter_contracts(notebook)
    if not title_headings:
        failures.append("missing course title heading")
    if not chapter_headings:
        failures.append("missing chapter heading")
    if not subsection_headings:
        failures.append("missing subsection heading")
    if not code:
        failures.append("missing executable example")
    if len(leading_titles) != 1 or any(
        re.search(r"(?m)^#{2,6}\s+\S", str(cell.source)) for cell in leading_titles
    ):
        failures.append("course title must be a dedicated leading cell")
    incomplete_chapters = [
        contract["heading"]
        for contract in chapter_contracts
        if not (
            contract["has_code"]
            and contract["has_comment"]
            and contract["has_interpretation"]
            and contract["has_checkpoint"]
        )
    ]
    if len(chapter_contracts) < 2 or incomplete_chapters:
        failures.append(
            "requires coherent chapter progression with a commented example, interpretation, and checkpoint "
            f"in each chapter; incomplete={incomplete_chapters}"
        )
    if not any(term in lower for term in ("interpret", "limitation", "does not", "not prove", "boundary")):
        failures.append("missing interpretation or limitations")
    if any(re.search(pattern, lower) for pattern in PLACEHOLDER_PATTERNS):
        failures.append("contains placeholder marker")
    required_concepts = REQUIRED_NOTEBOOK_CONCEPTS.get(path.name, ())
    concept_chapters = {
        index
        for index, contract in enumerate(chapter_contracts)
        if any(concept in str(contract["text"]) for concept in required_concepts)
    }
    missing_concepts = [
        concept
        for concept in required_concepts
        if not any(concept in str(contract["text"]) for contract in chapter_contracts)
    ]
    if missing_concepts:
        failures.append(f"missing required curriculum concepts: {missing_concepts}")
    if required_concepts and len(concept_chapters) < 2:
        failures.append("required curriculum concepts must be taught across multiple chapters")
    if any(not cell.source.strip() for cell in notebook.cells):
        failures.append("contains empty cell padding")
    normalized_sources = [re.sub(r"\s+", " ", str(cell.source)).strip().lower() for cell in notebook.cells]
    if len(normalized_sources) != len(set(normalized_sources)):
        failures.append("contains repeated cell padding")
    if any(len(cell.source.split()) < 5 for cell in markdown):
        failures.append("contains trivial markdown cell")
    if notebook.metadata.get("jouvence", {}).get("bounded") is not True:
        failures.append("missing metadata.jouvence.bounded=true")
    if notebook.metadata.get("jouvence", {}).get("read_only") is not True:
        failures.append("missing metadata.jouvence.read_only=true")
    failures.extend(_code_capability_failures(code_text))
    if any(pattern in code_text for pattern in WRITE_PATTERNS):
        failures.append("contains forbidden write operation")
    if any(pattern in code_text for pattern in UNBOUNDED_PARQUET_PATTERNS):
        failures.append("contains unbounded Parquet read")
    if any(pattern in code_text for pattern in NETWORK_PATTERNS):
        failures.append("contains direct network/process operation")
    for token in FORBIDDEN:
        if token in text:
            failures.append(f"forbidden token: {token}")
    for cell in notebook.cells:
        if cell.cell_type == "code" and (cell.get("execution_count") is not None or cell.get("outputs")):
            failures.append("committed code output/execution count")
            break
    return {
        "path": str(path.relative_to(ROOT)),
        "cells": len(notebook.cells),
        "markdown_cells": len(markdown),
        "code_cells": len(code),
        "title_headings": len(title_headings),
        "chapter_headings": len(chapter_headings),
        "subsection_headings": len(subsection_headings),
        "coherent_chapters": sum(
            bool(
                contract["has_code"]
                and contract["has_comment"]
                and contract["has_interpretation"]
                and contract["has_checkpoint"]
            )
            for contract in chapter_contracts
        ),
        "commented_chapters": sum(bool(contract["has_comment"]) for contract in chapter_contracts),
        "curriculum_chapters": len(concept_chapters),
        "failures": failures,
        "phrases": {phrase: phrase in lower for phrase in REQUIRED_PHRASES},
    }


def execute_notebook(path: Path, destination: Path) -> dict[str, object]:
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    with fixture_execution_environment(destination / "_fixture_cache"):
        client.execute()
    output_path = destination / path.name
    nbformat.write(notebook, output_path)
    return {"path": str(path.relative_to(ROOT)), "status": "pass", "executed_copy": str(output_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    actual = sorted(path.name for path in NOTEBOOK_DIR.glob("*.ipynb"))
    suite_failures = [] if actual == EXPECTED else [f"notebook set mismatch: {actual}"]
    checks = [check_notebook(NOTEBOOK_DIR / name) for name in EXPECTED if (NOTEBOOK_DIR / name).exists()]
    suite_text = "\n".join(
        "\n".join(str(cell.source) for cell in nbformat.read(NOTEBOOK_DIR / name, as_version=4).cells).lower()
        for name in EXPECTED
        if (NOTEBOOK_DIR / name).exists()
    )
    for phrase in REQUIRED_PHRASES:
        if phrase not in suite_text:
            suite_failures.append(f"suite missing interpretation phrase: {phrase}")
    for check in checks:
        suite_failures.extend(f"{check['path']}: {failure}" for failure in check["failures"])

    executions: list[dict[str, object]] = []
    if args.execute and not suite_failures:
        destination = Path(tempfile.mkdtemp(prefix="jouvence-public-notebooks-"))
        for name in EXPECTED:
            executions.append(execute_notebook(NOTEBOOK_DIR / name, destination))

    report = {
        "status": "pass" if not suite_failures else "fail",
        "expected_notebooks": EXPECTED,
        "static_checks": checks,
        "executions": executions,
        "failures": suite_failures,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
