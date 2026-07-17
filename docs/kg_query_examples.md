# Jouvence KG query helpers

Small ergonomic helpers live in `manage_db/kg_queries.py` for read-only queries over
the canonical Jouvence KG Parquets.

They are intentionally Parquet-backed. They do **not** claim full Lamin ORM
relation querying: relation tables are not yet universally materialized in
`lnschema_txgnn`. Use these helpers as the immediate convenient layer for common
KG lookups.

## Data root

By default the helpers read the canonical FUSE/GCS root:

```text
/Users/jkobject/mnt/gcs/jouvencekb-kg/v2
```

This can be overridden with either:

```bash
export JOUVENCE_KG_ROOT=/path/to/kg/v2
```

or per call/CLI with `kg_root=` / `--kg-root`. Do not point examples at legacy
`.omoc` cache paths.

## Python examples

Resolve a gene symbol/name to canonical KG gene ids:

```python
from manage_db.kg_queries import resolve_gene, diseases_for_gene

resolve_gene(gene_name="BRCA1")
```

Typical columns:

```text
id, ncbi_gene_id, hgnc_id, uniprot_id, gene_name, name, description, source,
match_kind, rank
```

Return diseases associated with a gene:

```python
df = diseases_for_gene(gene_name="BRCA1")
df[["gene_id", "gene_name", "disease_id", "disease_name", "edge_source", "evidence_count"]].head()
```

The helper reads:

- `nodes/gene.parquet` for gene resolution;
- `edges/disease_associated_gene.parquet` where `x_id` is the gene and `y_id` is
  the disease;
- `nodes/disease.parquet` for disease labels/xrefs;
- `evidence/disease_associated_gene.parquet`, when present, for evidence summary
  counts/sources/scores.

You can query by canonical id directly:

```python
diseases_for_gene(gene_id="NCBI:672")
diseases_for_gene(gene_id="ENSG00000012048")
```

For symbols such as `BRCA1`, `resolve_gene()` may return more than one canonical
human-like row (for example NCBI and Ensembl ids) when both exist in the KG. The
disease helper unions associations across all resolved ids and deduplicates the
stable output rows.

## CLI examples

Resolve a gene:

```bash
uv run python -m manage_db.kg_queries resolve-gene --gene-name BRCA1 --format table
```

List associated diseases as JSON:

```bash
uv run python -m manage_db.kg_queries diseases-for-gene --gene-name BRCA1 --format json --limit 10
```

List associated diseases as TSV:

```bash
uv run python -m manage_db.kg_queries diseases-for-gene --gene-id NCBI:672 --format tsv > brca1_diseases.tsv
```

Skip the evidence summary join when you only need edge + disease metadata:

```bash
uv run python -m manage_db.kg_queries diseases-for-gene --gene-name BRCA1 --no-evidence
```

## Stable disease output shape

`diseases_for_gene()` returns a `pandas.DataFrame` with these columns:

```text
gene_id
gene_name
gene_label
disease_id
disease_name
disease_description
mondo_id
efo_id
mesh_id
hp_id
omim_id
doid_id
icd10_code
edge_source
credibility
score
evidence_count
evidence_sources
evidence_score_max
```

Empty results return an empty DataFrame with the same columns.
