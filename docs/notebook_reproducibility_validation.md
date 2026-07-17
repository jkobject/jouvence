# Notebook reproducibility validation

Validation task: `t_ef08aab2`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Runner: tester profile on macOS, repo commands run from workspace root with `uv run`  
Canonical writes: none

## Scope

Validated the numbered KG reproducibility notebooks and README produced by the N1/N2 work:

- `notebooks/1_lamindb_instance_setup.ipynb`
- `notebooks/1_lamindb_instance_setup.executed.ipynb`
- `notebooks/2_manage_db_setup.ipynb`
- `notebooks/2_manage_db_setup.executed.ipynb`
- `notebooks/3_access_and_cache_sources.ipynb`
- `notebooks/4_download_opentargets_and_source_snapshots.ipynb`
- `notebooks/5_create_core_nodes.ipynb`
- `notebooks/6_build_core_edges_and_evidence.ipynb`
- `notebooks/7_opentargets_edges_and_evidence.ipynb`
- `notebooks/8_block1_relation_splitting_policy.ipynb`

Parent handoffs read via Kanban:

- N0 `t_27bae77a`: audit report at `docs/notebook_reproducibility_audit.md`; sequence 3-10 proposed, with notebooks calling existing package code rather than reimplementing the pipeline inline.
- N2 `t_94a533c9`: notebooks 6-8 accepted after fix `t_99060059`; unsupported DuckDB `LEFT ANTI JOIN` removed; sample/read-only execution passed.
- N1 `t_b3a61186`: notebooks 3-5 and `notebooks/README.md` accepted after README filename/status fix.

## Commands run

### Environment smoke

```bash
cd /Users/jkobject/.openclaw/workspace/work/txgnn
pwd
uv --version
```

Observed:

- `pwd` = `/Users/jkobject/.openclaw/workspace/work/txgnn`
- `uv 0.11.23 (Homebrew 2026-06-19 aarch64-apple-darwin)`

`git status --short && git branch --show-current` was attempted but failed before reporting repo state:

```text
fatal: 'work/jkobject.github.io/.git' not recognized as a git repository
```

The validation below therefore does not rely on git state.

### nbformat validation

```bash
uv run python - <<'PY'
from pathlib import Path
import nbformat, re
root=Path.cwd()
nb_dir=root/'notebooks'
numbered=sorted([p for p in nb_dir.glob('*.ipynb') if re.match(r'^\d', p.name)])
for p in numbered:
    nb=nbformat.read(p, as_version=4)
    nbformat.validate(nb)
    code=sum(1 for c in nb.cells if c.cell_type=='code')
    md=sum(1 for c in nb.cells if c.cell_type=='markdown')
    outputs=sum(len(c.get('outputs',[])) for c in nb.cells if c.cell_type=='code')
    print(f'PASS {p.name}: cells={len(nb.cells)} code={code} markdown={md} outputs={outputs}')
PY
```

Result: PASS for all 10 numbered notebooks.

| Notebook | Cells | Code | Markdown | Outputs |
|---|---:|---:|---:|---:|
| `1_lamindb_instance_setup.executed.ipynb` | 19 | 8 | 11 | 35 |
| `1_lamindb_instance_setup.ipynb` | 19 | 8 | 11 | 9 |
| `2_manage_db_setup.executed.ipynb` | 17 | 12 | 5 | 72 |
| `2_manage_db_setup.ipynb` | 17 | 12 | 5 | 6 |
| `3_access_and_cache_sources.ipynb` | 15 | 8 | 7 | 0 |
| `4_download_opentargets_and_source_snapshots.ipynb` | 12 | 6 | 6 | 0 |
| `5_create_core_nodes.ipynb` | 16 | 8 | 8 | 0 |
| `6_build_core_edges_and_evidence.ipynb` | 10 | 6 | 4 | 0 |
| `7_opentargets_edges_and_evidence.ipynb` | 10 | 6 | 4 | 0 |
| `8_block1_relation_splitting_policy.ipynb` | 10 | 6 | 4 | 0 |

### Secrets, stale paths, and root/cache consistency scan

```bash
uv run python - <<'PY'
from pathlib import Path
import nbformat, re, json
root=Path.cwd(); nb_dir=root/'notebooks'
numbered=sorted([p for p in nb_dir.glob('*.ipynb') if re.match(r'^\d', p.name)])
patterns={
 'stale_home_ubuntu': re.compile(r'/home/ubuntu/data|/home/ubuntu'),
 'credential_file': re.compile(r'(GOOGLE_APPLICATION_CREDENTIALS|\.json\s*["\']|service[_-]?account|private_key)', re.I),
 'secret_like': re.compile(r'(api[_-]?key|secret|token|password)\s*=\s*["\'][^"\']{8,}', re.I),
 'absolute_user_path': re.compile(r'/Users/[^\s\"\']+|/mnt/gcs/[^\s\"\']+|gs://[^\s\"\']+'),
}
for p in numbered:
    nb=nbformat.read(p, as_version=4)
    text='\n'.join(str(c.get('source','')) for c in nb.cells)
    hits={k: sorted(set(m.group(0) for m in rx.finditer(text)))[:10] for k,rx in patterns.items()}
    print(p.name, json.dumps({k:v for k,v in hits.items() if v}, ensure_ascii=False))
PY
```

Findings:

- No `/home/ubuntu` or `/home/ubuntu/data` stale paths found.
- No inline secret assignments found by the `api_key|secret|token|password = "..."` scan.
- `notebooks/4_download_opentargets_and_source_snapshots.ipynb` matched `.json` only because it documents/writes a gated manifest path `.omoc/notebook-manifests/opentargets_sources.json`; the markdown explicitly says the manifest records paths/release strings but no credentials.
- Expected KG/cache roots are used/documented: `.omoc/gcs-cache/kg-v2`, `/mnt/gcs/jouvencekb/kg/v2`, and `gs://jouvencekb/kg/v2`.
- Notebooks 3-5 derive default writable paths under the current repo workspace (`data/opentargets`, `data/kg`) and keep writes disabled unless explicit flags are set.

### Import and loader/builder call scan

```bash
uv run python - <<'PY'
from pathlib import Path
import nbformat, re, ast, json
root=Path.cwd(); nb_dir=root/'notebooks'
numbered=sorted([p for p in nb_dir.glob('*.ipynb') if re.match(r'^\d', p.name)])
for p in numbered:
    imports=set(); calls=set(); syntax=[]
    nb=nbformat.read(p, as_version=4)
    for i,c in enumerate(nb.cells):
        if c.cell_type!='code':
            continue
        src=str(c.get('source',''))
        try:
            tree=ast.parse(src)
        except SyntaxError as e:
            syntax.append((i, str(e))); continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names: imports.add(a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                f=node.func
                name=None
                if isinstance(f, ast.Name): name=f.id
                elif isinstance(f, ast.Attribute): name=f.attr
                if name and re.search(r'(load|build|create|download|audit|validate|cache|split|write|read)', name, re.I):
                    calls.add(name)
    print(p.name, sorted(imports), sorted(calls), syntax)
PY
```

Result:

- All code cells parse with no syntax errors.
- Notebooks 3-8 use existing project modules/functions such as `txdata_download.download_opentargets_datasets`, `manage_db.audit_kg_coverage`, `manage_db.audit_edge_evidence`, and `manage_db.validate_kg` / `validate_duckdb` surfaces rather than inline rebuild logic.

A naive top-level import probe reported failures for direct `import lamin`, direct `import lnschema_txgnn`, and direct `import IPython`; this was not treated as a notebook failure because the actual notebook execution below is the authoritative check. Notably, notebook 3 imports `lamindb as lamin` successfully during execution.

### Safe execution of notebooks 3-8

Executed all code cells in notebooks 3-8 with sample/read-only flags and no network/build/full-validation/split promotion flags:

```bash
TXGNN_NOTEBOOK_SAMPLE_MODE=1 \
TXGNN_NOTEBOOK_ALLOW_WRITES=0 \
TXGNN_NOTEBOOK_ALLOW_NETWORK=0 \
TXGNN_NOTEBOOK_RUN_BUILD=0 \
TXGNN_NOTEBOOK_FULL_VALIDATION=0 \
TXGNN_NOTEBOOK_RUN_BLOCK1_SPLIT=0 \
uv run python - <<'PY'
import nbformat
notebooks=[
 'notebooks/3_access_and_cache_sources.ipynb',
 'notebooks/4_download_opentargets_and_source_snapshots.ipynb',
 'notebooks/5_create_core_nodes.ipynb',
 'notebooks/6_build_core_edges_and_evidence.ipynb',
 'notebooks/7_opentargets_edges_and_evidence.ipynb',
 'notebooks/8_block1_relation_splitting_policy.ipynb',
]
for nb_path in notebooks:
    nb=nbformat.read(nb_path, as_version=4)
    ns={'__name__':'__notebook_validation__'}
    ran=0
    for idx,cell in enumerate(nb.cells):
        if cell.cell_type!='code':
            continue
        exec(compile(str(cell.source), f'{nb_path}#cell{idx}', 'exec'), ns)
        ran += 1
    print(f'PASS {nb_path}: code_cells={ran}')
PY
```

Result: PASS for all six notebooks in safe mode.

| Notebook | Safe execution result |
|---|---|
| `3_access_and_cache_sources.ipynb` | PASS, 8 code cells |
| `4_download_opentargets_and_source_snapshots.ipynb` | PASS, 6 code cells; dry run, no download, no manifest write |
| `5_create_core_nodes.ipynb` | PASS, 8 code cells; dry run, no node build |
| `6_build_core_edges_and_evidence.ipynb` | PASS, 6 code cells; build/full validation skipped by flags |
| `7_opentargets_edges_and_evidence.ipynb` | PASS, 6 code cells; build/full validation skipped by flags |
| `8_block1_relation_splitting_policy.ipynb` | PASS, 6 code cells; split/full validation skipped by flags |

## README review

`notebooks/README.md` gives a clear numbered story:

1. setup (`1_lamindb_instance_setup.ipynb`, `2_manage_db_setup.ipynb`)
2. access/cache (`3_access_and_cache_sources.ipynb`)
3. source download (`4_download_opentargets_and_source_snapshots.ipynb`)
4. nodes (`5_create_core_nodes.ipynb`)
5. edges/evidence (`6_build_core_edges_and_evidence.ipynb`, `7_opentargets_edges_and_evidence.ipynb`)
6. Block 1 policy (`8_block1_relation_splitting_policy.ipynb`)
7. planned validation/export continuation (`9_sync_lamindb_and_parity.ipynb`, `10_export_and_load_graph.ipynb`)

It also documents safe defaults and heavy-operation gates:

- `TXGNN_NOTEBOOK_SAMPLE_MODE=1`
- `TXGNN_NOTEBOOK_RUN_BUILD=1`
- `TXGNN_NOTEBOOK_FULL_VALIDATION=1`
- `TXGNN_NOTEBOOK_RUN_BLOCK1_SPLIT=1`

## Data-level caveats surfaced during safe execution

These did not break notebook execution, but they are important validation signals for humans/agents rerunning the notebooks:

- `notebooks/6_build_core_edges_and_evidence.ipynb` reported `gene_interacts_gene` edge/evidence anti-join status `ok=False`: `7,424,037` edge rows, `14,336,594` evidence rows, `642,150` edges without evidence, `0` evidence rows without edges.
- `notebooks/7_opentargets_edges_and_evidence.ipynb` reported several current KG evidence-support caveats in its summary table, including `disease_associated_gene`, `gene_interacts_gene`, and `molecule_treats_disease` with `ok=False`; example: `disease_associated_gene` had `83,339` edge rows, `2,928` evidence rows, and `80,411` edges without evidence.
- `notebooks/8_block1_relation_splitting_policy.ipynb` again reported `gene_interacts_gene` with `ok=False` for edge/evidence support, while `pathway_contains_gene` and `molecule_targets_gene` were `ok=True` in the sampled/cache-backed anti-join report.

These are data/KG state findings, not notebook reproducibility failures: the notebooks executed and surfaced the caveats rather than hiding them. Full DuckDB endpoint validation and any production split/build remain intentionally gated and were not run.

## Verdict

PASS for the N3 reproducibility-notebook validation scope:

- nbformat validation passed for all numbered notebooks present in the repository.
- Safe/read-only execution passed for notebooks 3-8 under `uv run` from repo root.
- No canonical KG/GCS writes were performed.
- No stale `/home/ubuntu` paths or inline secrets were found.
- README now presents a coherent numbered story from setup through access/cache, source download, nodes, edges/evidence, Block 1 policy, and validation/export planning.

Recommended next fixes are outside this notebook-reproducibility validation card:

1. Investigate the broken git discovery state if future workers need git status/diff from this workspace (`fatal: 'work/jkobject.github.io/.git' not recognized as a git repository`).
2. Treat the anti-join `ok=False` rows surfaced by notebooks 6-8 as KG/data-quality backlog items if not already covered by active Block 1/evidence-support cards.
3. Run full endpoint validation only on a safe local/staging KG root with `TXGNN_NOTEBOOK_FULL_VALIDATION=1`; do not run it as part of lightweight notebook smoke validation.
