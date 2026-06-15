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
Evidence audit answers: "which canonical edges have support rows, and are any
support rows orphaned?"

As of 2026-06-15 after the remaining OpenTargets-backed `target_essentiality`
and `enhancer_to_gene` imports, the canonical export reports `15 / 15` node
files and `40 / 80` edge files: `55,365,186` nodes and `144,155,654` edges.
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

Current evidence status is tracked in `CLAUDE.md` and
`docs/evidence_and_edge_schema_plan.md`. As of the 2026-06-15 read-only audit,
canonical evidence exists for six relations
(`disease_associated_gene`, `disease_involves_pathway`,
`mutation_affects_molecule_response`, `mutation_associated_gene`,
`mutation_causes_protein_change`, and `molecule_targets_protein`) and targeted
`manage_db.audit_edge_evidence` reports zero unsupported/orphan records for all
six. The active evidence backlog starts with `mutation_associated_disease`, then
clinical `molecule_treats_disease` / `molecule_contraindicates_disease`, then
enhancer/expression/cell-line support tranches.

## Source policy for next gene-gene tranches

- `gene_ortholog_gene`: the only currently mapped non-GCS exporter is
  `manage_db.ingest_opentargets --datasets orthology`, which reads the
  OpenTargets `target.homologues` field exactly. It keeps only `ENSG` human
  query genes with high-confidence (`isHighConfidence` true/`1`) entries whose
  `homologyType` starts with `ortholog_`, writes endpoint Ensembl gene stubs
  needed for local validation, and rejects within-species/other paralogues.
  This is intentionally **not** in `ALL_DATASETS`; run against a temp root first:

  ```bash
  uv run python -m manage_db.ingest_opentargets \
    --data-dir /tmp/txgnn-orthology-smoke --datasets orthology --no-download
  uv run python -m manage_db.validate_kg /tmp/txgnn-orthology-smoke/kg \
    --threads 2 --duckdb-memory-limit 1GB \
    --duckdb-temp-dir /tmp/txgnn-orthology-smoke/duckdb-tmp
  ```

  Replace `/tmp/txgnn-orthology-smoke/opentargets/target` with a local or
  read-only copy of the OT `target` Parquet directory before running. Do not
  promote to canonical GCS until the parent has reviewed the non-human gene-node
  policy and LaminDB parity implications.
- `gene_coexpressed_gene`: no exact source mapping is selected yet. Do not infer
  coexpression from already-promoted tissue/cell-type expression edges or emit an
  empty placeholder. Pick an explicit coexpression network source (for example a
  GTEx/HPA correlation product with thresholding and tissue context policy), add
  tests on a temp root, then export.

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
