# LaminDB KG export / registry design

Date: 2026-06-23

Task: design the LaminDB representation for the Jouvence/TxGNN KG from canonical
`kg/v2` artifacts.

## Executive recommendation

Keep `gs://jouvencekb/kg/v2` (or the FUSE mirror at `/mnt/gcs/jouvencekb/kg/v2`)
as the source of truth for graph content. LaminDB should be the registry, catalog,
lineage, validation, and query-discovery layer, not the primary storage engine for
all node/edge/evidence rows.

Concretely:

1. Register every canonical Parquet layer as a versioned LaminDB `Artifact`:
   `nodes/*.parquet`, `edges/*.parquet`, `evidence/*.parquet`, `features/*.parquet`,
   plus `metadata/provenance.json` and generated manifest/stat files.
2. Use exact-ID registries for KG node identity:
   - `lnschema_txgnn.*` for TxGNN/Jouvence exact primary IDs where public
     `bionty`/`pertdb` writes are unsafe or unavailable.
   - `bionty` / `pertdb` as source-backed ontology/compound context, xrefs, and
     optional enrichments, not as the only parity target for exact KG IDs.
3. Do not create ORM records for every edge or every evidence row. At current KG
   scale (`~55.5M` documented nodes, `~94.9M` documented edges, plus tens of
   millions of evidence rows), per-edge SQL rows would be slower, harder to
   update idempotently, and less faithful to the canonical Parquet design.
4. Add a small custom registry surface for KG layers, relations, source datasets,
   versions, and validation manifests only if Lamin core `Artifact`, `Collection`,
   `Feature`, `ULabel`, `Run`, and `Transform` cannot express a query cleanly.
5. Revise and activate `lnschema_txgnn` in `jkobject/jouvencekb` before relying on
   ORM access to its registries. The live DB currently contains
   `lnschema_txgnn_*` tables, but the active instance is configured only with
   `bionty, pertdb`; importing `lnschema_txgnn` fails with
   `ModuleWasntConfigured`.

This gives an implementation card a bounded path: build a Parquet manifest and
Artifact registration sync first; then re-enable/fix `lnschema_txgnn` for exact-ID
node registries; only later add richer query/index sidecars for edge exploration.

## Observed current state

Read-only probes from this workspace show:

- Project boot context declares:
  - canonical KG root: `/mnt/gcs/jouvencekb/kg/v2` / `gs://jouvencekb/kg/v2`
  - active LaminDB instance: `jkobject/jouvencekb`
  - configured modules intended for current work: `bionty`, `pertdb`
- Python package imports:
  - `lamindb==2.2.1`: OK
  - `bionty==2.2.1`: OK
  - `pertdb==2.1.1`: OK
  - `lnschema_txgnn==0.1.0`: distribution installed, but import fails because it
    is not configured for the active instance.
- Active Lamin instance repr:
  - slug: `jkobject/jouvencekb`
  - storage: `gs://jouvencekb/lamin`
  - DB cache path: `~/Library/Caches/lamindb/jouvencekb/lamin/.lamindb/lamin.db`
  - modules: `bionty, pertdb`
- Django app registry contains only `lamindb`, `bionty`, `pertdb`.
- The DB still has orphaned/inactive `lnschema_txgnn_*` tables. Direct SQL counts
  at probe time:

| Table | Rows | Role |
| --- | ---: | --- |
| `lnschema_txgnn_gene` | 109,325 | exact Ensembl gene registry subset |
| `lnschema_txgnn_transcript` | 507,365 | exact ENST registry |
| `lnschema_txgnn_protein` | 233,995 | exact ENSP registry |
| `lnschema_txgnn_pathway` | 48,575 | exact Reactome/GO pathway registry |
| `lnschema_txgnn_molecule` | 31,007 | exact ChEMBL molecule registry |
| `lnschema_txgnn_mutation` | 2,589,508 | exact rsID/gnomAD-like mutation registry; one less than documented node rows, likely due to prior collision/reconciliation state |
| `lnschema_txgnn_disease` | 41,859 | exact normalized source ontology disease registry |
| `lnschema_txgnn_celltype` | 3,513 | exact CL registry |
| `lnschema_txgnn_tissue` | 16,061 | exact UBERON registry |
| `lnschema_txgnn_paper` | 4,205,891 | PubMed/literature registry; larger than current documented canonical `paper` node count due prior literature syncs |
| `lnschema_txgnn_dataset` | 0 | schema exists, not populated |
| `lnschema_txgnn_enhancer` | 0 | schema exists, not populated despite canonical enhancer nodes |

Important implication: implementation must not assume `import lnschema_txgnn as txs`
works until the instance settings include that module. Existing sync/audit code
currently imports it, so node parity sync is effectively blocked or must use a
controlled migration/reactivation step first.

The FUSE path and local `.omoc/gcs-cache/kg-v2` were not mounted in this run, so
this design uses counts documented in `AGENTS.md`, `docs/kg_schema_overview.md`,
and `docs/source_measure_edge_matrix.md`. Implementation should rerun coverage
against a mounted or complete mirror before writing final manifests.

## Design principles

1. Parquet remains canonical.
   - Canonical graph assertions live in `nodes/`, `edges/`, `evidence/`, and
     `features/` under `gs://jouvencekb/kg/v2`.
   - LaminDB records point to, validate, version, and label those files.
   - LaminDB must not silently mutate or rewrite canonical KG rows.

2. Exact KG IDs are first-class.
   - The KG's primary ID for each node type must be representable exactly.
   - Do not rely on public `bionty`/`pertdb` name/source resolution when it can
     alias or mutate records. This was already identified for `Gene`, `Molecule`,
     `Pathway`, `Tissue`, and `CellType`.

3. Edges are graph assertions; evidence is support metadata.
   - Edge rows stay deduplicated `(relation, x_id, y_id)` assertions with endpoint
     types and graph-level fields.
   - Evidence rows preserve source-specific predicate, score, study, paper,
     assay, release, and provenance.
   - LaminDB should register edge/evidence files and their schemas, not explode
     them into one SQL record per row.

4. Everything exported is reproducible and idempotent.
   - A repeated sync from unchanged `kg/v2` must be a no-op.
   - Changed files create new Artifact versions / replacement records with
     checksums and run lineage.
   - Node registry syncs use exact unique keys and bounded batches.

5. Query ergonomics should be layered.
   - Fast row-level analytics/query: DuckDB/Polars/PyArrow on Parquet.
   - Registry/search/catalog: LaminDB Artifacts, Features, ULabels, Collections,
     custom exact-ID node records.
   - Downstream model load: existing Parquet -> PyG/DGL export loaders.

## Canonical layer mapping

### 1. KG version / release

Represent each KG release as a LaminDB `Collection` plus a manifest artifact.

Recommended stable identifiers:

```text
collection key/name: jouvence-kg/v2
ulabels: kg, jouvence, txgnn, canonical, kg-v2
manifest artifact path: gs://jouvencekb/kg/v2/metadata/manifest.json
provenance artifact path: gs://jouvencekb/kg/v2/metadata/provenance.json
```

The manifest should contain at least:

```json
{
  "kg_version": "v2",
  "canonical_root": "gs://jouvencekb/kg/v2",
  "generated_at": "...",
  "code_sha": "...",
  "layers": [
    {
      "layer": "nodes",
      "name": "gene",
      "uri": "gs://jouvencekb/kg/v2/nodes/gene.parquet",
      "rows": 267830,
      "columns": ["id", "ncbi_gene_id", "hgnc_id", "uniprot_id", "gene_name"],
      "content_hash": "...",
      "parquet_schema_hash": "...",
      "row_group_count": 4
    }
  ]
}
```

Use this manifest as the idempotency driver rather than scanning the whole KG in
LaminDB on every run.

### 2. Node Parquets -> exact-ID registries + Artifact catalog

For every `nodes/{node_type}.parquet`:

- Register the file as a LaminDB `Artifact` with:
  - `key`: `kg/v2/nodes/{node_type}.parquet`
  - `description`: canonical node table for `{node_type}`
  - ULabels: `kg`, `kg-v2`, `node`, `node_type:{node_type}`, `canonical`
  - Feature/schema metadata: columns, dtypes, primary key `id`, xref columns
  - Run/Transform: `sync_kg_v2_to_lamindb`
- Ensure all node IDs are represented in an exact-ID registry:

| Node type | Canonical ID | Registry recommendation |
| --- | --- | --- |
| `gene` | ENSG | `lnschema_txgnn.Gene.ensembl_gene_id`; link/enrich from `bionty.Gene` only when exact source-backed mapping exists |
| `transcript` | ENST | `lnschema_txgnn.Transcript.ensembl_transcript_id` |
| `protein` | ENSP | `lnschema_txgnn.Protein.ensembl_protein_id`; UniProt is xref, not primary |
| `disease` | normalized source ontology ID, e.g. `EFO:...`, `MONDO:...` | `lnschema_txgnn.Disease.ontology_id`; do not force non-MONDO IDs into MONDO-backed `bionty.Disease` |
| `molecule` | ChEMBL | `lnschema_txgnn.Molecule.chembl_id`; `pertdb.Compound` optional enrichment only |
| `pathway` | Reactome/GO | `lnschema_txgnn.Pathway.ontology_id` |
| `tissue` | UBERON | `lnschema_txgnn.Tissue.ontology_id` |
| `cell_type` | CL | `lnschema_txgnn.CellType.ontology_id` |
| `phenotype` | HP | `bionty.Phenotype` can be used if exact ontology IDs are source-backed; add custom `lnschema_txgnn.Phenotype` only if parity fails or public writes are unsafe |
| `cell_line` | Cellosaurus | `bionty.CellLine` if exact source-backed; add custom registry only if parity fails |
| `organism` | NCBI Taxonomy | `bionty.Organism` is sufficient for `NCBITaxon:9606` |
| `paper` | PMID | `lnschema_txgnn.Paper.pmid` |
| `mutation` | rsID or gnomAD-like variant ID | `lnschema_txgnn.Mutation` keyed by `rsid` or `gnomad_id`, with collision reconciliation |
| `dataset` | DOI/UUID/source key | `lnschema_txgnn.Dataset` or LaminDB `Artifact`/`Collection`/`Reference` depending on whether it is a source dataset entity or a stored file |
| `enhancer` | ENCODE/rE2G interval ID | `lnschema_txgnn.Enhancer.encode_id` or `ensembl_regulatory_id`; needs population strategy for ~48.8M rows |

Do not block Artifact registration if a node registry is temporarily unavailable.
Instead record parity status per node type in the manifest:

```json
{
  "node_type": "protein",
  "artifact_registered": true,
  "registry": "lnschema_txgnn.Protein",
  "registry_status": "schema_module_not_configured",
  "parquet_unique_ids": 233995,
  "matched_ids": null,
  "missing_ids": null
}
```

This preserves catalog usefulness while making registry gaps explicit.

### 3. Edge Parquets -> Artifact catalog + relation registry

For every `edges/{relation}.parquet`:

- Register the Parquet file as an Artifact.
- Label it with:
  - `kg`, `kg-v2`, `edge`, `relation:{relation}`, `x_type:{x_type}`, `y_type:{y_type}`,
    `kind:{kind}`, `direct:{yes|no|maybe}`, `canonical`
- Attach schema/features for standard columns:
  - `x_id`, `x_type`, `y_id`, `y_type`, `relation`, `display_relation`, `source`,
    `credibility`, plus relation-specific metadata columns.
- Store row count, byte size, row-group count, endpoint anti-join validation status,
  and evidence support status in the manifest or a small custom `KGRelation` /
  `KGLayer` record.

Minimal custom relation record if needed:

```python
class KGRelation(ln.Record):
    relation: str              # molecule_targets_gene
    x_type: str                # molecule
    y_type: str                # gene
    kind: str                  # pharmacological
    direct: str                # no / maybe / yes
    canonical: bool
    edge_artifact: ln.Artifact
    evidence_artifact: ln.Artifact | None
    edge_rows: int
    evidence_rows: int | None
    endpoint_validation_status: str
    evidence_support_status: str
```

This table should have one record per relation per KG version, not one record per
edge row.

### 4. Evidence Parquets -> Artifact catalog + support metadata

For every `evidence/{relation}.parquet`:

- Register as an Artifact.
- Link it to the corresponding edge relation record/artifact.
- Label with `evidence`, `relation:{relation}`, source datasets found in the file,
  and `canonical`.
- Preserve source-specific columns in Parquet, not as fixed Lamin fields.

Minimum expected evidence columns:

```text
edge_key, relation, x_id, x_type, y_id, y_type,
evidence_type, source, source_dataset, source_record_id,
paper_id, dataset_id, study_id, evidence_score,
effect_size, p_value, predicate, text_span, provenance fields...
```

Expected API example:

```python
# Discover canonical evidence artifact for a relation
artifact = ln.Artifact.get(key="kg/v2/evidence/molecule_targets_gene.parquet")
path = artifact.path

# Query rows with DuckDB/Polars rather than ORM-expanding all evidence rows
import duckdb
rows = duckdb.sql(f"""
    select x_id, y_id, source_dataset, predicate, evidence_score
    from read_parquet('{path}')
    where x_id = 'CHEMBL941'
    limit 20
""").df()
```

### 5. Feature Parquets -> Artifact catalog + typed feature schemas

For every `features/{feature_table}.parquet`:

- Register as an Artifact.
- Label with `feature`, `node_type:{node_type}`, `feature_family:{sequence|text|fingerprint|context|...}`.
- Attach LaminDB `Feature` records for columns that matter for search/filtering:
  `node_id`, `node_type`, `feature_name`, `source`, `source_dataset`, `release`,
  and feature-specific metadata.
- Keep dense vectors, long sequences, textual summaries, fingerprints, and large
  context matrices in Parquet.

Examples from current docs include official feature tables for node sequence,
textual summaries, and molecule fingerprints. Lamin should answer “which feature
artifacts exist for protein text summaries?” and then hand the Parquet path to
DuckDB/Polars/PyArrow for row access.

### 6. Source datasets and versions

Source datasets should have a small registry because they are reused across node,
edge, evidence, and feature artifacts.

Minimal schema:

```python
class KGSourceDataset(ln.Record):
    source: str              # OpenTargets, HPA, TxGNN, ENCODE, Reactome, ...
    source_dataset: str      # interaction, go, drug_mechanism_of_action, ...
    release: str | None      # e.g. 26.03
    uri: str | None
    license: str | None
    snapshot_artifact: ln.Artifact | None
    canonical: bool
```

If avoiding new custom records in phase 1, represent these as `ULabel`s and
`Artifact` metadata, then add `KGSourceDataset` once query needs justify it.

## `lnschema_txgnn` decision

Recommendation: revise lightly and activate/configure `lnschema_txgnn`; do not
abandon it, and do not replace it with direct writes to public `bionty`/`pertdb`
registries.

Rationale:

- The exact-ID node registry problem is real and already solved conceptually by
  custom TxGNN registries.
- Public registry writes can resolve by symbols/names and mutate source-backed
  rows, which is unsafe for KG parity.
- Current direct SQL counts show the custom tables already contain most exact-ID
  records, so abandoning them would strand useful state.
- The problem is configuration/activation and schema hygiene, not the concept of
  `lnschema_txgnn`.

Required changes before implementation relies on it:

1. Add `lnschema_txgnn` to the active instance settings/modules for
   `jkobject/jouvencekb` through the approved LaminDB admin path.
2. Verify import:

```python
import lamindb as ln
import lnschema_txgnn as txs
assert ln.setup.settings.instance.slug == "jkobject/jouvencekb"
```

3. Run read-only model/table checks:

```python
for model in [txs.Gene, txs.Molecule, txs.Pathway, txs.Tissue, txs.CellType,
              txs.Disease, txs.Protein, txs.Transcript, txs.Mutation, txs.Paper,
              txs.Dataset, txs.Enhancer]:
    print(model.__name__, model.objects.count())
```

4. Reconcile model definitions against current DB columns. At probe time the DB
   tables include useful fields such as:
   - `Gene`: `ensembl_gene_id`, `symbol`, `name`, `ncbi_gene_id`, `hgnc_id`,
     `uniprot_id`
   - `Protein`: `ensembl_protein_id`, `ensembl_gene_id`, `uniprot_id`,
     `refseq_protein`, `pdb_ids`
   - `Disease`: `ontology_id`, `source_ontology`, `name`, `mondo_id`, `omim_id`,
     `doid_id`, `icd10_code`, `mesh_id`, `hp_id`
   - `Mutation`: `rsid`, `hgvs`, `clinvar_id`, `gnomad_id`, genomic fields
   - `Enhancer` and `Dataset`: tables exist but are not populated.
5. Add only small catalog records (`KGRelation`, `KGSourceDataset`, optional
   `KGLayer`) if core Lamin objects are insufficient.
6. Do not add `KGEdge` / `KGEvidence` row-level registries for all graph rows.

Phase-1 fallback if module activation cannot happen immediately:

- Register Artifacts, Collections, ULabels, Features, and manifest records using
  only configured `lamindb`, `bionty`, `pertdb`.
- Mark exact-ID node parity as `schema_module_not_configured`.
- Do not attempt direct SQL writes to inactive `lnschema_txgnn_*` tables except as
  a deliberate migration with backups and human approval.

## Idempotent export/update semantics

### Stable keys

Use deterministic keys for all Lamin artifacts and labels:

```text
kg/v2/nodes/{node_type}.parquet
kg/v2/edges/{relation}.parquet
kg/v2/evidence/{relation}.parquet
kg/v2/features/{feature_table}.parquet
kg/v2/metadata/manifest.json
kg/v2/metadata/provenance.json
kg/v2/reports/{report_name}.json
```

For a future immutable release snapshot, use:

```text
kg/releases/{release_id}/...
```

where `release_id` can be date + content hash, e.g.
`2026-06-23T1500Z-<manifest_hash>`.

### Manifest-driven sync algorithm

1. Open canonical root with `manage_db.kg_storage.open_kg_root("gs://jouvencekb/kg/v2")`
   or the FUSE path.
2. Build a manifest with layer, name, URI, row count, byte size, Parquet schema,
   row group count, content hash or GCS generation/etag, and selected validation
   statuses.
3. Register/update the manifest artifact first in dry-run mode.
4. For each layer entry:
   - Look up an existing Lamin `Artifact` by stable key and stored hash/generation.
   - If unchanged: leave as-is and record `status=noop`.
   - If changed: register a new artifact version or update metadata according to
     LaminDB's supported versioning semantics; never overwrite canonical GCS data.
   - Attach ULabels/features/collection membership idempotently.
5. For node registries:
   - Batch-read only columns needed for that node type.
   - Build exact registry specs using existing `sync_parquet_nodes_to_lamindb`
     logic.
   - Lookup existing keys in chunks.
   - Bulk-create only missing exact keys.
   - Reconcile known mutation rsID/gnomAD collisions.
   - Emit parity report.
6. Save a run report artifact:

```json
{
  "kg_version": "v2",
  "dry_run": false,
  "artifacts": {"created": 0, "updated": 3, "noop": 142},
  "registries": {
    "protein": {"seen": 233995, "existing": 233995, "created": 0, "missing_after": 0}
  },
  "errors": []
}
```

### Deletion semantics

Do not delete Lamin records just because a row disappears from `kg/v2`.
Instead:

- Mark old artifacts as superseded by manifest version.
- For registry records, keep historical exact-ID records unless a deliberate
  cleanup migration is approved. KG membership is determined by the current node
  Artifact/manifest, not by deleting registry rows.

### Concurrency / locking

- Use dry-run by default; require `--write` for registry writes.
- Configure SQLite busy timeout as existing sync code does.
- Run one registry writer at a time for `jkobject/jouvencekb`.
- Prefer small transactions/bulk batches to avoid long DB locks.

## Data-volume and indexing strategy

Documented current KG baseline:

- nodes: `55,523,691`
- edges: `94,877,374`
- node files: `15 / 15`
- edge files documented/active: up to `67` schema relations, with `36` accessible
  in a partial validation cache.
- largest current node family: `enhancer`, documented at `48,808,144` rows.
- largest edge families include:
  - `enhancer_regulates_gene`: `48,808,144`
  - `cell_line_expresses_gene`: `20,928,056`
  - `gene_interacts_gene`: `7,424,037`
  - `tissue_expresses_gene`: `5,338,736`
  - `mutation_associated_disease`: `4,656,171`
  - `molecule_synergizes_molecule`: `2,672,628`

Implications:

1. SQL ORM is appropriate for node registries up to a few million rows only if
   writes are batched and indexed by exact key. It is not appropriate for 95M
   edges + evidence rows.
2. Parquet row groups should target ~256MB as already implemented in
   `manage_db.kg_storage`.
3. For very large relation/feature files, consider partitioned Parquet directories
   in a future `kg/v3` or `kg/v2/indexes` sidecar, but do not change canonical
   `kg/v2` layout in this design task.
4. Build optional query sidecars rather than expanding all rows into LaminDB:

```text
indexes/relations/{relation}/by_x_type_x_id.duckdb
indexes/relations/{relation}/stats.parquet
indexes/entities/{node_type}/degree_stats.parquet
```

5. Recommended chunk sizes for implementation:
   - node Parquet read batches: `50_000` rows (existing default)
   - registry lookup chunks: `5_000` keys (existing default)
   - custom registry bulk_create: `1_000` rows (existing default)
   - large enhancer registry: consider `100_000` read batches with `1_000-5_000`
     bulk writes only after testing DB lock behavior.
6. Register Artifacts by metadata without reading entire files into memory. Use
   Parquet metadata for row counts/schema and GCS generation/hash where possible.

## Minimal schema examples

### Lamin core objects

```python
# Collection for the KG release
kg = ln.Collection(name="jouvence-kg/v2", description="Canonical Jouvence/TxGNN KG v2")
kg.save()

# Stable labels
canonical = ln.ULabel(name="canonical").save()
node_label = ln.ULabel(name="kg-layer:nodes").save()
gene_label = ln.ULabel(name="node_type:gene").save()

# Artifact for nodes/gene.parquet
artifact = ln.Artifact(
    "gs://jouvencekb/kg/v2/nodes/gene.parquet",
    key="kg/v2/nodes/gene.parquet",
    description="Canonical KG v2 gene node table keyed by Ensembl gene ID",
)
artifact.save()
artifact.ulabels.add(canonical, node_label, gene_label)
kg.artifacts.add(artifact)
```

Exact API names may need adjustment to the installed LaminDB 2.2.1 API, but the
semantic objects should remain the same.

### Custom exact-ID node records

```python
class Gene(ln.Record):
    ensembl_gene_id: str  # unique, exact KG primary ID
    symbol: str | None
    name: str | None
    ncbi_gene_id: str | None
    hgnc_id: str | None
    uniprot_id: str | None

class Protein(ln.Record):
    ensembl_protein_id: str  # unique, exact ENSP primary ID
    ensembl_gene_id: str | None
    uniprot_id: str | None
    refseq_protein: str | None
    pdb_ids: str | None

class Disease(ln.Record):
    ontology_id: str         # unique, normalized EFO/MONDO/HP/etc. source ID
    source_ontology: str | None
    name: str | None
    mondo_id: str | None
    hp_id: str | None
```

### Custom layer/relation records if needed

```python
class KGLayer(ln.Record):
    kg_version: str           # v2
    layer: str                # nodes / edges / evidence / features
    name: str                 # gene / molecule_targets_gene / ...
    artifact: ln.Artifact
    rows: int
    bytes: int
    content_hash: str
    schema_hash: str
    validation_status: str

class KGRelation(ln.Record):
    kg_version: str
    relation: str
    x_type: str
    y_type: str
    kind: str
    direct: str
    edge_artifact: ln.Artifact
    evidence_artifact: ln.Artifact | None
    edge_rows: int
    evidence_rows: int | None
```

These should be small summary registries; not row-level graph storage.

## Expected API/query examples

### Find all canonical artifacts for a relation

```python
import lamindb as ln

edge = ln.Artifact.get(key="kg/v2/edges/molecule_targets_gene.parquet")
evidence = ln.Artifact.get(key="kg/v2/evidence/molecule_targets_gene.parquet")
print(edge.path, evidence.path)
```

### Check exact node registry parity

```python
import lnschema_txgnn as txs

txs.Protein.objects.filter(ensembl_protein_id="ENSP00000369497").exists()
txs.Molecule.objects.filter(chembl_id="CHEMBL941").exists()
txs.Disease.objects.filter(ontology_id="EFO:0000305").exists()
```

### Query an edge file by entity

```python
import duckdb
import lamindb as ln

edge_artifact = ln.Artifact.get(key="kg/v2/edges/molecule_targets_gene.parquet")
rows = duckdb.sql(f"""
    select x_id, y_id, relation, source, credibility
    from read_parquet('{edge_artifact.path}')
    where x_id = 'CHEMBL941'
    limit 50
""").df()
```

### Discover feature tables for protein text

```python
import lamindb as ln

# Exact call may vary by Lamin API; semantic target is artifact filtering by labels/key.
protein_text_features = ln.Artifact.filter(
    key__contains="kg/v2/features/protein",
).all()
```

### Build a PyG export from registered artifacts

```python
from txgnn import KGLoader

kg_root = "gs://jouvencekb/kg/v2"  # still canonical root
kg = KGLoader(data_dir=kg_root)
hetero_data = kg.to_pyg()
```

LaminDB should make the root and version discoverable; `KGLoader` should still
load canonical Parquet.

## Implementation plan for the next card

1. Add `manage_db/build_lamindb_kg_manifest.py`.
   - Inputs: KG root, output path, optional `--hash-content`.
   - Outputs: `metadata/lamindb_manifest.json` or report path under `.omoc/reports`.
   - Uses Parquet metadata and GCS/file metadata; no full table materialization.

2. Add `manage_db/sync_kg_artifacts_to_lamindb.py`.
   - Dry-run default.
   - Registers/updates Artifacts, Collection, ULabels, Features, and run report.
   - Does not require `lnschema_txgnn` for phase-1 artifact catalog.

3. Add `manage_db/audit_lnschema_txgnn_activation.py`.
   - Verifies active modules include `lnschema_txgnn`.
   - Imports expected models.
   - Compares model fields against current `lnschema_txgnn_*` table columns.
   - Reports inactive/orphaned table state clearly.

4. After human/admin activation of `lnschema_txgnn`, update/reuse
   `manage_db/sync_parquet_nodes_to_lamindb.py`.
   - Add `dataset` and `enhancer` support, or explicitly mark them deferred.
   - Add `phenotype`/`cell_line` parity decision if public registries fail exact
     KG ID checks.
   - Run dry-run then write per node family.

5. Add parity and artifact tests.
   - Unit-test stable keys, labels, manifest hash behavior, and dry-run no-op.
   - Integration smoke with a tiny local KG root.
   - Live read-only smoke against `jkobject/jouvencekb` when credentials exist.

6. Produce implementation run reports:
   - `docs/lamindb_kg_export_implementation_report.md`
   - `.omoc/reports/lamindb-kg-v2-artifact-sync-*.json`
   - `.omoc/reports/lamindb-kg-v2-node-parity-*.json`

## Risks and open decisions for Jérémie

1. Instance module activation.
   - Current state has inactive `lnschema_txgnn_*` tables but active modules only
     `bionty, pertdb`.
   - Decision needed: approve/admin-enable `lnschema_txgnn` for
     `jkobject/jouvencekb`, or keep it intentionally disabled and accept
     artifact-only cataloging until a schema migration is reviewed.

2. Orphaned table reconciliation.
   - Tables contain useful records but ORM is inactive.
   - Before activation, verify installed `lnschema_txgnn==0.1.0` model definitions
     match DB columns and migrations. If not, write a migration rather than
     forcing import.

3. Enhancer registry scale.
   - `enhancer` has ~48.8M documented rows and currently `0` custom registry rows.
   - Full exact-ID enhancer ORM registry may be expensive and not necessary for
     first-class Artifact cataloging.
   - Recommendation: phase 1 registers enhancer node Artifact and relation files;
     defer full enhancer registry unless exact-ID lookup by enhancer in Lamin is
     a real product requirement.

4. Dataset registry semantics.
   - `lnschema_txgnn_dataset` exists with `0` rows.
   - Decide whether `dataset` nodes are biological KG nodes, source datasets,
     Lamin Artifacts/Collections, or both. Recommendation: use source dataset
     records for provenance and reserve KG `dataset` nodes for graph assertions.

5. Mutation count discrepancy.
   - Direct SQL shows `2,589,508` custom mutation rows vs documented canonical
     `2,589,509` mutation node rows. This may reflect prior rsID/gnomAD collision
     reconciliation or stale docs.
   - Implementation should rerun `audit_lamindb_parity` after module activation
     and report exact missing IDs.

6. Paper registry scope.
   - Direct SQL shows `4,205,891` paper records, while current schema overview
     documents `2,958,199` canonical paper nodes and older blocker notes mention
     larger retired literature syncs.
   - Treat current KG membership as manifest-driven; do not infer current paper
     node membership from registry count alone.

7. Public registry use.
   - `bionty`/`pertdb` are valuable for ontology context, but previous work found
     unsafe write behavior for exact KG parity.
   - Keep custom exact-ID TxGNN records as the authoritative KG parity surface.

8. Query index format.
   - Need a product decision later on whether DuckDB sidecars, partitioned
     Parquet, or a small service API is the preferred interactive relation query
     layer. LaminDB alone should not be used as a 100M-edge query engine.

## Acceptance-criteria checklist

- Concrete recommendation for implementation: yes; phase-1 Artifact catalog sync,
  `lnschema_txgnn` activation audit, then exact-ID node registry sync.
- Canonical source of truth preserved: yes; `gs://jouvencekb/kg/v2` remains
  canonical, LaminDB is registry/query/catalog/lineage.
- Parquet layers mapped: nodes, edges, evidence, features, source datasets,
  versions, artifact lineage.
- `lnschema_txgnn` decision: revise/activate for exact-ID nodes and small summary
  records; do not use it for row-level edges/evidence.
- Minimal schema examples included: yes.
- Expected API/query examples included: yes.
- Data-volume and chunking/indexing strategy included: yes.
- Risks/open decisions for Jérémie included: yes.
