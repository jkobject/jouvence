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

As of the latest full canonical cleanup report
`.omoc/reports/schema-direction-update-coverage-20260619.json`, the canonical
export reports `15 / 15` node files and `36 / 67` edge files: `55,523,691`
nodes and `94,877,374` edges.
The formerly missing node files (`cell_line`, `dataset`, `enhancer`) are now
present. The schema denominator in the latest full cleanup baseline is `67` edge
relations after source-native relation additions such as `molecule_targets_gene`,
`gene_interacts_gene`, and `cell_line_gene_essentiality`; future ingestion should
use measured gene endpoints instead of protein-named compatibility slots.
Coverage evidence: `.omoc/reports/schema-direction-update-coverage-20260619.json`.
The remaining missing edge files are schema/vision relations that still need
explicit source mapping; do not create empty placeholder Parquets for them.
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
That full run predates the 2026-06-16 additive tranches and reported
`144,155,654` edges. The new edge files were validated separately with
targeted anti-joins:

- Direct cell-type protein expression remains source-policy-gated. Do not promote
  RNA-expression-derived proxy rows into `cell_type_expresses_protein`; use only
  direct protein abundance/staining sources with explicit endpoint policy.
- `mutation_associated_phenotype`: `25,545` edges, zero dangling endpoints; its
  `26,980` evidence rows pass `manage_db.audit_edge_evidence` with zero
  unsupported/orphan support.
- `gene_ortholog_gene`: `161,675` edges, zero dangling endpoints; matching
  evidence rows pass `manage_db.audit_edge_evidence` with zero unsupported/orphan
  support.
- `cell_line_from_organism`: `1,183` edges, zero dangling endpoints; matching
  evidence rows pass `manage_db.audit_edge_evidence` with zero unsupported/orphan
  support.
- `cell_line_expresses_protein`: naive mRNA/gene-expression projection remains
  rejected. Promote this relation only from direct cell-line proteomics or other
  direct protein-measurement sources with evidence metadata.

Current evidence status is tracked in `AGENTS.md` and
`docs/evidence_and_edge_schema_plan.md`. Block 1 validation on 2026-06-22 is
recorded in `docs/block1_validation_report.md`. It validates the accessible
local cache `.omoc/gcs-cache/kg-v2`, not whole-KG coverage, because
`/mnt/gcs/jouvencekb/kg/v2` was unavailable in that worker session.

Block 1 evidence gate result:

- `pathway_contains_gene`: `630,932` edges / `630,932` evidence rows,
  `edges_without_evidence=0`, `evidence_without_edge=0`.
- `molecule_targets_gene`: `41,239` edges / `41,239` evidence rows,
  `edges_without_evidence=0`, `evidence_without_edge=0`; stale
  `molecule_targets_protein` evidence tokens are zero.
- `gene_interacts_gene`: `7,424,037` edges and `14,336,594`
  OpenTargets/interaction evidence rows. The `642,150` TxGNN legacy broad edges
  without evidence are an accepted policy exception, not a license to fabricate
  evidence or split current gene endpoints into protein/TF/transcript relations.

The active evidence backlog now starts with clinical
`molecule_treats_disease` / `molecule_contraindicates_disease`, remaining
direct protein-expression/context tranches, and future source-native mechanism
relations approved from raw endpoint-native sources.

## Source policy for next gene-gene tranches

- `gene_ortholog_gene`: promoted on 2026-06-16 from OpenTargets
  `target.homologues` high-confidence orthologs (`161,675` edges and matching
  evidence rows). The local build ran under systemd `MemoryMax=5G` with `1.7G`
  peak RSS; canonical promotion had zero dangling gene endpoints and backed up
  the previous `nodes/gene.parquet` under
  `/mnt/gcs/jouvencekb/kg/scratch/hermes-backups/20260616T133709Z-pre-orthology/`.
  Keep this exporter explicit-only (`--datasets orthology`), not in
  `ALL_DATASETS`, because it adds non-human Ensembl gene stubs.
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
