# lnschema_txgnn activation / exact-ID registry validation

Date: 2026-06-23
Task: `t_edb59ab8` — VALIDATE lnschema_txgnn activation/exact-ID registry
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Target LaminDB instance: `jkobject/jouvencekb`
KG root tested: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`

## Verdict

`tofix` / documented blocked state.

The LaminDB instance is active with `lnschema_txgnn`, the supported top-level import `import lnschema_txgnn` works, exact-ID registry counts are populated, bounded canonical-KG dry-runs are idempotent, and targeted tests pass.

However, `import manage_db.lnschema_txgnn` still fails in a fresh process with a Django app-registry conflict because the package is also importable as top-level `lnschema_txgnn`. This is not the previous `ModuleWasntConfigured` failure, but it means the specific `manage_db.lnschema_txgnn` import path is still unsafe unless replaced by the top-level schema-module import or fixed with a single canonical import namespace.

## 1. Active Lamin config / module behavior

Command:

```bash
uv run lamin info
```

Observed:

```text
Instance: jkobject/jouvencekb
 - branch: main
 - space: all
Details:
 - storage: gs://jouvencekb/lamin (None)
 - db: sqlite:////Users/jkobject/Library/Caches/lamindb/jouvencekb/lamin/.lamindb/lamin.db
 - modules: bionty, lnschema_txgnn, pertdb
```

Local Lamin env files both include the schema module:

```text
/Users/jkobject/.lamin/instance--jkobject--jouvencekb.env:
lamindb_instance_schema_str=bionty,pertdb,lnschema_txgnn

/Users/jkobject/.lamin/current_instance.env:
lamindb_instance_schema_str=bionty,pertdb,lnschema_txgnn
```

Python settings probe:

```text
instance_slug= jkobject/jouvencekb
instance_modules= ['bionty', 'lnschema_txgnn', 'pertdb']
```

## 2. Import behavior

Fresh process, `manage_db.lnschema_txgnn` first:

```text
manage_db.lnschema_txgnn: FAIL RuntimeError: Conflicting 'paper' models in application 'lnschema_txgnn': <class 'lnschema_txgnn.models.Paper'> and <class 'manage_db.lnschema_txgnn.models.Paper'>.
lnschema_txgnn: OK file=/Users/jkobject/.openclaw/workspace/work/txgnn/manage_db/lnschema_txgnn/__init__.py
```

Fresh process, `lnschema_txgnn` first:

```text
lnschema_txgnn: OK file=/Users/jkobject/.openclaw/workspace/work/txgnn/manage_db/lnschema_txgnn/__init__.py
manage_db.lnschema_txgnn: FAIL RuntimeError: Conflicting 'paper' models in application 'lnschema_txgnn': <class 'lnschema_txgnn.models.Paper'> and <class 'manage_db.lnschema_txgnn.models.Paper'>.
```

Interpretation: Lamin activation is no longer blocked by `ModuleWasntConfigured`; the canonical schema-module import is `import lnschema_txgnn`. The `manage_db.lnschema_txgnn` package path still double-registers Django models under the same app label and should not be used as an import path without a namespace fix.

## 3. Registry row counts

Command:

```bash
uv run python - <<'PY'
import lamindb as ln
import lnschema_txgnn as txs
print('instance_slug=', ln.setup.settings.instance.slug)
print('instance_modules=', sorted(str(x) for x in ln.setup.settings.instance.modules))
for model in [txs.Gene, txs.Molecule, txs.Disease, txs.Protein, txs.Transcript, txs.Mutation, txs.Paper, txs.Pathway, txs.Tissue, txs.CellType, txs.Dataset, txs.Enhancer]:
    print(f'{model.__name__}\t{model.objects.count()}\ttable={model._meta.db_table}')
PY
```

Observed counts:

```text
Gene	109325	table=lnschema_txgnn_gene
Molecule	31007	table=lnschema_txgnn_molecule
Disease	41859	table=lnschema_txgnn_disease
Protein	233995	table=lnschema_txgnn_protein
Transcript	507365	table=lnschema_txgnn_transcript
Mutation	2589508	table=lnschema_txgnn_mutation
Paper	4205891	table=lnschema_txgnn_paper
Pathway	48575	table=lnschema_txgnn_pathway
Tissue	16061	table=lnschema_txgnn_tissue
CellType	3513	table=lnschema_txgnn_celltype
Dataset	0	table=lnschema_txgnn_dataset
Enhancer	0	table=lnschema_txgnn_enhancer
```

## 4. Exact-ID pilot dry-run and idempotence

Command:

```bash
uv run python -m manage_db.sync_parquet_nodes_to_lamindb \
  /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --node-types gene molecule disease protein transcript mutation paper pathway tissue cell_type \
  --max-rows 5 \
  --json
```

Observed: all 10 tested node types returned `status: ok`, `seen: 5`, `existing: 5`, `would_create: 0`, `created: 0`, `skipped: 0`, `unsupported: 0`.

Idempotence command:

```bash
uv run python - <<'PY'
import json
import lnschema_txgnn as txs
from manage_db.sync_parquet_nodes_to_lamindb import sync_parquet_nodes_to_lamindb
models = {'gene': txs.Gene, 'molecule': txs.Molecule, 'disease': txs.Disease}
def counts():
    return {k: m.objects.count() for k, m in models.items()}
before = counts()
a = [s.__dict__ for s in sync_parquet_nodes_to_lamindb('/Users/jkobject/mnt/gcs/jouvencekb-kg/v2', node_types=list(models), max_rows=10, write=False)]
b = [s.__dict__ for s in sync_parquet_nodes_to_lamindb('/Users/jkobject/mnt/gcs/jouvencekb-kg/v2', node_types=list(models), max_rows=10, write=False)]
after = counts()
print(json.dumps({'before_counts': before, 'dry_run_a': a, 'dry_run_b': b, 'after_counts': after, 'counts_unchanged': before == after, 'dry_runs_identical': a == b}, indent=2, sort_keys=True))
PY
```

Observed:

```json
{
  "before_counts": {"disease": 41859, "gene": 109325, "molecule": 31007},
  "after_counts": {"disease": 41859, "gene": 109325, "molecule": 31007},
  "counts_unchanged": true,
  "dry_runs_identical": true
}
```

Each dry-run returned `existing: 10`, `would_create: 0`, `created: 0` for gene, molecule, and disease.

## 5. Unsafe private/internal Lamin hack review

Search scope: project Python files under `/Users/jkobject/.openclaw/workspace/work/txgnn`.

Findings:

- No direct Lamin SQLite writes, no manual table mutation, no Django app registry mutation, and no LaminHub/private API activation path found in the sync code.
- `manage_db/sync_parquet_nodes_to_lamindb.py` uses public `ln.connect(...)` when needed, read-only `ln.setup.settings` inspection, Django model `_meta` introspection for table/field names, and `PRAGMA busy_timeout` for SQLite lock tolerance. These are not schema/data hacks.
- `manage_db/lnschema_txgnn/__init__.py` uses `lamindb_setup._check_instance_setup(from_module="lnschema_txgnn")`, the standard Lamin schema-module guard already present in the schema package, not an activation hack.
- Activation itself was via local `~/.lamin/*.env` schema string updates documented in `docs/lamindb_lnschema_txgnn_activation_report_t_c51d9a5b.md`; no SQLite table was edited directly in this validation.

## 6. Tests

Command:

```bash
uv run --group dev pytest tests/test_sync_parquet_nodes_to_lamindb.py tests/test_lamindb_kg_artifact_sync.py -q
```

Observed:

```text
........................                                                 [100%]
24 passed in 0.28s
```

## Recommended follow-up

Fix or remove the `manage_db.lnschema_txgnn` import namespace. Recommended owner: dev. The schema package should have one canonical import path for Django model registration, likely the top-level `lnschema_txgnn` module used by LaminDB. Until then, downstream code should use `import lnschema_txgnn as txs` only.
