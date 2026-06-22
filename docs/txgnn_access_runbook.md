# TxGNN KG access runbook

This runbook is the default access path for workers using the Jouvence/TxGNN KG at `gs://jouvencekb/kg/v2` from the macOS worker environment.

Status from verification on 2026-06-21:

- GCS CLI access: verified with both `gcloud storage` and `gsutil`.
- Local targeted Parquet cache: verified under `.omoc/gcs-cache/kg-v2/` with DuckDB.
- FUSE mount: not present at `~/mnt/gcs/jouvencekb/kg/v2` or `/mnt/gcs/jouvencekb/kg/v2`; do not wait on macFUSE for ordinary audits.
- LaminDB instance `jkobject/jouvencekb`: verified after exporting `LAMIN_API_KEY` from `~/.laminkey` and repairing the local Lamin SQLite cache. `uv run lamin connect jkobject/jouvencekb` exits 0 and `ln.DB("jkobject/jouvencekb")` instantiates. Caveat: Lamin instance metadata still points at missing `gs://jouvencekb/.lamindb/lamin.db`; the usable DB currently comes from the local cache copied from `gs://jouvencekb/lamin/.lamindb/lamin.db`.

Do not print tokens, DB URLs, or raw Lamin/GCloud credential files in logs.

## 1. GCS access: primary verified path

Check the active Google account without printing the email in shared logs:

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)' | sed 's/.*/<configured-account>/'
```

Verify the bucket root and subdirectories:

```bash
gcloud storage ls gs://jouvencekb/kg/v2/
gcloud storage ls gs://jouvencekb/kg/v2/edges/ | sed -n '1,5p'
gsutil ls gs://jouvencekb/kg/v2/
```

Observed sanitized output on 2026-06-21:

```text
ACTIVE_GCLOUD_ACCOUNT=<configured-account>

GCS_ROOT_LISTING
gs://jouvencekb/kg/v2/_removed_relations_20260618/
gs://jouvencekb/kg/v2/archive/
gs://jouvencekb/kg/v2/edges/
gs://jouvencekb/kg/v2/evidence/
gs://jouvencekb/kg/v2/metadata/
gs://jouvencekb/kg/v2/nodes/

GCS_EDGES_SAMPLE
gs://jouvencekb/kg/v2/edges/cell_line_derived_from_tissue.parquet
gs://jouvencekb/kg/v2/edges/cell_line_expresses_gene.parquet
gs://jouvencekb/kg/v2/edges/cell_line_from_organism.parquet
gs://jouvencekb/kg/v2/edges/cell_type_expresses_gene.parquet
gs://jouvencekb/kg/v2/edges/dataset_contains_cell_line.parquet

GSUTIL_ROOT_LISTING
gs://jouvencekb/kg/v2/_removed_relations_20260618/
gs://jouvencekb/kg/v2/archive/
gs://jouvencekb/kg/v2/edges/
gs://jouvencekb/kg/v2/evidence/
gs://jouvencekb/kg/v2/metadata/
gs://jouvencekb/kg/v2/nodes/
```

Use `gcloud storage` for new scripts; keep `gsutil` examples for compatibility with older worker notes.

## 2. Repo-local targeted cache convention

Workers should cache only the Parquet files needed for the current audit/build step. The repo-local convention is:

```text
.omoc/gcs-cache/kg-v2/edges/
.omoc/gcs-cache/kg-v2/evidence/
.omoc/gcs-cache/kg-v2/nodes/
.omoc/gcs-cache/kg-v2/raw/
```

Create it with:

```bash
mkdir -p .omoc/gcs-cache/kg-v2/{edges,evidence,nodes,raw}
```

Verified on 2026-06-21:

```text
.omoc/gcs-cache/kg-v2/edges ok
.omoc/gcs-cache/kg-v2/evidence ok
.omoc/gcs-cache/kg-v2/nodes ok
.omoc/gcs-cache/kg-v2/raw ok
```

Copy targeted files from GCS into the matching cache subdirectory:

```bash
gcloud storage cp \
  gs://jouvencekb/kg/v2/edges/gene_interacts_gene.parquet \
  .omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet

gcloud storage cp \
  gs://jouvencekb/kg/v2/evidence/gene_interacts_gene.parquet \
  .omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet
```

For raw/source archives under `gs://jouvencekb/kg/...`, put copied files under `.omoc/gcs-cache/kg-v2/raw/<source-or-slice-name>/` and keep the original `gs://...` path in the report or script arguments.

### DuckDB verification on cached Parquet

Example command:

```bash
gcloud storage cp \
  gs://jouvencekb/kg/v2/nodes/organism.parquet \
  .omoc/gcs-cache/kg-v2/nodes/organism.parquet

uv run --with duckdb python - <<'PY'
import duckdb
p = '.omoc/gcs-cache/kg-v2/nodes/organism.parquet'
con = duckdb.connect()
print('count', con.sql(f"select count(*) from read_parquet('{p}')").fetchone()[0])
print(con.sql(f"describe select * from read_parquet('{p}')").df().to_string(index=False))
print(con.sql(f"select * from read_parquet('{p}') limit 3").df().to_string(index=False))
PY
```

Observed output on 2026-06-21:

```text
count 1
    column_name column_type null  key default extra
             id     VARCHAR  YES None    None  None
    taxonomy_id     VARCHAR  YES None    None  None
        gbif_id     VARCHAR  YES None    None  None
           name     VARCHAR  YES None    None  None
scientific_name     VARCHAR  YES None    None  None
         source     VARCHAR  YES None    None  None
            id taxonomy_id gbif_id  name scientific_name        source
NCBITaxon:9606        9606 2436436 human    Homo sapiens NCBI Taxonomy
```

For relation/evidence audits, use DuckDB summaries before making schema decisions:

```bash
uv run --with duckdb python - <<'PY'
import duckdb
relation = 'gene_interacts_gene'
p = f'.omoc/gcs-cache/kg-v2/evidence/{relation}.parquet'
con = duckdb.connect()
print(con.sql(f"""
    select source, source_dataset, evidence_type, predicate, direction, count(*) as n
    from read_parquet('{p}')
    group by 1,2,3,4,5
    order by n desc
""").df().to_string(index=False))
PY
```

## 3. FUSE mount policy

Use `~/mnt/gcs/jouvencekb` only if it is already mounted and readable. Do not require macFUSE approval for ordinary worker tasks.

Check it with:

```bash
if [ -d "$HOME/mnt/gcs/jouvencekb/kg/v2" ]; then
  echo '~/mnt/gcs/jouvencekb/kg/v2 exists'
  mount | grep "$HOME/mnt/gcs/jouvencekb" || true
else
  echo '~/mnt/gcs/jouvencekb/kg/v2 not mounted/present'
fi
```

Observed on 2026-06-21:

```text
~/mnt/gcs/jouvencekb/kg/v2 not mounted/present
/mnt/gcs/jouvencekb/kg/v2 not present
```

If the mount is absent, use `gcloud storage cp` or `gsutil cp` into `.omoc/gcs-cache/kg-v2/` and read with DuckDB/PyArrow locally.

If the mount becomes available later, the macOS mount command is expected to be:

```bash
mkdir -p ~/mnt/gcs/jouvencekb
gcsfuse --implicit-dirs jouvencekb ~/mnt/gcs/jouvencekb
```

That depends on macFUSE approval in System Settings. Do not block downstream KG audits on it.

## 4. LaminDB connection

Active instance slug for this project:

```text
jkobject/jouvencekb
```

The repo currently pins `lamindb==2.2.1` in `pyproject.toml`; an older executed notebook notes that the remote DB may be ahead of that package version and suggests `pip install lamindb>=2.4`. In this repo, use `uv run` so the workspace schema package is available.

### CLI checks

Workers on this Mac should load the local Lamin API key before Lamin commands. Do not echo the key:

```bash
export LAMIN_API_KEY="$(cat ~/.laminkey)"
```

Then run:

```bash
uv run lamin info
uv run lamin connect jkobject/jouvencekb
uv run lamin info
```

If `uv run lamin info` reports `User: anonymous`, first check whether `~/.laminkey` exists and was exported as above. If credentials are absent or expired, run:

```bash
uv run lamin login
uv run lamin connect jkobject/jouvencekb
```

Do not print `~/.lamin/*.env`, `~/.laminkey`, or raw credential contents; they may contain secrets.

Observed sanitized output on 2026-06-21 after auth/cache repair:

```text
Instance: jkobject/jouvencekb
 - branch: main
 - space: all
Details:
 - storage: gs://jouvencekb (None)
 - db: sqlite:////Users/jkobject/Library/Caches/lamindb/jouvencekb/.lamindb/lamin.db
 - modules: bionty, pertdb
Cache & settings:
 - cache: /Users/jkobject/Library/Caches/lamindb
 - user settings: /Users/jkobject/.lamin
 - system settings: /Library/Application Support/lamindb
User: jkobject

uv run lamin connect jkobject/jouvencekb
! The original path gs://jouvencekb/.lamindb/lamin.db does not exist anymore.
However, the local path /Users/jkobject/Library/Caches/lamindb/jouvencekb/.lamindb/lamin.db still exists, you might want to reupload the object back.
! SQLite file does not exist in the cloud, but exists locally: /Users/jkobject/Library/Caches/lamindb/jouvencekb/.lamindb/lamin.db
To push the file to the cloud, call: lamin disconnect
→ connected lamindb: jkobject/jouvencekb
exit_code 0
```

Do **not** run `lamin disconnect` or otherwise push/reupload the SQLite DB to GCS from a worker unless the operator explicitly approves that remote write. The cleaner long-term fix is to align the Lamin instance storage root with the actual DB object path, or intentionally copy/symlink the DB to the path Lamin expects.

### Python checks

Default repo environment:

```bash
export LAMIN_API_KEY="$(cat ~/.laminkey)"
uv run python - <<'PY'
import lamindb as ln
print('lamindb', getattr(ln, '__version__', 'unknown'))
db = ln.DB('jkobject/jouvencekb')
print('db_instantiated', type(db).__name__)
print('artifact_count', ln.Artifact.filter().count())
print('collection_count', ln.Collection.filter().count())
PY
```

One-off newer package probe, useful if the repo pin becomes too old for the remote DB:

```bash
export LAMIN_API_KEY="$(cat ~/.laminkey)"
uv run \
  --with 'lamindb>=2.4' \
  --with 'lnschema-txgnn @ ./manage_db/lnschema_txgnn' \
  python - <<'PY'
import lamindb as ln
print('lamindb', getattr(ln, '__version__', 'unknown'))
db = ln.DB('jkobject/jouvencekb')
print('db_instantiated', type(db).__name__)
PY
```

Observed on 2026-06-21 after auth/cache repair:

```text
lamindb 2.2.1
→ connected lamindb: jkobject/jouvencekb
db_instantiated DB
Artifact count 0
Collection count 0
```

Interpretation: the repo-pinned LaminDB package can connect and inspect registries when the API key is exported and the repaired local SQLite cache is present. The warning about missing `gs://jouvencekb/.lamindb/lamin.db` is expected until the remote storage-root mismatch is fixed.

### Local Lamin SQLite cache

A working local Lamin cache exists at Lamin's default cache path:

```text
/Users/jkobject/Library/Caches/lamindb/jouvencekb/.lamindb/lamin.db
```

It was repaired non-destructively by copying the real remote DB from:

```text
gs://jouvencekb/lamin/.lamindb/lamin.db
```

The repo-local copy remains useful for direct SQLite inspection:

```text
.omoc/gcs-cache/lamin/lamin.db
```

Observed size on 2026-06-21:

```text
-rw-r--r--  2.8G .omoc/gcs-cache/lamin/lamin.db
```

Treat direct SQLite access as a local inspection fallback. For normal KG relation audits, prefer the GCS Parquet cache unless the task explicitly needs Lamin registries.

## 5. Worker decision tree

1. Need canonical KG Parquets?
   - First try `gcloud storage ls gs://jouvencekb/kg/v2/`.
   - Copy only needed Parquets into `.omoc/gcs-cache/kg-v2/{edges,evidence,nodes,raw}`.
   - Query local files with DuckDB or PyArrow.
2. Need full tree filesystem semantics?
   - Use `~/mnt/gcs/jouvencekb` only if already mounted.
   - If absent, do not wait for macFUSE; copy targeted files instead.
3. Need LaminDB registries?
   - Run `uv run lamin info`.
   - If anonymous, export `LAMIN_API_KEY` from `~/.laminkey` using the CLI-check command above; if that file is missing/expired, run `uv run lamin login` or ask the operator for LaminHub auth/permissions.
   - Then run `uv run lamin connect jkobject/jouvencekb` and the Python `ln.DB(...)` probe.
4. Need to update canonical KG?
   - Build and validate locally first.
   - Use explicit GCS write/copy commands only after validation gates and human review where relevant.

## 6. Common pitfalls

- Do not use `/home/ubuntu/data` on this macOS worker.
- Do not assume `/mnt/gcs/jouvencekb` exists; this path is from older/Linux-oriented notes.
- Do not convert RNA/gene-level source rows into protein relations just because a gene-to-protein mapping exists.
- Do not copy whole bucket directories unless the task explicitly requires it; most audits need a handful of Parquets.
- Do not print Lamin/GCloud credential file contents.
- Do not treat local `.omoc/gcs-cache/lamin/lamin.db` as equivalent to a verified LaminDB connection; verify with `uv run lamin connect jkobject/jouvencekb` and a Python registry probe.
- Do not run the `lamin disconnect` cloud-push suggestion from Lamin's warning unless explicitly approved; it is a remote write to the bucket.
