# Public Jouvence notebook execution report — t_3de2db50

Date: 2026-07-16

## Scope

Six output-free user notebooks, now located directly under `notebooks/` as the canonical numbered usage suite, were generated and executed independently in default fixture mode. The fixture exercises node, edge, evidence, feature, embedding, Lamin-equivalent, sampled PyG, retrieval, neighborhood, and link-prediction paths without canonical writes, live LaminDB writes, full-KG reads, or macOS GCS-FUSE.

## Execution evidence

Command:

```bash
uv sync --group dev --group notebooks --group gnn
uv run python scripts/build_public_notebooks.py
/usr/bin/time -l uv run python scripts/check_public_notebooks.py --execute
```

Result: PASS for all 6/6 notebooks. The checker verified the exact numbered suite, output-free committed cells, bounded/read-only notebook metadata, and forbidden path/project tokens. Executed copies were written only to a temporary directory.

Measured process evidence from the final full notebook execution:

- wall time: 9.07 s
- user time: 4.69 s
- system time: 1.09 s
- maximum resident set size: 448,102,400 bytes (427.34375 MiB)
- exit code: 0

Targeted tests:

```text
uv run pytest -q tests/test_public_notebooks.py tests/test_build_pyg_export.py tests/test_kg_queries.py
12 passed, 1 skipped in 2.27s
```

The skip is the existing opt-in live canonical integration test. The task-specific `tests/test_public_notebooks.py` result is 4/4 PASS with the GNN group installed.

## Full-suite baseline

`uv run pytest -q` does not collect cleanly on the prerequisite migration branch. Five pre-existing collection errors reference files absent from that branch (`stage_biogrid_categorized`, `ingest_literature`, `artifacts.scripts.stage_cell_type_responds_to_molecule_sciplex2`, and two legacy `.omoc/scripts` files). This notebook change does not add or mask those failures; targeted exporter/query/notebook tests pass.

## Limits and scientific interpretation

- Default execution uses deterministic illustrative fixtures, not release cardinalities or benchmark data.
- Live requester-pays reads require caller-provided `JOUVENCE_BILLING_PROJECT`; no personal billing project or credential is embedded.
- Live LaminDB access is opt-in, exact-slug constrained to `jkobject/jouvencekb`, read-only, and explicitly described as partial. Empty Lamin output is not treated as canonical absence.
- Public embedding publication is not assumed. Live embedding lookup requires an explicitly supplied accepted immutable shard URI because release identity/license/compaction gates remain pending.
- Sampled PyG and link-prediction runs prove executable contracts only. They do not prove full-KG materialization, model quality, causality, clinical efficacy, or prospective utility.
- The PR is stacked on the existing artifact-workspace migration branch because `origin/main` does not contain the tested `build_pyg_export`, `run_pyg_gnn_smoke`, or `kg_queries` prerequisites. It should merge only after or with the prerequisite migration PR.
