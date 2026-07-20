#!/usr/bin/env python3
"""Deterministically verify the bounded commands in docs/getting-started-data.md."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from manage_db.public_notebooks import (
    PUBLIC_KG_ROOT,
    bounded_edge_evidence_join,
    build_public_fixture,
    diseases_with_gene_evidence,
    parquet_catalog,
    read_bounded_parquet,
)


def _fixture_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jouvence-quickstart-") as tmp:
        root = build_public_fixture(Path(tmp) / "kg")
        catalog = parquet_catalog(root)
        genes = read_bounded_parquet(root / "nodes" / "gene.parquet", limit=3)
        joined = bounded_edge_evidence_join(
            root,
            "disease_associated_gene",
            edge_limit=5,
            evidence_limit=10,
        )
        question = diseases_with_gene_evidence(root, "ENSG00000141510", limit=5)
        assert len(genes) == 3
        assert len(joined) == 5
        assert len(question) == 2
        return {
            "mode": "fixture",
            "status": "pass",
            "tables": len(catalog),
            "sample_rows": len(genes),
            "joined_rows": len(joined),
            "question_rows": len(question),
        }


def _live_check(billing_project: str | None) -> dict[str, Any]:
    if not billing_project:
        raise SystemExit(
            "live mode requires --billing-project or JOUVENCE_BILLING_PROJECT"
        )
    gene_uri = f"{PUBLIC_KG_ROOT}/nodes/gene.parquet"
    genes = read_bounded_parquet(
        gene_uri,
        columns=["id", "name", "source"],
        limit=3,
        billing_project=billing_project,
    )
    joined = bounded_edge_evidence_join(
        PUBLIC_KG_ROOT,
        "disease_associated_gene",
        edge_limit=100,
        evidence_limit=1_000,
        billing_project=billing_project,
    )
    assert len(genes) == 3
    assert not joined.empty
    return {
        "mode": "live",
        "status": "pass",
        "canonical_root": PUBLIC_KG_ROOT,
        "sample_uri": gene_uri,
        "sample_rows": len(genes),
        "sample_columns": list(genes.columns),
        "edge_prefix_rows": 100,
        "evidence_prefix_rows": 1_000,
        "joined_rows": len(joined),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--billing-project")
    args = parser.parse_args()
    billing_project = args.billing_project or os.environ.get(
        "JOUVENCE_BILLING_PROJECT"
    )
    result = (
        _fixture_check()
        if args.mode == "fixture"
        else _live_check(billing_project)
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()