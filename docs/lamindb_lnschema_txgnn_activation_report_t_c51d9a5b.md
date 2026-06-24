# lnschema_txgnn activation / exact-ID registry report

Date: 2026-06-23
Task: `t_c51d9a5b` — LAMIN-SCHEMA

## Decision

Keep and activate the existing `lnschema_txgnn` schema for exact-ID TxGNN/Jouvence KG node registries. Do not replace exact KG IDs with public `bionty`/`pertdb` writes.

Jouvence is self-managed rather than LaminHub-managed for this instance. The active schema-module configuration is stored in local Lamin env files under `~/.lamin/`, not changed through a LaminHub UI.

## Activation performed

Updated both local Lamin instance env files, with timestamped backups:

```text
~/.lamin/instance--jkobject--jouvencekb.env
~/.lamin/current_instance.env
```

Changed:

```text
lamindb_instance_schema_str=bionty,pertdb
```

to:

```text
lamindb_instance_schema_str=bionty,pertdb,lnschema_txgnn
```

No Lamin SQLite table was edited directly.

## Verification

`uv run lamin info` now reports:

```text
Instance: jkobject/jouvencekb
storage: gs://jouvencekb/lamin
db: sqlite:////Users/jkobject/Library/Caches/lamindb/jouvencekb/lamin/.lamindb/lamin.db
modules: pertdb, bionty, lnschema_txgnn
```

Import/count probe:

```bash
uv run python - <<'PY'
import lamindb as ln
import lnschema_txgnn as txs
print(ln.setup.settings.instance.slug)
print(ln.setup.settings.instance.modules)
for model in [txs.Gene, txs.Molecule, txs.Disease, txs.Protein, txs.Transcript, txs.Mutation, txs.Paper, txs.Pathway, txs.Tissue, txs.CellType, txs.Dataset, txs.Enhancer]:
    print(model.__name__, model.objects.count())
PY
```

Observed:

```text
modules: {'lnschema_txgnn', 'bionty', 'pertdb'}
Gene 109325
Molecule 31007
Disease 41859
Protein 233995
Transcript 507365
Mutation 2589508
Paper 4205891
Pathway 48575
Tissue 16061
CellType 3513
Dataset 0
Enhancer 0
```

Tests:

```bash
uv run --group dev pytest tests/test_sync_parquet_nodes_to_lamindb.py tests/test_lamindb_kg_artifact_sync.py -q
```

Observed:

```text
24 passed in 0.71s
```

Exact-ID dry-run over canonical FUSE root:

```bash
uv run python -m manage_db.sync_parquet_nodes_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --node-types gene molecule disease \
  --max-rows 5 \
  --json
```

Observed output includes `status: ok` for all three node types:

```json
[
  {"node_type": "gene", "registry": "lnschema_txgnn.Gene", "seen": 5, "existing": 5, "would_create": 0, "status": "ok"},
  {"node_type": "molecule", "registry": "lnschema_txgnn.Molecule", "seen": 5, "existing": 5, "would_create": 0, "status": "ok"},
  {"node_type": "disease", "registry": "lnschema_txgnn.Disease", "seen": 5, "existing": 5, "would_create": 0, "status": "ok"}
]
```

Note: the command prints a Lamin connection line before JSON; capture stdout/stderr if machine-parsing.

## Residual schema note

Some field names reflect earlier ontology assumptions (`Gene.ensembl_gene_id`, `Molecule.chembl_id`), while current canonical IDs can include `NCBI:*` gene IDs and DrugBank-like molecule IDs. The current sync still stores exact canonical IDs in those fields and the bounded dry-run matches existing records. A future reviewed migration could add neutral `stable_id` fields after validation/review.

## Next gate

Validation card `t_edb59ab8` should now verify the activated config, exact-ID dry-run behavior, and absence of unsafe SQLite hacks. Reviewer card `t_59139647` should review after validation.
