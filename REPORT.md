# Paper Ingest Report

Verdict: FAIL_REAL

Reason: real download, ingest, and KG validation passed, but export to `gs://jouvencekb/kg/v2/` failed because this environment has no active Google Cloud credentials.

## Evidence

- Branch: `chore/paper-ingest`
- OpenTargets release: `24.09`
- Downloaded real data:
  - `data/opentargets/evidence_europepmc`: 200 Parquet files, 3.9G
  - `data/opentargets/target`: 37 Parquet files
  - `data/opentargets/disease`: 200 Parquet files
- Generated KG files:
  - `data/kg/nodes/paper.parquet`: 2,958,199 rows
  - `data/kg/edges/paper_mentions_gene.parquet`: 7,177,163 rows
  - `data/kg/edges/paper_mentions_disease.parquet`: 6,492,130 rows
  - `data/kg/nodes/gene.parquet`: 30,227 rows
  - `data/kg/nodes/disease.parquet`: 28,327 rows
  - `data/kg/edges/disease_subtype_of_disease.parquet`: 40,421 rows
- Validation command:
  - `/data/home/venvs/jouvencekb/bin/python -m manage_db.validate_kg data/kg/`
- Validation output:

```text
KG validation summary
  node_types: 3
  edge_types: 3
  total_nodes: 3016753
  total_edges: 13709714
  total_dangling_edges: 0

Dangling edges by relation

PASS: KG has no dangling edges
```

## Export Failure

Export command:

```text
gcloud storage rsync --recursive data/kg gs://jouvencekb/kg/v2/
```

Output:

```text
ERROR: (gcloud.storage.rsync) You do not currently have an active account selected.
Please run:

  $ gcloud auth login

to obtain new credentials.
```

Credential checks:

```text
gcloud auth list
# no active accounts

gsutil ls gs://jouvencekb/kg/v2/
ServiceException: 401 Anonymous caller does not have storage.objects.get access
```

## Code Fixes

- Added OpenTargets `output/etl/parquet` download support and aliases for `literature` -> `evidence/sourceId=europepmc`.
- Added resumable/retried per-file downloads.
- Added required nullable paper xref columns (`doi`, `pmc_id`, `arxiv_id`) in literature ingest.
- Added required nullable disease `hp_id` xref.
- Added literature-only gene stubs for ENSG IDs mentioned by Europe PMC but absent from the target node registry, preserving existing target metadata.
- Added a fast dedup path for single-source edge tables without evidence metadata.
- Added `python -m manage_db.validate_kg` CLI using `KGLoader`.

## Not Committed

- Downloaded OpenTargets Parquet data under `data/`.
- Generated KG Parquet files under `data/kg/`.
- Local logs under `.omx/logs/`.

## Test Notes

- `jouvencekb` venv does not include `pytest`; targeted pytest could not run there.
- `compileall` passed for changed Python files.
