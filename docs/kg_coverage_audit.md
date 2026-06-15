# KG Coverage Audit

Use this before claiming that `gs://jouvencekb/kg/v2` is complete.

```bash
uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2
uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2 --json
uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2 --fail-on-missing
```

The audit compares physical `nodes/*.parquet` and `edges/*.parquet` files
against `manage_db/kg_schema.py`. It reports row counts from Parquet metadata,
so it is fast and does not read whole tables.

By default, this command is informational and exits `0` even when schema files
are missing. Use `--fail-on-missing` only for strict completeness gates.

This is complementary to dangling-edge validation. Full canonical validation on
GCS/FUSE can be CPU-bound for a long time and `validate_kg` only prints the final
summary unless progress is requested, so long monitor/background runs should use
flushed heartbeats:

```bash
PYARROW_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  uv run python -m manage_db.validate_kg gs://jouvencekb/kg/v2 \
  --batch-size 250000 --progress-every-relations 1
```

Coverage audit answers: "which schema files are physically missing?"
Validation answers: "do present edges resolve to present node IDs?"

As of 2026-06-15 after the remaining OpenTargets-backed `target_essentiality`
and `enhancer_to_gene` imports, the canonical export reports `15 / 15` node
files and `40 / 77` edge files: `55,365,186` nodes and `144,155,654` edges.
The formerly missing node files (`cell_line`, `dataset`, `enhancer`) are now
present. The remaining missing edge files are schema/vision relations that still
need explicit source mapping; do not create empty placeholder Parquets for them.
Post-import coverage evidence is
`.omoc/reports/hermes-kg-coverage-post-remaining-20260615T000243Z.json`, and
new-slice endpoint validation evidence is
`.omoc/reports/hermes-remaining-slices-duckdb-fast-validation-clean-20260615T000434Z.json`.
Full generic `validate_kg` now uses DuckDB anti-joins relation-by-relation and
supports `--duckdb-memory-limit` plus `--duckdb-temp-dir`, so it can validate the
huge enhancer slice without materializing all node IDs in Python. The successful
2026-06-15 canonical run used:

```bash
uv run --no-sync python -m manage_db.validate_kg /mnt/gcs/jouvencekb/kg/v2 \
  --threads 2 --duckdb-memory-limit 4GB --duckdb-temp-dir .omoc/duckdb-tmp \
  --progress-every-relations 1
```

Evidence: `.omoc/reports/hermes-full-validate-duckdb-enhancer-20260615T084756Z.txt`.

## Node ontology namespace coverage

Use this companion audit to summarize physical node ID namespaces and populated
cross-reference columns:

```bash
uv run python -m manage_db.audit_node_ontology_coverage /mnt/gcs/jouvencekb/kg/v2
uv run python -m manage_db.audit_node_ontology_coverage /mnt/gcs/jouvencekb/kg/v2 --json
```

Dated reports from 2026-06-11 predate the remaining-slice promotion and are
historical. For current coverage, run the command above on
`/mnt/gcs/jouvencekb/kg/v2`; the canonical node files are now complete (`15 / 15`)
including `cell_line`, `dataset`, and `enhancer`. Disease and cell-type Parquets
use CURIE separators for selected ontology IDs (`EFO:...`, `MONDO:...`,
`CL:...`, etc.); the normalization pass collapsed `11,030` duplicate disease
rows created by prior mixed underscore/colon syntax. Targeted validation evidence
is stored at `.omoc/reports/canonical-targeted-validation-after-ontology-normalization.json`.
