# LaminDB KG artifact export/registry implementation report

Date: 2026-06-23
Task: `LAMIN-BUILD: implement idempotent KG export/registry into LaminDB`

## What was implemented

Phase-1 LaminDB KG registration is implemented as a manifest-driven artifact
catalog sync.  It follows `docs/lamindb_kg_export_design.md`: canonical Parquet
under `kg/v2` remains the source of truth; LaminDB stores discoverable Artifact,
Collection, ULabel, and Feature metadata for node, edge, evidence, and feature
files.  It does not rely on `.omoc` and does not require `lnschema_txgnn` for the
artifact catalog path.

New files:

- `manage_db/build_lamindb_kg_manifest.py`
  - scans `nodes/`, `edges/`, `evidence/`, and `features/` Parquet files;
  - reads Parquet footers for rows, columns, dtypes, row groups, schema hashes;
  - builds stable keys such as `kg/v2/nodes/gene.parquet`;
  - separates scan root from public canonical URI via `--public-root`, so a
    local/FUSE mirror can produce `gs://jouvencekb/kg/v2/...` Artifact URIs
    instead of causing LaminDB to upload local files;
  - emits deterministic labels such as `kg-layer:nodes`, `node_type:gene`,
    `relation:molecule_targets_gene`, and `feature`;
  - can optionally compute full content sha256 with `--hash-content`, but avoids
    full-file reads by default.
- `manage_db/sync_kg_artifacts_to_lamindb.py`
  - dry-run by default;
  - registers/updates LaminDB Artifacts by stable key in `--write` mode;
  - stores a metadata fingerprint in the Artifact description so unchanged files
    become no-ops on repeated syncs;
  - attaches ULabels, Feature records for table columns, and a `jouvence-kg/v2`
    Collection when the LaminDB API is available;
  - includes `--list-metadata` for a smoke-test discovery view over nodes, edges,
    evidence, and features.
- `tests/test_lamindb_kg_artifact_sync.py`
  - local mini-KG tests for all four layers;
  - dry-run credential-free sync smoke;
  - fake-Lamin idempotence tests for no-op and update behavior.

Existing exact-ID node registry sync remains in
`manage_db/sync_parquet_nodes_to_lamindb.py`.  Per the design, run it only after
`lnschema_txgnn` is activated/configured for `jkobject/jouvencekb`; this artifact
sync intentionally does not hack around inactive schema modules.

## Refresh commands

Dry-run against canonical FUSE path:

```bash
uv run python -m manage_db.sync_kg_artifacts_to_lamindb \
  --kg-root /mnt/gcs/jouvencekb/kg/v2 \
  --public-root gs://jouvencekb/kg/v2 \
  --manifest-output docs/lamindb_kg_v2_manifest.json \
  --report-output docs/lamindb_kg_v2_artifact_sync_report.json \
  --list-metadata
```

Write to the active LaminDB instance after reviewing the dry-run report:

```bash
export LAMIN_API_KEY="$(cat ~/.laminkey)"
uv run python -m manage_db.sync_kg_artifacts_to_lamindb \
  --manifest docs/lamindb_kg_v2_manifest.json \
  --report-output docs/lamindb_kg_v2_artifact_sync_report.write.json \
  --write
```

Optional exact content hashes for a smaller or mounted root:

```bash
uv run python -m manage_db.build_lamindb_kg_manifest \
  /mnt/gcs/jouvencekb/kg/v2 \
  --public-root gs://jouvencekb/kg/v2 \
  --output docs/lamindb_kg_v2_manifest.hashed.json \
  --hash-content
```

## Smoke validation

A user can list discovery metadata without credentials:

```bash
uv run python -m manage_db.sync_kg_artifacts_to_lamindb \
  --manifest docs/lamindb_kg_v2_manifest.json \
  --list-metadata
```

The printed discovery view is grouped by `nodes`, `edges`, `evidence`, and
`features`, with each item exposing `key`, `name`, `rows`, `uri`, and
`metadata_fingerprint`.  The write report has the same per-artifact keys plus
sync statuses: `would_create`, `created`, `noop`, `would_update`, `updated`, or
`error`.

## `lnschema_txgnn` status

This implementation does not require `lnschema_txgnn` activation for Artifact
registration.  If exact-ID registry writes are requested, first activate/configure
the schema module through the approved LaminDB admin path, then run the existing
node sync.  Do not direct-SQL insert into inactive `lnschema_txgnn_*` tables.

## Verification

Targeted tests run:

```text
uv run --group dev pytest tests/test_lamindb_kg_artifact_sync.py tests/test_audit_lamindb_parity.py tests/test_sync_parquet_nodes_to_lamindb.py -q
30 passed in 0.29s

uv run python -m py_compile manage_db/build_lamindb_kg_manifest.py manage_db/sync_kg_artifacts_to_lamindb.py
exit_code 0
```

Canonical FUSE dry-run with `--public-root gs://jouvencekb/kg/v2`:

```text
manifest_entries 79
counts_by_layer {'edges': 37, 'evidence': 15, 'features': 12, 'nodes': 15}
rows_by_layer {'edges': 94880924, 'evidence': 69693655, 'features': 808269, 'nodes': 55523691}
sync_summary {'created': 0, 'error': 0, 'noop': 0, 'updated': 0, 'would_create': 79, 'would_update': 0}
```

Live LaminDB write verification:

```text
first corrected full write: {'created': 19, 'error': 0, 'noop': 60, 'updated': 0, 'would_create': 0, 'would_update': 0}
second identical write:     {'created': 0, 'error': 0, 'noop': 79, 'updated': 0, 'would_create': 0, 'would_update': 0}
```
