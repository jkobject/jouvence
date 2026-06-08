# KG Coverage Audit

Use this before claiming that `gs://jouvencekb/kg/v2` is complete.

```bash
uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2
uv run python -m manage_db.audit_kg_coverage gs://jouvencekb/kg/v2 --json
```

The audit compares physical `nodes/*.parquet` and `edges/*.parquet` files
against `manage_db/kg_schema.py`. It reports row counts from Parquet metadata,
so it is fast and does not read whole tables.

This is complementary to dangling-edge validation:

```bash
uv run python -m manage_db.validate_kg gs://jouvencekb/kg/v2
```

Coverage audit answers: "which schema files are physically missing?"
Validation answers: "do present edges resolve to present node IDs?"

As of 2026-06-08, the GCS export has `paper` files but the paper mention edges
are not graph-valid because OpenTargets uses `ENSG...`, `EFO_...`, and
`MONDO_...` identifiers that have not yet been merged into the exported
gene/disease node ID spaces.
