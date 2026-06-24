# LaminDB registry export and PyG mapping validation report

Date: 2026-06-23
Task: `t_616059b0`
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Verdict

PASS for the implemented/exported artifacts currently under review.

- No operational `.omoc` dependency was found in the LaminDB export code/tests. The PyG builder contains two `.omoc` mentions only in explanatory strings stating that it never reads `.omoc` staging state.
- LaminDB manifest/report artifacts point to canonical `gs://jouvencekb/kg/v2/...` URIs, with no local or `.omoc` artifact URI leakage.
- LaminDB metadata/list smoke passed without credentials and returned nodes/edges/evidence/features groups.
- PyG strict pilot at `gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict` passed validation and internal consistency checks for node maps, edge_index shapes, reverse edge sidecars, relation metadata, and feature row maps.
- Scope note: this validates the bounded strict PyG pilot described by `docs/pyg_export_runbook.md`, not a full-KG tensorization or PyTorch/PyG `.pt` runtime load path.

## Environment

- Repo/workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
- Canonical KG root from project docs: `/mnt/gcs/jouvencekb/kg/v2` / `gs://jouvencekb/kg/v2`
- PyG pilot output: `gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict`
- Commands run with `uv run` from the repo root.

## Commands and outputs

### 1. Static `.omoc` dependency check + compile + targeted tests

Command:

```bash
python - <<'PY'
from pathlib import Path
files = [
    'manage_db/build_lamindb_kg_manifest.py',
    'manage_db/sync_kg_artifacts_to_lamindb.py',
    'manage_db/build_pyg_export.py',
    'tests/test_lamindb_kg_artifact_sync.py',
    'tests/test_build_pyg_export.py',
]
for f in files:
    text = Path(f).read_text()
    hits = [(i+1,l) for i,l in enumerate(text.splitlines()) if '.omoc' in l]
    print(f'{f}: {len(hits)} .omoc hits')
    for line_no, line in hits[:10]:
        print(f'  {line_no}: {line}')
PY
uv run python -m py_compile \
  manage_db/build_lamindb_kg_manifest.py \
  manage_db/sync_kg_artifacts_to_lamindb.py \
  manage_db/build_pyg_export.py
uv run --group dev pytest \
  tests/test_lamindb_kg_artifact_sync.py \
  tests/test_build_pyg_export.py -q
```

Output:

```text
manage_db/build_lamindb_kg_manifest.py: 0 .omoc hits
manage_db/sync_kg_artifacts_to_lamindb.py: 0 .omoc hits
manage_db/build_pyg_export.py: 2 .omoc hits
  88:     ``features/`` Parquets from ``config.kg_root``.  It never reads ``.omoc`` and
  531: Derived from `{config.kg_root}` without reading `.omoc` staging state.
tests/test_lamindb_kg_artifact_sync.py: 0 .omoc hits
tests/test_build_pyg_export.py: 0 .omoc hits

uv run python -m py_compile ...
exit_code 0

uv run --group dev pytest tests/test_lamindb_kg_artifact_sync.py tests/test_build_pyg_export.py -q
..........                                                               [100%]
10 passed in 1.12s
```

### 2. LaminDB manifest/report canonical URI validation

Command:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
m=json.loads(Path('docs/lamindb_kg_v2_manifest.json').read_text())
r=json.loads(Path('docs/lamindb_kg_v2_artifact_sync_report.json').read_text())
layers=m['layers']
counts={}; rows={}; uri_bad=[]; local_like=[]
for x in layers:
    counts[x['layer']]=counts.get(x['layer'],0)+1
    rows[x['layer']]=rows.get(x['layer'],0)+int(x['rows'])
    uri=x.get('uri','')
    if not uri.startswith('gs://jouvencekb/kg/v2/'):
        uri_bad.append((x.get('key'), uri))
    if '.omoc' in uri or '/.omoc/' in uri or uri.startswith('/'):
        local_like.append((x.get('key'), uri))
print('manifest canonical_root', m.get('canonical_root'))
print('manifest entries', len(layers))
print('manifest counts_by_layer', dict(sorted(counts.items())))
print('manifest rows_by_layer', dict(sorted(rows.items())))
print('manifest uri_bad_count', len(uri_bad), 'local_or_omoc_uri_count', len(local_like))
print('dry_run report summary', r.get('summary', {}))
print('dry_run errors', r.get('errors'))
if uri_bad or local_like or r.get('errors') or r.get('summary',{}).get('error',0):
    raise SystemExit(1)
PY
```

Output:

```text
manifest canonical_root gs://jouvencekb/kg/v2
manifest entries 79
manifest counts_by_layer {'edges': 37, 'evidence': 15, 'features': 12, 'nodes': 15}
manifest rows_by_layer {'edges': 94880924, 'evidence': 69693655, 'features': 808269, 'nodes': 55523691}
manifest uri_bad_count 0 local_or_omoc_uri_count 0
dry_run report summary {'created': 0, 'error': 0, 'noop': 0, 'updated': 0, 'would_create': 79, 'would_update': 0}
dry_run errors []
```

### 3. LaminDB metadata/query smoke

Command:

```bash
uv run python - <<'PY'
import json, subprocess, sys
cmd=[sys.executable,'-m','manage_db.sync_kg_artifacts_to_lamindb','--manifest','docs/lamindb_kg_v2_manifest.json','--list-metadata']
proc=subprocess.run(cmd,text=True,capture_output=True)
print('subprocess_exit', proc.returncode)
text=proc.stdout.strip(); dec=json.JSONDecoder(); objs=[]; idx=0
while idx < len(text):
    while idx < len(text) and text[idx].isspace(): idx+=1
    if idx>=len(text): break
    obj,end=dec.raw_decode(text, idx); objs.append(obj); idx=end
print('json_objects', len(objs))
metadata=objs[0]
report=objs[-1]
print('metadata_group_counts', {k: len(metadata[k]) for k in ['nodes','edges','evidence','features']})
print('metadata_sample_node', metadata['nodes'][0])
print('metadata_sample_feature', metadata['features'][0])
print('report_summary', report.get('summary'))
print('report_errors', report.get('errors'))
if proc.returncode != 0 or report.get('errors') or report.get('summary',{}).get('error',0):
    raise SystemExit(1)
PY
```

Output:

```text
subprocess_exit 0
json_objects 2
metadata_group_counts {'nodes': 15, 'edges': 37, 'evidence': 15, 'features': 12}
metadata_sample_node {'key': 'kg/v2/nodes/cell_line.parquet', 'metadata_fingerprint': 'b59867b3382b0420ecb728203ae9f10dae7eef4dedaf975e162a6c893524681c', 'name': 'cell_line', 'rows': 1183, 'uri': 'gs://jouvencekb/kg/v2/nodes/cell_line.parquet'}
metadata_sample_feature {'key': 'kg/v2/features/cell_line_textual_summary.parquet', 'metadata_fingerprint': '44b7140b08edbeeeed33ff51c45ca50d80ea6aaa84938f8db4b0ebb4524a4b5a', 'name': 'cell_line_textual_summary', 'rows': 1140, 'uri': 'gs://jouvencekb/kg/v2/features/cell_line_textual_summary.parquet'}
report_summary {'created': 0, 'error': 0, 'noop': 0, 'updated': 0, 'would_create': 79, 'would_update': 0}
report_errors []
```

### 4. PyG strict pilot consistency validation

Command:

```bash
uv run python - <<'PY'
# Opens gs://jouvencekb/kg/v2/ml/pyg/pilot_t_a28b941e_strict with fsspec.
# Checks manifest kg_root, validation_report status, node maps/inverses/stats,
# relation_to_edge_type metadata, edge_index.npy/parquet/row_map/attr counts,
# reverse edge sidecars, endpoint bounds, and node feature row maps.
PY
```

Output:

```text
status {'validation_status': 'pass', 'error_count': 0, 'warning_count': 0, 'errors': []}
node_counts {'disease': 41859, 'gene': 267830, 'molecule': 31007}
edge_summaries [{'relation': 'disease_associated_gene', 'edge_dir': 'gene__disease_associated_gene__disease', 'shape': [2, 10000], 'rows': 10000, 'reverse_shape': [2, 10000], 'missing_src': 0, 'missing_dst': 0}, {'relation': 'molecule_targets_gene', 'edge_dir': 'molecule__molecule_targets_gene__gene', 'shape': [2, 10000], 'rows': 10000, 'reverse_shape': [2, 10000], 'missing_src': 0, 'missing_dst': 0}]
feature_summaries [{'key': 'gene/gene_textual_summary', 'row_map': 'node_features/gene/gene_textual_summary.row_map.parquet', 'rows': 212029, 'manifest_mapped_rows': 212029, 'node_type': 'gene', 'source_path': 'gs://jouvencekb/kg/v2/features/gene_textual_summary.parquet', 'coverage_fraction': 0.791655}, {'key': 'molecule/molecule_textual_summary', 'row_map': 'node_features/molecule/molecule_textual_summary.row_map.parquet', 'rows': 22230, 'manifest_mapped_rows': 22230, 'node_type': 'molecule', 'source_path': 'gs://jouvencekb/kg/v2/features/molecule_textual_summary.parquet', 'coverage_fraction': 0.716935}]
metadata_edge_types ["('gene', 'disease_associated_gene', 'disease')", "('molecule', 'molecule_targets_gene', 'gene')"]
```

## Notes

- I did not perform live LaminDB writes; validation used the reviewed manifest/report plus credential-free `--list-metadata`/dry-run path.
- The PyG validation initially failed under an incorrect validator assumption that feature row maps lived under `features/`; inspecting `manifest.json` showed the actual expected layout is `node_features/{node_type}/{feature_table}.row_map.parquet`. The final validator used the manifest-declared paths and passed.
