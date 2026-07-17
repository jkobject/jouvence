# Part 2 non-ReMap canonical promotion: BioGRID physical PPI

Task: `t_17cfc462`  
Reviewer gate: `t_ce6e158c`  
Run: `part2_biogrid_ppi_promotion_20260622_234233`

## Scope promoted

Only the reviewer-approved BioGRID physical PPI tranche was promoted.

- Relation: `protein_interacts_protein`
- Edges: `gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet`
- Evidence: `gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet`
- Canonical staging prefix: `gs://jouvencekb/kg/v2/_promotion_staging/part2_biogrid_ppi_promotion_20260622_234233/`

Explicitly not promoted: ReMap `tf_binds_enhancer`, BioGRID PTM files, IntAct bounded sample, miRNA/lncRNA/protein_complex/PTM/paralog/pharmacology/context-only tranches, and all reviewer-deferred or feature-context-only artifacts.

## Pre-promotion state

`gsutil stat` immediately before write found both canonical destinations absent:

- `gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet`
- `gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet`

The source staged objects were copied locally and hashed before writing.

## Counts and validation

| Check | Expected | Observed |
|---|---:|---:|
| edge rows | 3,550 | 3,550 |
| evidence rows | 12,288 | 12,288 |
| duplicate active edges | 0 | 0 |
| edges without evidence | 0 | 0 |
| evidence assertions without edge | 0 | 0 |
| x endpoints missing canonical protein id/uniprot/name | 0 | 0 |
| y endpoints missing canonical protein id/uniprot/name | 0 | 0 |

Evidence class counts:

- `binary_physical`: 1615
- `biochemical_or_ptm_like_activity`: 372
- `complex_or_cofractionation_association`: 10301

Organism pair counts:

- `9606/9606`: 12288

`manage_db.audit_edge_evidence` on canonical readback returned `ok=true` with 3,550 edge rows, 12,288 evidence rows, 0 edges without evidence, and 0 evidence without edge.

## Readback / checksums

Canonical GCS objects were copied back after promotion. SHA256 matched the staged local hashes:

- edges: `f6025e952e5b08716c93abbb0abcef5bc249e6c4c58efc5ffeabf4a12b6610e3`
- evidence: `70f519999c16363b577dd3205297784a97a4996a7889f9ab34ba37055173859f`

GCS sizes after promotion:

```text
30420  2026-06-22T21:44:17Z  gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet
    895996  2026-06-22T21:44:18Z  gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet
TOTAL: 2 objects, 926416 bytes (904.7 KiB)
```

## Repo checks

- `uv run python -m py_compile manage_db/kg_schema.py manage_db/kg_evidence.py manage_db/backfill_edge_evidence.py manage_db/ingest_opentargets.py`: PASS
- `uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_kg_evidence.py tests/test_backfill_edge_evidence.py tests/test_biogrid_categorized_stage.py -q`: PASS (`33 passed in 0.41s`)
- Full `/mnt/gcs/jouvencekb/kg/v2` coverage audit: not run because `/mnt/gcs` is not mounted on this host; targeted GCS readback validations above were run instead.

## Rollback notes

If reviewer rejects this promotion, remove exactly these two canonical objects:

- `gs://jouvencekb/kg/v2/edges/protein_interacts_protein.parquet`
- `gs://jouvencekb/kg/v2/evidence/protein_interacts_protein.parquet`

The versioned staging copies remain at `gs://jouvencekb/kg/v2/_promotion_staging/part2_biogrid_ppi_promotion_20260622_234233/` for byte-for-byte inspection or restore. No ReMap paths were written.

Machine-readable manifest: `.omoc/reports/part2_biogrid_ppi_canonical_promotion_manifest.json`
