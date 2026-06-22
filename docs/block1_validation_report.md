# Block 1 validation report

Task: `t_8d6a0599` — D1 validate Block 1 relations, evidence, endpoint integrity, tests
Fix task: `t_c3a400fc` — stale cache/evidence audit blocker cleanup

Date: 2026-06-22
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Accessible KG root used for validation: `.omoc/gcs-cache/kg-v2`
Canonical mount status: `/mnt/gcs/jouvencekb/kg/v2` is not mounted in this worker session; canonical evidence was accessed with `gcloud storage`.

## Parent and promotion handoffs read

- `t_6a3d2420` (`molecule_targets_gene` cleanup): accepted after review; cleaned/backfilled evidence was staged at `.omoc/staging/molecule-targets-cleanup-20260621/evidence/molecule_targets_gene.parquet`, with 41,239 evidence rows and stale predicate/direction/source-record counts all zero. Canonical promotion was intentionally deferred in that implementation card.
- `t_e383bbd2` (`pathway_contains_gene`): accepted after independent review; staged/validated pathway evidence has full edge/evidence support and no `pathway_contains_protein` split was promoted.
- `t_f1b6f016` (`gene_interacts_gene`): accepted after R4; current canonical `gene_interacts_gene` remains broad/no-split, stale PPI split artifacts were removed, and no approved C1 PPI split artifact remains.
- `t_d8c49571` (promotion): explicitly promoted the accepted C2/C3 evidence artifacts to canonical GCS. It deleted the local promoted duplicates after verification, explaining why `.omoc/staging/molecule-targets-cleanup-20260621/evidence/molecule_targets_gene.parquet` is absent locally. Promoted canonical `molecule_targets_gene` evidence: size `1,028,430`, CRC32C `AR1yjQ==`, MD5 `4uQXe3q9QOQT7PCZ0sOyjQ==`, SHA256 `fc6bf7ca687167a906b43bc83af219e1a16bcb4e78245dcf4371536a9e2621f7`.

## Overall status

PASS for corrected Block 1 validation inputs available to this worker.

The D1 blockers were mechanical/local-scope blockers, not evidence-policy blockers:

1. The local validation cache had stale `molecule_targets_gene` evidence. It was refreshed from the accepted canonical GCS object at `gs://jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet` into `.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet`.
2. `gene_interacts_gene` is not included in the complete-evidence audit gate for Block 1, because the accepted C1/R4 policy keeps this canonical relation broad/no-split and preserves the legacy TxGNN subset without invented evidence. The full audit is still recorded below as a policy exception: 642,150 TxGNN edges lack evidence; the OpenTargets/interaction subset has evidence.
3. Full KG coverage still cannot be asserted from this worker because `/mnt/gcs/jouvencekb/kg/v2` is absent and `.omoc/gcs-cache/kg-v2` is intentionally partial. This report validates the Block 1 relations and evidence files accessible for D1, not whole-KG canonical coverage.

## Commands and results

### 1. Python compile checks

Command:

```bash
uv run python -m compileall -q manage_db
```

Result: PASS, exit code 0.

Output:

```text
warning: `VIRTUAL_ENV=/Users/jkobject/.hermes/hermes-agent/venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
```

### 2. Targeted pytest suites

Command:

```bash
uv run --group dev pytest \
  tests/test_kg_schema_cleanup.py \
  tests/test_kg_evidence.py \
  tests/test_backfill_edge_evidence.py \
  tests/test_kg_storage.py \
  tests/test_audit_kg_coverage.py \
  tests/test_build_intact_protein_interactions.py \
  tests/test_build_staged_mirna_targets.py \
  tests/test_prepare_real_mirna_sources.py \
  -q
```

Result: PASS, exit code 0.

Output:

```text
...................................................                      [100%]
51 passed in 4.42s
```

### 3. Restored/synced accepted `molecule_targets_gene` evidence artifact

The local staged path from `t_6a3d2420` is absent because promotion task `t_d8c49571` intentionally deleted local promoted duplicates after successful canonical upload and verification. The accepted artifact was recovered from canonical GCS and synced into the validation-accessible local cache.

Command:

```bash
mkdir -p .omoc/gcs-cache/kg-v2/evidence
gcloud storage cp \
  gs://jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet \
  .omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet
gcloud storage hash .omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet
```

Result: PASS.

Output:

```text
Copying gs://jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet to file://.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet
Average throughput: 36.3MiB/s
---
crc32c_hash: AR1yjQ==
digest_format: base64
md5_hash: 4uQXe3q9QOQT7PCZ0sOyjQ==
url: .omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet
{'path': '.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet', 'exists': True, 'size': 1028430}
```

Focused metadata validation command:

```bash
uv run --with duckdb python - <<'PY'
import duckdb, json
p='.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet'
con=duckdb.connect()
res={}
res['rows']=con.execute(f"select count(*) from read_parquet('{p}')").fetchone()[0]
res['source_dataset_counts']=dict(con.execute(f"select coalesce(source_dataset,'<NULL>') as ds, count(*) from read_parquet('{p}') group by 1 order by 2 desc").fetchall())
cols={r[0] for r in con.execute(f"describe select * from read_parquet('{p}')").fetchall()}
if 'predicate' in cols:
    res['stale_predicate_rows']=con.execute(f"select count(*) from read_parquet('{p}') where predicate='molecule_targets_protein'").fetchone()[0]
if 'direction' in cols:
    res['stale_direction_rows']=con.execute(f"select count(*) from read_parquet('{p}') where direction='molecule_targets_protein'").fetchone()[0]
if 'source_record_id' in cols:
    res['stale_source_record_rows']=con.execute(f"select count(*) from read_parquet('{p}') where source_record_id like 'molecule_targets_protein:%'").fetchone()[0]
if 'text_span' in cols:
    res['text_span_present_rows']=con.execute(f"select count(*) from read_parquet('{p}') where text_span is not null and text_span <> ''").fetchone()[0]
print(json.dumps(res, indent=2, sort_keys=True))
PY
```

Result: PASS.

```json
{
  "rows": 41239,
  "source_dataset_counts": {
    "ctd_chemical_gene": 1212,
    "drug_mechanism_of_action": 14559,
    "drug_protein": 25468
  },
  "stale_direction_rows": 0,
  "stale_predicate_rows": 0,
  "stale_source_record_rows": 0,
  "text_span_present_rows": 41239
}
```

### 4. Corrected edge/evidence support audit

Corrected audit scope: complete edge/evidence support is required for the newly accepted Block 1 evidence backfills/cleanup (`pathway_contains_gene`, `molecule_targets_gene`). `gene_interacts_gene` is handled as a policy exception below because C1/R4 explicitly accepted keeping the broad legacy relation with the TxGNN subset lacking evidence rather than inventing unsupported evidence or deriving source-native protein/TF/transcript splits from gene endpoints.

Command:

```bash
uv run python -m manage_db.audit_edge_evidence \
  .omoc/gcs-cache/kg-v2 \
  --relations pathway_contains_gene molecule_targets_gene \
  --json | tee .omoc/reports/block1-validation-corrected-evidence-audit-20260622.json
```

Result: PASS (`ok=true`).

```json
{
  "kg_uri": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/gcs-cache/kg-v2",
  "ok": true,
  "relation_reports": {
    "molecule_targets_gene": {
      "edge_rows": 41239,
      "edges_without_evidence": 0,
      "evidence_rows": 41239,
      "evidence_without_edge": 0,
      "ok": true,
      "relation": "molecule_targets_gene"
    },
    "pathway_contains_gene": {
      "edge_rows": 630932,
      "edges_without_evidence": 0,
      "evidence_rows": 630932,
      "evidence_without_edge": 0,
      "ok": true,
      "relation": "pathway_contains_gene"
    }
  }
}
```

### 5. `gene_interacts_gene` policy exception audit

Command retained for transparency:

```bash
uv run python -m manage_db.audit_edge_evidence \
  .omoc/gcs-cache/kg-v2 \
  --relations gene_interacts_gene pathway_contains_gene molecule_targets_gene \
  --json | tee .omoc/reports/block1-validation-full-evidence-audit-20260622.json
```

Result: expected `ok=false` only because `gene_interacts_gene` contains 642,150 legacy TxGNN broad edges without evidence.

```json
{
  "relation_reports": {
    "gene_interacts_gene": {
      "edge_rows": 7424037,
      "edges_without_evidence": 642150,
      "evidence_rows": 14336594,
      "evidence_without_edge": 0,
      "ok": false,
      "relation": "gene_interacts_gene"
    },
    "molecule_targets_gene": {
      "edge_rows": 41239,
      "edges_without_evidence": 0,
      "evidence_rows": 41239,
      "evidence_without_edge": 0,
      "ok": true,
      "relation": "molecule_targets_gene"
    },
    "pathway_contains_gene": {
      "edge_rows": 630932,
      "edges_without_evidence": 0,
      "evidence_rows": 630932,
      "evidence_without_edge": 0,
      "ok": true,
      "relation": "pathway_contains_gene"
    }
  }
}
```

Source-count spot check:

```bash
uv run --with duckdb python - <<'PY'
import duckdb, json
con=duckdb.connect()
edge='.omoc/gcs-cache/kg-v2/edges/gene_interacts_gene.parquet'
evid='.omoc/gcs-cache/kg-v2/evidence/gene_interacts_gene.parquet'
res={
  'edge_source_counts': dict(con.execute(f"select coalesce(source,'<NULL>'), count(*) from read_parquet('{edge}') group by 1 order by 2 desc").fetchall()),
  'evidence_source_dataset_counts': dict(con.execute(f"select coalesce(source,'<NULL>') || '/' || coalesce(source_dataset,'<NULL>'), count(*) from read_parquet('{evid}') group by 1 order by 2 desc").fetchall()),
}
print(json.dumps(res, indent=2, sort_keys=True))
PY
```

Result:

```json
{
  "edge_source_counts": {
    "OpenTargets": 6781887,
    "TxGNN": 642150
  },
  "evidence_source_dataset_counts": {
    "OpenTargets/interaction": 14336594
  }
}
```

Policy decision: do not fabricate evidence for the 642,150 TxGNN legacy rows. C1/R4 accepted that current canonical `gene_interacts_gene` stays broad/no-split and that no source-native split artifact should be promoted from these gene endpoints. Therefore, the D1 complete-evidence gate must exclude this accepted legacy subset/relation or report it as a policy-accepted exception, not as a blocker.

### 6. DuckDB endpoint anti-join validation and policy spot checks

D1 endpoint validation remains PASS from the accessible cache.

| Relation | Edge rows | Evidence rows | Missing x nodes | Missing y nodes | Source counts |
|---|---:|---:|---:|---:|---|
| `gene_interacts_gene` | 7,424,037 | 14,336,594 | 0 gene | 0 gene | OpenTargets 6,781,887; TxGNN 642,150 |
| `pathway_contains_gene` | 630,932 | 630,932 | 0 pathway | 0 gene | TxGNN 340,383; OpenTargets/GO 290,549 |
| `molecule_targets_gene` | 41,239 | 41,239 | 0 molecule | 0 gene | TxGNN 26,680; OpenTargets 14,559 |

Additional policy checks:

- `pathway_contains_gene`: `protein_like_gene_endpoints = 0`.
- `molecule_targets_gene`: endpoint families are molecule→gene only; refreshed evidence now has no stale `molecule_targets_protein` predicate/direction/source_record tokens and has recovered TxGNN source datasets.
- No gene-level rows were observed promoted to active `pathway_contains_protein` or `molecule_targets_protein` relations in the accessible Block 1 cache.
- Current canonical `gene_interacts_gene` remains broad/no-split; no approved C1 PPI split should be promoted.

### 7. Coverage audit

Command previously run by D1:

```bash
uv run python -m manage_db.audit_kg_coverage \
  .omoc/gcs-cache/kg-v2 \
  --json > .omoc/reports/block1-validation-coverage-20260622.json
```

Result: expected `ok=false` for the partial local cache, not a Block 1 evidence failure. The cache has the Block 1 relation files used above but not the full canonical schema (11/67 edge files and 10/15 node files in the D1 run). `/mnt/gcs/jouvencekb/kg/v2` is still absent in this worker session, so full canonical KG coverage must be run from an environment with the GCS FUSE mount or a complete local mirror.

## Source-native policy validation

Status: PASS for corrected D1 inputs, with one explicit policy exception.

Checks passed:

- `pathway_contains_gene` has complete edge/evidence support: 630,932 / 630,932, zero missing support.
- `molecule_targets_gene` has complete edge/evidence support after local cache refresh: 41,239 / 41,239, zero missing support.
- `molecule_targets_gene` evidence provenance is the accepted cleaned artifact: source datasets `drug_protein`, `ctd_chemical_gene`, `drug_mechanism_of_action`; stale `molecule_targets_protein` metadata token counts are zero.
- Block 1 active relation endpoints are type-consistent and anti-join clean in the local cache.
- No gene-level rows are promoted to active protein split relations in the accessible cache.
- No RNA expression is projected to protein.

Policy-accepted exception:

- `gene_interacts_gene` has 642,150 TxGNN legacy edges without evidence. Per `t_f1b6f016` and accepted C1/R4 policy, this relation remains broad/no-split and should not be backfilled with invented evidence or split into protein/TF/transcript relations from gene endpoints. The validation command that gates complete evidence therefore excludes `gene_interacts_gene` and records the full-audit failure as an accepted legacy exception.

Remaining limitation:

- Whole-KG coverage cannot be confirmed from this partial cache. Re-run `uv run python -m manage_db.audit_kg_coverage /mnt/gcs/jouvencekb/kg/v2 --json` once `/mnt/gcs/jouvencekb/kg/v2` is mounted, or against a complete mirror.

## Tester re-run after fix (`t_b85a55c1`)

Timestamp: 2026-06-22 16:06:44 CEST (+0200)
Tester workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Canonical mount check: `/mnt/gcs/jouvencekb/kg/v2` is still absent (`mount_present=no`), so this independent re-run validates the Block 1 files in `.omoc/gcs-cache/kg-v2` plus the refreshed validation-accessible evidence object.

### Handoffs read

- Original blocked validation card `t_8d6a0599`: previous D1 failure was stale local `molecule_targets_gene` evidence plus an unscoped full evidence audit that treated accepted legacy `gene_interacts_gene` missing TxGNN evidence as a blocker.
- Parent fix card `t_c3a400fc`: synced accepted canonical `molecule_targets_gene` evidence into `.omoc/gcs-cache/kg-v2/evidence/molecule_targets_gene.parquet`, documented the accepted `gene_interacts_gene` policy exception, and did no canonical promotion.

### Commands re-run and outputs

Compile and targeted tests:

```bash
uv run python -m compileall -q manage_db && uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_kg_evidence.py tests/test_backfill_edge_evidence.py tests/test_kg_storage.py tests/test_audit_kg_coverage.py tests/test_build_intact_protein_interactions.py tests/test_build_staged_mirna_targets.py tests/test_prepare_real_mirna_sources.py -q
```

Result: PASS, exit code 0.

```text
warning: `VIRTUAL_ENV=/Users/jkobject/.hermes/hermes-agent/venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
warning: `VIRTUAL_ENV=/Users/jkobject/.hermes/hermes-agent/venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
...................................................                      [100%]
51 passed in 3.69s
```

Corrected evidence-support gate for intended complete-evidence relations:

```bash
uv run python -m manage_db.audit_edge_evidence .omoc/gcs-cache/kg-v2 --relations pathway_contains_gene molecule_targets_gene --json | tee .omoc/reports/block1-validation-corrected-evidence-audit-20260622-tester-rerun.json
```

Result: PASS (`ok=true`).

```json
{
  "kg_uri": "/Users/jkobject/.openclaw/workspace/work/txgnn/.omoc/gcs-cache/kg-v2",
  "ok": true,
  "relation_reports": {
    "molecule_targets_gene": {"edge_rows": 41239, "edges_without_evidence": 0, "evidence_rows": 41239, "evidence_without_edge": 0, "ok": true, "relation": "molecule_targets_gene"},
    "pathway_contains_gene": {"edge_rows": 630932, "edges_without_evidence": 0, "evidence_rows": 630932, "evidence_without_edge": 0, "ok": true, "relation": "pathway_contains_gene"}
  }
}
```

Full transparency audit including `gene_interacts_gene`:

```bash
uv run python -m manage_db.audit_edge_evidence .omoc/gcs-cache/kg-v2 --relations gene_interacts_gene pathway_contains_gene molecule_targets_gene --json | tee .omoc/reports/block1-validation-full-evidence-audit-20260622-tester-rerun.json
```

Result: expected `ok=false` only because accepted legacy broad `gene_interacts_gene` has 642,150 TxGNN edges without evidence. This relation is excluded from the Block 1 complete-evidence gate by accepted C1/R4 policy; there is no valid new evidence backfill in this fix, and no evidence was invented.

```json
{
  "gene_interacts_gene": {"edge_rows": 7424037, "edges_without_evidence": 642150, "evidence_rows": 14336594, "evidence_without_edge": 0, "ok": false},
  "molecule_targets_gene": {"edge_rows": 41239, "edges_without_evidence": 0, "evidence_rows": 41239, "evidence_without_edge": 0, "ok": true},
  "pathway_contains_gene": {"edge_rows": 630932, "edges_without_evidence": 0, "evidence_rows": 630932, "evidence_without_edge": 0, "ok": true}
}
```

DuckDB endpoint anti-joins and metadata/freshness checks were run with `uv run --with duckdb python ...` and saved to `.omoc/reports/block1-validation-endpoint-metadata-tester-rerun-20260622.json`.

Result: PASS.

Key output:

```json
{
  "gene_interacts_gene": {"edge_rows": 7424037, "missing_x_nodes": 0, "missing_y_nodes": 0, "edge_source_counts": {"OpenTargets": 6781887, "TxGNN": 642150}, "evidence_source_dataset_counts": {"OpenTargets/interaction": 14336594}},
  "pathway_contains_gene": {"edge_rows": 630932, "missing_x_nodes": 0, "missing_y_nodes": 0, "edge_source_counts": {"OpenTargets/GO": 290549, "TxGNN": 340383}, "evidence_rows": 630932},
  "molecule_targets_gene": {"edge_rows": 41239, "missing_x_nodes": 0, "missing_y_nodes": 0, "edge_source_counts": {"OpenTargets": 14559, "TxGNN": 26680}, "evidence_rows": 41239},
  "molecule_targets_gene_evidence_freshness": {"rows": 41239, "blank_source_dataset_rows": 0, "stale_predicate_rows": 0, "stale_direction_rows": 0, "stale_source_record_rows": 0, "text_span_present_rows": 41239, "source_dataset_counts": {"drug_protein": 25468, "drug_mechanism_of_action": 14559, "ctd_chemical_gene": 1212}},
  "active_protein_split_files": {"molecule_targets_protein": {"edge_exists": false, "evidence_exists": false}, "pathway_contains_protein": {"edge_exists": false, "evidence_exists": false}, "protein_interacts_protein": {"edge_exists": false, "evidence_exists": false}}
}
```

### Tester verdict

PASS for `t_b85a55c1` / D1 Block 1 validation after the evidence/cache fix.

- Corrected complete-evidence gate passes for intended evidence-backed Block 1 relations: `pathway_contains_gene` and `molecule_targets_gene`.
- `molecule_targets_gene` evidence is no longer stale in the validation-accessible path: 41,239 rows, blank `source_dataset` rows = 0, stale `molecule_targets_protein` predicate/direction/source-record tokens = 0.
- Endpoint anti-joins are clean for `gene_interacts_gene`, `pathway_contains_gene`, and `molecule_targets_gene` in the accessible cache.
- Broad legacy `gene_interacts_gene` is excluded from the complete-evidence gate by accepted C1/R4 policy; the full audit still reports 642,150 TxGNN edges without evidence, but this is a documented policy exception rather than a new valid evidence backfill.
- Remaining risk: whole-KG coverage is still not validated because the canonical mount is unavailable and `.omoc/gcs-cache/kg-v2` is partial.
