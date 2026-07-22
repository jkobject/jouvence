# Jouvence usage notebooks

This directory is the user-facing notebook entry point. It contains only notebooks that show how to inspect, query, and use Jouvence. Database construction and historical build/audit notebooks live in [`../reproduce/`](../reproduce/).

## Sequence

1. [`01_data_model_and_use_cases.ipynb`](01_data_model_and_use_cases.ipynb) — install the environment, understand ADC/IAM/requester-pays, then navigate nodes, assertions, evidence, features, metadata, and proof.
2. [`02_nodes_features_and_embeddings.ipynb`](02_nodes_features_and_embeddings.ipynb) — discover accepted immutable embedding releases, preserve vector/ID alignment, and inspect coverage, cosine similarity, and projections.
3. [`03_relations_evidence_and_questions.ipynb`](03_relations_evidence_and_questions.ipynb) — query relations with evidence, provenance, typed edge identity, and observed-versus-inferred boundaries.
4. [`04_lamindb_equivalent_queries.ipynb`](04_lamindb_equivalent_queries.ipynb) — compare canonical Parquet with exact-ID queries through the currently partial `jkobject/jouvencekb` LaminDB catalog.
5. [`05_sampled_pyg_heterodata.ipynb`](05_sampled_pyg_heterodata.ipynb) — build and inspect a bounded PyG `HeteroData`, node maps, edge indices, feature coverage, and fallback masks.
6. [`06_sampled_ml_use_cases.ipynb`](06_sampled_ml_use_cases.ipynb) — run deterministic retrieval, neighborhood, and link-prediction examples while auditing splits, negatives, metrics, and errors.

The numeric prefix is the canonical order. New user-facing notebooks must continue the sequence with a two-digit prefix.

## Safe execution

From the repository root:

```bash
uv sync --group dev --group notebooks --group gnn
uv run python scripts/build_public_notebooks.py
uv run python scripts/check_public_notebooks.py --execute
```

Each notebook uses the natural number of substantive cells needed for its topic,
organized as chapters, interpretations, and checkpoints. Cell counts are
descriptive telemetry, not a release gate: concise lessons must not be padded or
split artificially. Fixture mode is the default and performs no canonical write
or full-KG read. Live reads are opt-in and bounded; follow the access variables
documented in the repository [`README.md`](../README.md).
