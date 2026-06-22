# Block 1 — `pathway_contains_gene` evidence backfill and protein split policy

_Date: 2026-06-21_

## Scope

This audit re-checks canonical `gs://jouvencekb/kg/v2/edges/pathway_contains_gene.parquet`, verifies whether `evidence/pathway_contains_gene.parquet` exists, enumerates current pathway membership sources/subdatabases, and decides whether any observed rows justify populating `pathway_contains_protein`.

Access used the A0 runbook default for this macOS worker: targeted `gcloud storage cp` into `.omoc/gcs-cache/kg-v2/`, then local DuckDB reads. The GCS FUSE mount was not required.

Cached files inspected:

- `.omoc/gcs-cache/kg-v2/edges/pathway_contains_gene.parquet`
- `.omoc/gcs-cache/kg-v2/nodes/pathway.parquet`

Attempted but absent:

- `gs://jouvencekb/kg/v2/evidence/pathway_contains_gene.parquet`

## Current edge file audit

### Schema

`edges/pathway_contains_gene.parquet` has 10 columns:

| Column | Type | Meaning |
| --- | --- | --- |
| `x_id` | varchar | pathway ID (`GO:*` or `R-HSA-*`) |
| `x_type` | varchar | always `pathway` in sampled/audited rows |
| `y_id` | varchar | gene ID (`ENSG*` or `NCBI:*`) |
| `y_type` | varchar | always `gene` |
| `relation` | varchar | `pathway_contains_gene` |
| `display_relation` | varchar | display label |
| `source` | varchar | `TxGNN` or `OpenTargets/GO` |
| `credibility` | bigint | source credibility score |
| `go_evidence` | varchar | GO evidence code for OpenTargets/GO rows; null for TxGNN rows |
| `go_aspect` | varchar | GO aspect for OpenTargets/GO rows; null for TxGNN rows |

### Total and source counts

| Source | Rows |
| --- | ---: |
| TxGNN | 340,383 |
| OpenTargets/GO | 290,549 |
| **Total** | **630,932** |

The file contains 630,932 distinct `(x_id, y_id, relation)` triples and 0 duplicate rows by that key.

### Endpoint namespaces

| x namespace | y type | y namespace | Rows |
| --- | --- | --- | ---: |
| GO | gene | NCBI Gene | 297,737 |
| GO | gene | Ensembl Gene | 290,549 |
| Reactome/R-HSA | gene | NCBI Gene | 42,646 |

By source:

| Source | x namespace | Rows |
| --- | --- | ---: |
| OpenTargets/GO | GO | 290,549 |
| TxGNN | GO | 297,737 |
| TxGNN | Reactome/R-HSA | 42,646 |

| Source | y namespace | Rows |
| --- | --- | ---: |
| OpenTargets/GO | Ensembl Gene | 290,549 |
| TxGNN | NCBI Gene | 340,383 |

Distinct pathway/gene counts:

| Source | x namespace | distinct pathways | distinct genes | Rows |
| --- | --- | ---: | ---: | ---: |
| OpenTargets/GO | GO | 17,743 | 21,130 | 290,549 |
| TxGNN | GO | 18,584 | 20,599 | 297,737 |
| TxGNN | Reactome/R-HSA | 2,020 | 10,849 | 42,646 |

All edge `x_id`s join to a row in `nodes/pathway.parquet`:

| edge namespace | edge rows | rows with pathway node |
| --- | ---: | ---: |
| GO | 588,286 | 588,286 |
| Reactome/R-HSA | 42,646 | 42,646 |

### Pathway node source composition

`nodes/pathway.parquet` contains these pathway source/prefix groups:

| Node source | ID namespace | Rows |
| --- | --- | ---: |
| GO | GO | 26,798 |
| OpenTargets | GO | 17,743 |
| OpenTargets/evidence | Reactome/R-HSA | 1,518 |
| REACTOME | Reactome/R-HSA | 2,516 |

Interpretation: the edge relation currently merges GO and Reactome-style pathway namespaces. OpenTargets/GO rows use GO terms and Ensembl targets; TxGNN inherited rows use GO and Reactome IDs with NCBI Gene endpoints.

### GO aspect counts

| `go_aspect` | Meaning | Rows |
| --- | --- | ---: |
| null | TxGNN inherited GO/Reactome rows without current GO aspect payload | 340,383 |
| P | biological process | 122,618 |
| C | cellular component | 92,373 |
| F | molecular function | 75,558 |

### GO evidence-code counts

These codes are present only on OpenTargets/GO rows. TxGNN rows have null `go_evidence`.

| `go_evidence` | Rows |
| --- | ---: |
| null | 340,383 |
| IEA | 101,006 |
| IDA | 52,599 |
| IBA | 39,438 |
| TAS | 23,534 |
| IPI | 18,713 |
| ISS | 17,384 |
| IMP | 16,860 |
| NAS | 10,143 |
| HDA | 5,907 |
| IGI | 1,081 |
| ISA | 973 |
| IC | 794 |
| IEP | 748 |
| HTP | 477 |
| EXP | 397 |
| ND | 200 |
| HMP | 115 |
| RCA | 107 |
| HEP | 42 |
| IKR | 17 |
| ISO | 12 |
| ISM | 2 |

OpenTargets/GO aspect × evidence counts:

| Aspect | Evidence | Rows |
| --- | --- | ---: |
| C | IEA | 38,364 |
| C | IDA | 19,591 |
| C | TAS | 11,529 |
| C | IBA | 11,438 |
| C | HDA | 4,659 |
| C | ISS | 3,150 |
| C | NAS | 1,621 |
| C | ISA | 645 |
| C | IMP | 482 |
| C | HTP | 477 |
| C | IC | 177 |
| C | IPI | 121 |
| C | ND | 52 |
| C | IGI | 31 |
| C | EXP | 25 |
| C | IEP | 5 |
| C | ISO | 3 |
| C | RCA | 2 |
| C | ISM | 1 |
| F | IEA | 25,134 |
| F | IPI | 18,490 |
| F | IDA | 11,841 |
| F | IBA | 10,042 |
| F | TAS | 3,207 |
| F | ISS | 2,132 |
| F | IMP | 1,341 |
| F | HDA | 1,198 |
| F | NAS | 1,120 |
| F | EXP | 344 |
| F | ISA | 326 |
| F | RCA | 105 |
| F | IC | 102 |
| F | ND | 78 |
| F | IGI | 72 |
| F | IKR | 16 |
| F | IEP | 7 |
| F | ISO | 3 |
| P | IEA | 37,508 |
| P | IDA | 21,167 |
| P | IBA | 17,958 |
| P | IMP | 15,037 |
| P | ISS | 12,102 |
| P | TAS | 8,798 |
| P | NAS | 7,402 |
| P | IGI | 978 |
| P | IEP | 736 |
| P | IC | 515 |
| P | HMP | 115 |
| P | IPI | 102 |
| P | ND | 70 |
| P | HDA | 50 |
| P | HEP | 42 |
| P | EXP | 28 |
| P | ISO | 6 |
| P | ISA | 2 |
| P | ISM | 1 |
| P | IKR | 1 |

### Credibility counts

| Source | Credibility | Rows |
| --- | ---: | ---: |
| OpenTargets/GO | 1 | 165,239 |
| OpenTargets/GO | 3 | 125,310 |
| TxGNN | 3 | 340,383 |

## Source database/subdatabase semantics

### OpenTargets/GO

Raw source layer:

- OpenTargets `go` dataset: GO term metadata; used for pathway nodes.
- OpenTargets `target` dataset: each ENSG target contains nested `go` annotations.

Current code path: `manage_db/ingest_opentargets.py::ingest_go` reads `opentargets_dir / "go"` and `opentargets_dir / "target"`. It emits `pathway_contains_gene` rows from target nested GO annotations:

- `x_id`: normalized GO CURIE from annotation `id`.
- `y_id`: ENSG target ID.
- `predicate` in the ingestion code: annotation `evidence`.
- `aspect` in the ingestion code: annotation `aspect`.
- Current canonical edge columns expose these as `go_evidence` and `go_aspect`.

Membership semantics:

- GO biological process (`P`) membership/annotation: pathway/process contains or annotates a gene target.
- GO molecular function (`F`) membership/annotation: function term annotates a gene/gene product target, but current endpoint is still gene (`ENSG`), not protein.
- GO cellular component (`C`) membership/annotation: component term annotates a gene/gene product target, but current endpoint is still gene (`ENSG`), not protein.

### TxGNN inherited GO rows

Raw source layer:

- Legacy TxGNN/PrimeKG-style relations mapped by `TXDATA_RELATION_MAP` in `manage_db/kg_schema.py`:
  - `bioprocess_protein` → `pathway_contains_gene`
  - `molfunc_protein` → `pathway_contains_gene`
  - `cellcomp_protein` → `pathway_contains_gene`
- These relations are flipped by `TXDATA_RELATION_FLIP` into pathway → gene direction.

Current canonical rows:

- 297,737 GO→NCBI Gene rows.
- `go_evidence` and `go_aspect` are null.
- Legacy naming says `*_protein`, but current canonical endpoint is NCBI Gene and the row does not provide a protein/isoform endpoint.

Membership semantics:

- Legacy GO annotation membership from PrimeKG/TxGNN, normalized to gene-level canonical rows.
- Aspect/subdatabase should be recovered from the original legacy relation label if raw input is available: `bioprocess`, `molfunc`, `cellcomp`.

### TxGNN inherited Reactome rows

Raw source layer:

- Legacy TxGNN/PrimeKG-style `pathway_protein` / `protein_pathway` relation maps to `pathway_contains_gene` and is flipped into pathway → gene direction.

Current canonical rows:

- 42,646 Reactome/R-HSA→NCBI Gene rows.
- `go_evidence` and `go_aspect` are null because these are not GO annotation rows.

Membership semantics:

- Reactome pathway membership involving a gene/gene-product participant in the legacy source.
- Current endpoint remains NCBI Gene; the current edge file does not preserve UniProt/ENSP protein endpoints or participant/entity IDs.

## Evidence file status

`gs://jouvencekb/kg/v2/evidence/pathway_contains_gene.parquet` is absent. The `gcloud storage cp` check returned:

```text
ERROR: (gcloud.storage.cp) The following URLs matched no objects or files:
gs://jouvencekb/kg/v2/evidence/pathway_contains_gene.parquet
```

So downstream consumers currently cannot reconstruct the original source membership record beyond the edge columns. This is especially problematic for TxGNN inherited rows because GO aspect/subdatabase and Reactome participant provenance are missing from the edge file.

## Proposed evidence schema

Use the canonical evidence schema in `manage_db/kg_evidence.py` and populate these fields for `evidence/pathway_contains_gene.parquet`:

| Evidence field | OpenTargets/GO | TxGNN GO inherited | TxGNN Reactome inherited |
| --- | --- | --- | --- |
| `edge_key` | auto: `pathway_contains_gene|{go_id}|{ensg}` | auto | auto |
| `relation` | `pathway_contains_gene` | `pathway_contains_gene` | `pathway_contains_gene` |
| `x_id`, `x_type` | GO ID, `pathway` | GO ID, `pathway` | R-HSA ID, `pathway` |
| `y_id`, `y_type` | ENSG, `gene` | NCBI Gene, `gene` | NCBI Gene, `gene` |
| `evidence_type` | `database_record` | `database_record` | `database_record` |
| `source` | `OpenTargets` | `TxGNN` or original `PrimeKG` if recoverable | `TxGNN` or original `PrimeKG`/`Reactome` if recoverable |
| `source_dataset` | `go` | `bioprocess`, `molfunc`, or `cellcomp` if recoverable; otherwise `txgnn_go` | `reactome` |
| `source_record_id` | stable composite from OpenTargets release, target ID, GO ID, evidence code, aspect, and row index if needed | stable composite from raw relation label, GO ID, NCBI Gene ID, and source row/index | stable composite from pathway ID, NCBI Gene ID, original participant/entity ID if available, and row/index |
| `paper_id` | empty unless source row carries literature | PMID if raw source has it; otherwise empty | PMID if raw Reactome/PrimeKG source has it; otherwise empty |
| `dataset_id` | optional source dataset artifact/release ID | optional source dataset artifact/release ID | optional source dataset artifact/release ID |
| `study_id` | empty | empty | empty |
| `evidence_score` | null unless source exposes a score | null unless source exposes a score | null unless source exposes a score |
| `predicate` | GO evidence code (`IEA`, `IDA`, etc.) | original GO aspect/subdatabase or evidence code if recoverable | `pathway_membership` or original relation label |
| `text_span` | JSON payload with `go_aspect`, original GO ID, target ID namespace, source row metadata | JSON payload with original legacy relation, source endpoint IDs/names | JSON payload with Reactome entity/participant IDs, names, original source endpoint IDs |
| `release` | OpenTargets release and/or GO release | TxGNN/PrimeKG release if known | Reactome/PrimeKG release if known |
| `license` | source license if tracked | source license if tracked | source license if tracked |
| `created_at` | build timestamp | build timestamp | build timestamp |

Important implementation note: `manage_db/backfill_edge_evidence.py::backfill_edge_evidence` currently creates coarse evidence rows from existing edge rows. For this relation that is not enough: it would not preserve OpenTargets GO evidence/aspect correctly unless `_edge_source_metadata` is extended for `pathway_contains_gene`, and it cannot recover TxGNN subdatabase/provenance without the raw legacy rows. Use a relation-specific backfill function or extend the generic helper with relation-specific extraction.

## Proposed builder inputs

### Required local/canonical inputs

1. Current canonical edges:
   - `gs://jouvencekb/kg/v2/edges/pathway_contains_gene.parquet`
2. Current pathway nodes for validation/names:
   - `gs://jouvencekb/kg/v2/nodes/pathway.parquet`
3. Current gene nodes for endpoint anti-join validation:
   - `gs://jouvencekb/kg/v2/nodes/gene.parquet`

### Required raw/source inputs

1. OpenTargets `target` dataset for the active KG release:
   - needed columns: `id`, nested `go` array containing GO `id`, `evidence`, `aspect`, and any source/release metadata present.
   - builder should reconstruct one evidence row for each OpenTargets/GO edge and compare count to 290,549.
2. OpenTargets `go` dataset for GO term metadata:
   - needed columns: GO term `id`, label/name, aspect if present.
   - use for source metadata and validation, not as the sole edge source.
3. Legacy TxGNN/PrimeKG raw edge table used to create inherited `TxGNN` rows:
   - required original relation labels: `bioprocess_protein`, `molfunc_protein`, `cellcomp_protein`, `pathway_protein`, `protein_pathway`.
   - required original endpoint IDs before canonical flipping/mapping.
   - optional but valuable: original names, source database, PMIDs, confidence/evidence fields.
4. Reactome source used by TxGNN/PrimeKG if available separately:
   - needed only if the legacy TxGNN raw table lacks Reactome participant/source record IDs.
   - must preserve Reactome release/version and participant/entity identifiers if used.

The repo contains mixed historical notes naming OpenTargets releases (`25.12` in an older setup notebook and `26.03` in Block 1 notes). The builder must not hard-code either; it should read the actual raw snapshot path/manifest used for the canonical v2 build and write that value to `release`.

## Backfill algorithm

1. Load current canonical `pathway_contains_gene` edges.
2. Build OpenTargets/GO evidence from raw OpenTargets `target.go` annotations:
   - normalize GO IDs exactly as `ingest_go` does;
   - keep ENSG target IDs as gene endpoints;
   - set `source=OpenTargets`, `source_dataset=go`;
   - set `predicate={go evidence code}` and include `go_aspect` in `text_span` or a future structured metadata column;
   - create a stable `source_record_id`, for example `OpenTargets/go:{release}:{target_id}:{go_id}:{evidence}:{aspect}:{row_number}` if no source-native row ID exists.
3. Build TxGNN GO evidence from the legacy raw relation rows:
   - map/flips should follow `TXDATA_RELATION_MAP` and `TXDATA_RELATION_FLIP`;
   - preserve original relation label in `source_dataset`/`predicate` (`bioprocess`, `molfunc`, `cellcomp`);
   - do not infer GO aspect from current edge IDs alone unless the raw relation is unavailable and the fallback is explicitly marked as such.
4. Build TxGNN Reactome evidence from legacy `pathway_protein` / `protein_pathway` rows:
   - preserve original relation label and any Reactome participant/entity/source record IDs;
   - canonical endpoint remains gene unless raw rows contain protein-native endpoint IDs and the split gates below are satisfied.
5. Write evidence to a staging KG root, not directly to canonical v2.
6. Run `manage_db.audit_edge_evidence` on `pathway_contains_gene`.
7. Verify evidence support covers all 630,932 current edges.
8. Only after review, promote `evidence/pathway_contains_gene.parquet` to the canonical KG.

Expected staged evidence count should be at least 630,932 database-record rows if built one support row per current edge. It may be greater if the raw sources contain multiple source records, PMIDs, or participant records for the same edge; in that case the edge-support audit should still show full edge coverage and evidence rows should deduplicate by canonical evidence keys.

## `pathway_contains_protein` decision

Decision for this audit: do not populate `pathway_contains_protein` from the current `pathway_contains_gene` edge file.

Reasons:

1. Every observed current edge has `y_type='gene'`; no current row has a protein endpoint.
2. Current `y_id` namespaces are only Ensembl Gene and NCBI Gene.
3. OpenTargets/GO target annotations are gene/target-level rows; GO molecular function (`go_aspect='F'`) does not make the canonical endpoint a protein.
4. TxGNN inherited relation names include `*_protein`, but the active KG schema deliberately maps those rows to `pathway_contains_gene`; the canonical source endpoint is NCBI Gene after migration.
5. The current edge file does not preserve raw UniProt/ENSP/isoform IDs, Reactome participant IDs, or protein-complex membership evidence.

A future `pathway_contains_protein` build is justified only if a source-native input directly provides pathway/complex → protein or pathway/complex → isoform membership. Acceptable sources could include Reactome participant/entity exports, protein complex databases, or another pathway source with UniProt/ENSP endpoints, but only if the raw source endpoint and assertion are protein-native.

## Promotion gates for any future `pathway_contains_protein`

Before any row is promoted to `pathway_contains_protein`:

1. Raw source rows must include protein/isoform endpoint identifiers (`UniProt`, `ENSP`, or equivalent protein-product IDs), not only NCBI/ENSG genes.
2. The biological assertion must be protein/isoform membership in a pathway, complex, reaction, or pathway entity; not merely a gene annotated to a GO term.
3. Endpoint normalization must document the mapping policy and reject ambiguous gene→protein projections.
4. Evidence rows must be materialized together with edges and include source database/subdatabase, release/version, source record ID, original protein endpoint ID, original pathway/entity ID, membership type, and PMID/publication if present.
5. Validate `x_id` against pathway nodes and `y_id` against protein nodes with anti-join checks.
6. Run edge/evidence support audit and update docs/source matrix/coverage with real counts.
7. Keep `pathway_contains_gene` rows intact unless there is an explicit deprecation/migration plan; protein-native membership is a sibling relation, not a replacement for gene-level membership.

## Verification commands used

```bash
mkdir -p .omoc/gcs-cache/kg-v2/{edges,evidence,nodes,raw}
gcloud storage cp \
  gs://jouvencekb/kg/v2/edges/pathway_contains_gene.parquet \
  .omoc/gcs-cache/kg-v2/edges/pathway_contains_gene.parquet
gcloud storage cp \
  gs://jouvencekb/kg/v2/nodes/pathway.parquet \
  .omoc/gcs-cache/kg-v2/nodes/pathway.parquet
# evidence copy intentionally failed because the object is absent:
gcloud storage cp \
  gs://jouvencekb/kg/v2/evidence/pathway_contains_gene.parquet \
  .omoc/gcs-cache/kg-v2/evidence/pathway_contains_gene.parquet

uv run --with duckdb python - <<'PY'
import duckdb
p = '.omoc/gcs-cache/kg-v2/edges/pathway_contains_gene.parquet'
con = duckdb.connect()
print(con.sql(f"select count(*) from read_parquet('{p}')").fetchone()[0])
print(con.sql(f"select source, count(*) n from read_parquet('{p}') group by 1 order by n desc").df())
print(con.sql(f"describe select * from read_parquet('{p}')").df())
PY
```

## Implementation result — 2026-06-21

Implemented relation-specific evidence backfill in `manage_db/backfill_edge_evidence.py` and staged the output at:

- `.omoc/gcs-cache/kg-v2/evidence/pathway_contains_gene.parquet`
- `.omoc/block1-build/pathway_contains_gene.evidence.parquet`

Staged counts:

| Source | Source dataset | Evidence type | Rows |
| --- | --- | --- | ---: |
| TxGNN | `txgnn_legacy_go` | `database_record` | 297,737 |
| OpenTargets | `go` | `database_record` | 290,549 |
| TxGNN | `txgnn_legacy_reactome` | `database_record` | 42,646 |
| **Total** |  |  | **630,932** |

Support/endpoint validation:

| Check | Result |
| --- | ---: |
| Edge rows | 630,932 |
| Evidence rows | 630,932 |
| Distinct supported edge keys | 630,932 |
| Edges without evidence | 0 |
| Evidence without edge | 0 |
| Missing pathway node endpoints | 0 |
| Missing gene node endpoints | 0 |
| Protein-like/non-gene current endpoints | 0 |

Evidence preserves `source`, source subdatabase, GO evidence code as `predicate`, GO aspect in `text_span`, original pathway/gene IDs, and stable source-record IDs. OpenTargets rows are built from the source-native GO annotation fields already present on canonical edges. TxGNN inherited rows are marked in `text_span` as `edge_derived_legacy_fallback=true` because the current canonical edge file does not preserve raw PrimeKG/TxGNN row IDs, PMIDs, or protein/Reactome participant IDs.

No `pathway_contains_protein` file was promoted: all current endpoints are gene IDs (`ENSG*` or `NCBI:*`), and the legacy `*_protein` wording is not sufficient to project gene endpoints to protein/isoform endpoints.

Validation commands run:

```bash
uv run --group dev pytest tests/test_backfill_edge_evidence.py -q
uv run python -m manage_db.backfill_edge_evidence .omoc/gcs-cache/kg-v2 pathway_contains_gene --json
uv run --with duckdb python - <<'PY'
# DuckDB edge/evidence support, endpoint anti-joins, and protein-like endpoint checks
PY
uv run python -m manage_db.audit_edge_evidence .omoc/gcs-cache/kg-v2 --relations pathway_contains_gene --json
```

## Bottom line

`pathway_contains_gene` is correctly broad and now has staged evidence coverage for all 630,932 current edges. Keep it gene-level. Do not split to `pathway_contains_protein` until a raw source provides protein/isoform-native pathway or complex membership with protein endpoints and evidence metadata.
