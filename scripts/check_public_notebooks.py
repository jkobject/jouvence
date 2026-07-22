#!/usr/bin/env python3
"""Static and execution smoke checks for the public Jouvence notebooks."""

from __future__ import annotations

import argparse
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
CREDENTIAL_ACCESS_PATTERNS = (
    "os.environ['GOOGLE_APPLICATION_CREDENTIALS']",
    'os.environ["GOOGLE_APPLICATION_CREDENTIALS"]',
    "os.getenv('GOOGLE_APPLICATION_CREDENTIALS'",
    'os.getenv("GOOGLE_APPLICATION_CREDENTIALS"',
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


def check_notebook(path: Path) -> dict[str, object]:
    notebook = nbformat.read(path, as_version=4)
    text = "\n".join(str(cell.source) for cell in notebook.cells)
    lower = text.lower()
    failures: list[str] = []
    markdown = [cell for cell in notebook.cells if cell.cell_type == "markdown"]
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    code_text = "\n".join(str(cell.source) for cell in code)
    headings = [
        line
        for cell in markdown
        for line in cell.source.splitlines()
        if re.match(r"^##(?:#)?\s+\S", line)
    ]
    if len(notebook.cells) < 30:
        failures.append("requires at least 30 meaningful cells")
    if len(markdown) < 12 or len(code) < 10:
        failures.append("requires substantial markdown/code balance (>=12 markdown, >=10 code)")
    if len(headings) < 5:
        failures.append("requires at least 5 real chapter/subchapter headings")
    if any(not cell.source.strip() for cell in notebook.cells):
        failures.append("contains empty cell padding")
    if any(len(cell.source.split()) < 5 for cell in markdown):
        failures.append("contains trivial markdown cell")
    if notebook.metadata.get("jouvence", {}).get("bounded") is not True:
        failures.append("missing metadata.jouvence.bounded=true")
    if notebook.metadata.get("jouvence", {}).get("read_only") is not True:
        failures.append("missing metadata.jouvence.read_only=true")
    if any(pattern in code_text for pattern in WRITE_PATTERNS):
        failures.append("contains forbidden write operation")
    if any(pattern in code_text for pattern in UNBOUNDED_PARQUET_PATTERNS):
        failures.append("contains unbounded Parquet read")
    if any(pattern in code_text for pattern in NETWORK_PATTERNS):
        failures.append("contains direct network/process operation")
    if any(pattern in code_text for pattern in CREDENTIAL_ACCESS_PATTERNS):
        failures.append("contains direct credential-file access")
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
        "chapter_headings": len(headings),
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
