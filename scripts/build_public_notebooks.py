#!/usr/bin/env python3
"""Generate the deterministic, output-free public Jouvence notebook suite."""

from __future__ import annotations

import hashlib
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip() + "\n")


def code(text: str):
    return nbf.v4.new_code_cell(text.strip() + "\n")


def setup(*, pyg: bool = False):
    lines = """
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path.cwd()
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

from manage_db.public_notebooks import (
    PUBLIC_KG_ROOT,
    build_public_fixture,
    parquet_catalog,
    read_bounded_parquet,
)

MODE = os.environ.get("JOUVENCE_DATA_MODE", "fixture")
BILLING_PROJECT = os.environ.get("JOUVENCE_BILLING_PROJECT")
CACHE = Path(os.environ.get("JOUVENCE_NOTEBOOK_CACHE", REPO_ROOT / "artifacts" / "cache" / "public-notebooks"))
CACHE.mkdir(parents=True, exist_ok=True)
KG_ROOT = build_public_fixture(CACHE / "kg-fixture") if MODE == "fixture" else PUBLIC_KG_ROOT
print({"mode": MODE, "kg_root": str(KG_ROOT), "bounded": True})
"""
    if pyg:
        lines += """
try:
    import torch
    import torch_geometric
except ImportError as exc:
    raise RuntimeError("Install the notebook GNN environment with: uv sync --group notebooks --group gnn") from exc
"""
    return code(lines)


def write(path: str, cells: list) -> None:
    for index, cell in enumerate(cells):
        identity = f"{path}:{index}:{cell['cell_type']}".encode()
        cell["id"] = hashlib.sha256(identity).hexdigest()[:12]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "jouvence": {"default_mode": "fixture", "bounded": True, "read_only": True},
    }
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.execution_count = None
            cell.outputs = []
    nbf.write(notebook, OUT / path)


def _legacy_placeholder_notebooks() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write(
        "01_data_model_and_use_cases.ipynb",
        [
            md("""
# 01 — Jouvence data model and scientific use cases

Jouvence separates **entities** (`nodes/`), deduplicated biological **assertions** (`edges/`), source-specific **support/provenance** (`evidence/`), and node/edge **features** (`features/`). This separation matters: a graph edge states what the KG represents, while evidence records why that assertion is present and with what source context.

Useful questions include target–disease neighborhood inspection, provenance-aware hypothesis generation, representation retrieval, and leakage-controlled link prediction. None of these outputs independently proves causality, clinical efficacy, or mechanism.
"""),
            setup(),
            code("""
from manage_db.kg_schema import NODE_TYPES, RELATIONS
from manage_db.kg_evidence import EVIDENCE_PARQUET_COLUMNS
import pandas as pd

node_types = pd.DataFrame([{
    "node_type": key.value,
    "primary_ontology": value.primary_ontology,
    "example_id": value.example_id,
} for key, value in NODE_TYPES.items()])
relations = pd.DataFrame([{
    "relation": rel.name,
    "source_type": rel.source.value,
    "target_type": rel.target.value,
    "kind": rel.kind.value,
    "status": rel.status.value,
} for rel in RELATIONS])
print(f"Declared node types: {len(node_types)}; declared relations: {len(relations)}")
display(node_types.head(10))
display(relations.head(10))
"""),
            code("""
catalog = parquet_catalog(KG_ROOT, billing_project=BILLING_PROJECT)
display(catalog[["layer", "path", "rows", "row_groups"]])
print("Fixture rows are examples for executable documentation, not release cardinalities.")
"""),
            md("""
## Interpretation boundary

- Multiple source records can support one assertion; evidence count is not automatically evidence strength.
- Missing evidence in a bounded sample or currently partial LaminDB mirror does not prove absence from canonical Parquet.
- Provenance nodes and clinical-trial metadata are not default message-passing topology.
- Public embedding publication is separately gated by model identity, license, schema-compaction, and immutable-release checks.
"""),
        ],
    )
    write(
        "02_nodes_features_and_embeddings.ipynb",
        [
            md("""
# 02 — Explore entities, descriptions, sequences, and embeddings

Entity tables bind stable identifiers to cross-references and labels. Feature tables carry modality-specific data such as text, sequence, fingerprints, or embeddings. Modalities stay separate because sequence similarity, textual similarity, and chemical similarity answer different questions.
"""),
            setup(),
            code("""
root = str(KG_ROOT).rstrip("/")
gene_uri = f"{root}/nodes/gene.parquet"
genes = read_bounded_parquet(gene_uri, limit=10, billing_project=BILLING_PROJECT)
display(genes[[column for column in ["id", "gene_name", "name", "description", "source"] if column in genes]])
"""),
            code("""
feature_uri = f"{root}/features/gene_textual_summary.parquet"
features = read_bounded_parquet(feature_uri, limit=10, billing_project=BILLING_PROJECT)
display(features)
print("Canonical protein/transcript sequence tables can be sampled the same way; never call an unbounded full-table read from a laptop.")
"""),
            code("""
from manage_db.public_notebooks import nearest_embeddings

if MODE == "fixture":
    embedding_uri = Path(KG_ROOT) / "features" / "embeddings" / "text" / "fixture.parquet"
else:
    embedding_uri = os.environ.get("JOUVENCE_EMBEDDING_URI")
    if not embedding_uri:
        raise RuntimeError("Set JOUVENCE_EMBEDDING_URI to an accepted immutable public embedding shard; publication is not assumed.")
neighbors = nearest_embeddings(embedding_uri, "ENSG00000012048", limit=5, billing_project=BILLING_PROJECT)
display(neighbors)
"""),
            md("""
Cosine neighbors are candidates for inspection, not functional equivalence. Similarity depends on encoder, source text/sequence, preprocessing, and coverage. A learned fallback permits model execution but must not be described as source-derived biology.
"""),
        ],
    )
    write(
        "03_relations_evidence_and_questions.ipynb",
        [
            md("""
# 03 — Assertions, evidence, and a bounded biological question

We ask: **which diseases are connected to TP53 in this bounded graph, and what source records support each assertion?** DuckDB performs the join without loading a full KG into Python memory.
"""),
            setup(),
            code("""
root = str(KG_ROOT).rstrip("/")
edges = read_bounded_parquet(f"{root}/edges/disease_associated_gene.parquet", limit=20, billing_project=BILLING_PROJECT)
evidence = read_bounded_parquet(f"{root}/evidence/disease_associated_gene.parquet", limit=20, billing_project=BILLING_PROJECT)
display(edges)
display(evidence[["edge_key", "source", "source_dataset", "evidence_score", "predicate"]])
"""),
            code("""
from manage_db.public_notebooks import diseases_with_gene_evidence

if MODE != "fixture":
    print("The reusable DuckDB question helper currently requires local bounded Parquets. Stage only the three selected objects, then pass that local root.")
else:
    answer = diseases_with_gene_evidence(KG_ROOT, "ENSG00000141510", limit=20)
    display(answer)
"""),
            md("""
## What this means — and does not mean

The result shows represented associations and their attached provenance. Scores are source-specific and are not calibrated probabilities of causality. Association direction, tissue context, ancestry, assay type, and publication bias must be checked in evidence metadata before scientific interpretation. Do not infer treatment efficacy from a gene–disease neighborhood.
"""),
        ],
    )
    write(
        "04_lamindb_equivalent_queries.ipynb",
        [
            md("""
# 04 — Equivalent entity/relation lookup through LaminDB

LaminDB catalogs exact-ID registries and generic edge/evidence records in `jkobject/jouvencekb`. It is a query/catalog surface, not a replacement for canonical Parquet. Current ingestion is partial, so notebook output must not hide coverage gaps.
"""),
            setup(),
            code("""
from manage_db.public_notebooks import (
    LAMIN_INSTANCE,
    query_lamindb_edges,
    query_lamindb_evidence,
    query_lamindb_node,
)

print("Exact allowed instance:", LAMIN_INSTANCE)
LIVE_LAMIN = os.environ.get("JOUVENCE_LAMIN_LIVE", "0") == "1"
if LIVE_LAMIN:
    lamin_node = query_lamindb_node("gene", "ENSG00000141510", limit=5)
    lamin_rows = query_lamindb_edges(
        relation="disease_associated_gene",
        x_id="ENSG00000141510",
        limit=20,
    )
    lamin_evidence = query_lamindb_evidence(
        relation="disease_associated_gene",
        x_id="ENSG00000141510",
        limit=20,
    )
    display(lamin_node)
    display(lamin_rows)
    display(lamin_evidence)
else:
    print("Live Lamin query skipped. Set JOUVENCE_LAMIN_LIVE=1 only in an authenticated environment.")
"""),
            code("""
from manage_db.public_notebooks import diseases_with_gene_evidence

if MODE == "fixture":
    parquet_equivalent = diseases_with_gene_evidence(KG_ROOT, "ENSG00000141510", limit=20)
    display(parquet_equivalent)
print("An empty Lamin result can mean 'not ingested yet'; compare with canonical Parquet before concluding absence.")
"""),
            md("""
Lamin queries are bounded and read-only. The helper refuses any instance slug other than `jkobject/jouvencekb`. This protects against silently querying a similarly named or stale instance and preserves the current ingestion-incompleteness caveat.
"""),
        ],
    )
    write(
        "05_sampled_pyg_heterodata.ipynb",
        [
            md("""
# 05 — Build a meaningful sampled PyG `HeteroData`

This notebook delegates to the repository's tested `build_pyg_export` implementation. It preserves typed node maps, relation-specific edge indices, reverse-edge identity, feature coverage, and deterministic learned fallbacks. The fixture is intentionally tiny; production/full exports remain sidecar-first and worker-only.
"""),
            setup(pyg=True),
            code("""
from manage_db.public_notebooks import build_sampled_pyg

if MODE != "fixture":
    raise RuntimeError("Public notebook live mode requires an explicitly staged bounded local subset; never point a laptop build at the full KG.")
PYG_ROOT = CACHE / "pyg-sample"
result = build_sampled_pyg(KG_ROOT, PYG_ROOT, max_nodes_per_type=100, max_edges_per_relation=200)
print(result)
manifest = json.loads((PYG_ROOT / "manifest.json").read_text())
print({"node_counts": result.node_counts, "edge_counts": manifest["edge_counts"]})
"""),
            code("""
from manage_db.public_notebooks import load_sampled_pyg

data = load_sampled_pyg(PYG_ROOT)
print(data)
print("node feature shapes:", {node_type: tuple(data[node_type].x.shape) for node_type in data.node_types})
print("edge types:", data.edge_types)
metadata = json.loads((PYG_ROOT / "heterodata" / "full_graph.metadata.json").read_text())
display(metadata.get("node_embedding_policy", {}))
"""),
            md("""
The node maps define index↔biological-ID identity and must travel with tensors. Real vectors are used where joined; missing rows receive explicitly declared model-side learned fallbacks. A successful bounded build proves executability, not full-scale materialization, model quality, or biological validity.
"""),
        ],
    )
    write(
        "06_sampled_ml_use_cases.ipynb",
        [
            md("""
# 06 — Sampled link prediction, retrieval, and neighborhood analysis

Three realistic operations are demonstrated on a deterministic fixture: representation retrieval, relation-neighborhood inspection, and a tiny heterogeneous link-prediction smoke. The training result is a software smoke only.
"""),
            setup(pyg=True),
            code("""
from manage_db.public_notebooks import build_sampled_pyg, nearest_embeddings, run_sampled_ml

if MODE != "fixture":
    raise RuntimeError("Train only on an explicitly staged bounded subset with a reviewed leakage policy.")
embedding_uri = Path(KG_ROOT) / "features" / "embeddings" / "text" / "fixture.parquet"
display(nearest_embeddings(embedding_uri, "ENSG00000012048", limit=3))
"""),
            code("""
edge_uri = Path(KG_ROOT) / "edges" / "disease_associated_gene.parquet"
neighborhood = read_bounded_parquet(edge_uri, limit=100)
display(neighborhood.groupby("x_id").size().rename("sampled_degree").sort_values(ascending=False))
"""),
            code("""
PYG_ROOT = CACHE / "pyg-ml-sample"
build_sampled_pyg(KG_ROOT, PYG_ROOT, max_nodes_per_type=100, max_edges_per_relation=200)
smoke = run_sampled_ml(PYG_ROOT, seed=13)
print(json.dumps({
    "status": smoke["status"],
    "split_counts": smoke["split_counts"],
    "metrics": smoke["metrics"],
    "validation": smoke["validation"],
}, indent=2))
"""),
            md("""
## Leakage and validity checklist

- Split by biological entity/time/source when the task requires zero-shot or prospective evaluation; a random edge split can leak close duplicates and neighboring evidence.
- Mask treatment/trial outcome text for held-out `molecule_treats_disease` prediction.
- Do not encode labels, split membership, model predictions, or downstream target evidence into inputs.
- Negative samples are unknown/unobserved pairs, not proven biological negatives.
- Smoke loss/accuracy on this fixture is not a benchmark, efficacy estimate, or publication result.
"""),
        ],
    )
    print(f"wrote 6 legacy placeholder notebooks under {OUT}")


def main() -> None:
    """Generate the chaptered public course from deterministic source cells."""

    from scripts.public_notebook_course import course_notebooks

    OUT.mkdir(parents=True, exist_ok=True)
    notebooks = course_notebooks(md, code, setup)
    for path, cells in notebooks.items():
        write(path, cells)
    print(f"wrote {len(notebooks)} pedagogical notebooks under {OUT}")


if __name__ == "__main__":
    main()
