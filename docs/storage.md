# KG Parquet Storage

The TxGNN knowledge graph is normalised into a predictable Parquet layout that
works for both local disk and Google Cloud Storage. The canonical production
root is `gs://jouvencekb/kg/v2`.

## Layout

```
kg_root/
  nodes/{node_type}.parquet
  edges/{relation}.parquet
  metadata/
    provenance.json
    SUMMARY.md
```

Each node file stores the primary ontology ID (`id`) plus the xref columns
defined in `manage_db/kg_schema.py`. Edge files contain the canonical
relationship columns (`x_id`, `x_type`, `y_id`, `y_type`, `relation`,
`display_relation`, `source`, `credibility`) with optional metadata fields per
relation.

## Local vs GCS URIs

`manage_db.kg_storage.open_kg_root(uri)` accepts plain paths (`./data/kg/v2`) or
`gs://bucket/prefix` URIs. The storage layer uses `fsspec` under the hood, so
the same API works transparently against local directories, gcsfuse mounts, or
direct GCS access through ADC credentials. For production writes, use the
canonical root `gs://jouvencekb/kg/v2`.

## Atomic writes and append semantics

- Writes land in `<target>.tmp.<pid>` files and are renamed atomically once the
  Parquet writer succeeds. This keeps readers safe from partially written
  files, including on gcsfuse.
- `mode="append"` reads the existing file, concatenates, and rewrites it in a
  single atomic swap. Edge append operations deduplicate on
  (`x_id`, `y_id`, `relation`) using the credibility pipeline from
  `manage_db.credibility`.

## Adding a new node or edge type

1. Declare the schema in `manage_db/kg_schema.py` (update `NODE_TYPES` or
   `RELATIONS` as appropriate).
2. Emit rows from ingestion code and call `kg_storage.write_nodes` or
   `kg_storage.write_edges`; the storage layer enforces the schema and handles
   the I/O details.

## Provenance

`kg_storage.write_provenance` and `kg_storage.finalize_kg_export` maintain the
metadata directory. A typical `metadata/provenance.json` looks like:

```json
{
  "generated_at": "2026-06-03T17:42:00.123456+00:00",
  "code_sha": "3004725...",
  "code_version": "v0.2.0-dev",
  "sources": {
    "archived_local": {
      "version": "v0.2.0-dev",
      "uri": "./data/kg",
      "sha256": "…",
      "row_counts": {
        "nodes": {"gene": 100, "disease": 50},
        "edges": {"disease_associated_gene": 500}
      }
    }
  }
}
```

`SUMMARY.md` provides a human-readable summary of node/edge counts and total
storage size for quick inspections.
