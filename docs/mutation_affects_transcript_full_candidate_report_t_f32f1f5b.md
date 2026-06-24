# `mutation_affects_transcript` full-scale canonical-promotion candidate

Kanban task: `t_f32f1f5b`
Date: 2026-06-23
Relation: `mutation_affects_transcript`
OpenTargets release: Platform 26.03
Canonical writes: none

## Scope

This task rebuilds the `mutation_affects_transcript` candidate from all 25 OpenTargets 26.03 `variant` Parquet parts, replacing the previous first-part/25k smoke tranche as review input.

Only `mutation_affects_transcript` is staged here. The prior reviewer accepted this relation as source-native canonical edge material in principle, but rejected promotion of the smoke artifact because it was partial. This full-scale artifact preserves the same policy gates:

- source-native OpenTargets `variant.transcriptConsequences[].transcriptId` rows only;
- every emitted Sequence Ontology id must be in the strict allowed transcript-local SO allowlist from `docs/mutation_genomic_relations_promotion_policy.md`;
- `isEnsemblCanonical == true`;
- `x_id` anti-joins cleanly against canonical mutation nodes;
- `y_id` anti-joins cleanly against canonical transcript nodes;
- duplicate edge-key check is zero;
- edge/evidence support anti-joins are zero;
- no L2G/GWAS/association source leakage;
- staged artifact only, pending tester+reviewer approval before any canonical write.

## Artifacts

Local stage root:

```text
artifacts/staged/t_f32f1f5b_sql
```

Final staged Parquets:

```text
artifacts/staged/t_f32f1f5b_sql/edges/mutation_affects_transcript.parquet
artifacts/staged/t_f32f1f5b_sql/evidence/mutation_affects_transcript.parquet
artifacts/staged/t_f32f1f5b_sql/nodes/mutation.parquet
```

Machine-readable reports:

```text
artifacts/staged/t_f32f1f5b_sql/source_audit.json
artifacts/staged/t_f32f1f5b_sql/manifest.json
artifacts/staged/t_f32f1f5b_sql/validation.json
artifacts/reports/t_f32f1f5b_variant_urls.txt
artifacts/reports/t_f32f1f5b_sql_builder_summary.json
artifacts/reports/t_f32f1f5b_mutation_affects_transcript_full_sql_qa.json
artifacts/reports/t_f32f1f5b_mutation_affects_transcript_audit_edge_evidence.json
```

Builder/QA scripts used for this task:

```text
artifacts/reports/t_f32f1f5b_build_mutation_affects_transcript_sql.py
artifacts/reports/t_f32f1f5b_qa_mutation_affects_transcript_sql.py
```

The downloaded OpenTargets 26.03 variant cache is local working data:

```text
artifacts/cache/t_f32f1f5b/opentargets-26.03/variant/
```

## Counts

From `artifacts/reports/t_f32f1f5b_sql_builder_summary.json`:

| Metric | Count |
| --- | ---: |
| OpenTargets variant input rows | 7,432,549 |
| Canonical mutation matches | 2,589,092 |
| Distinct mutation x endpoints in staged edges | 2,312,815 |
| Distinct transcript y endpoints in staged edges | 40,939 |
| Staged edge rows | 2,599,922 |
| Staged evidence rows | 2,599,922 |
| Staged mutation node rows | 2,312,815 |

## QA gates

`artifacts/reports/t_f32f1f5b_mutation_affects_transcript_full_sql_qa.json` reports `passed: true`.

| Gate | Count |
| --- | ---: |
| duplicate edge keys | 0 |
| edges without evidence | 0 |
| evidence without edge | 0 |
| missing canonical mutation x endpoints | 0 |
| missing canonical transcript y endpoints | 0 |
| noncanonical transcript evidence rows | 0 |
| disallowed SO evidence rows | 0 |
| L2G/GWAS/association leakage rows | 0 |

Independent `manage_db.audit_edge_evidence` output (`artifacts/reports/t_f32f1f5b_mutation_affects_transcript_audit_edge_evidence.json`) also reports:

```json
{
  "ok": true,
  "relation_reports": {
    "mutation_affects_transcript": {
      "edge_rows": 2599922,
      "evidence_rows": 2599922,
      "edges_without_evidence": 0,
      "evidence_without_edge": 0,
      "ok": true
    }
  }
}
```

Canonical absence check after staging:

```text
absent edges/mutation_affects_transcript.parquet
absent evidence/mutation_affects_transcript.parquet
```

## Commands run

```bash
uv run python -m py_compile manage_db/build_staged_mutation_genomic_edges.py
uv run --group dev pytest tests/test_build_staged_mutation_genomic_edges.py tests/test_variant_enhancer_missing_edge_plan.py -q
# 6 passed in 0.40s

uv run python -m py_compile artifacts/reports/t_f32f1f5b_build_mutation_affects_transcript_sql.py
uv run python artifacts/reports/t_f32f1f5b_build_mutation_affects_transcript_sql.py \
  > artifacts/reports/t_f32f1f5b_sql_stdout.log \
  2> artifacts/reports/t_f32f1f5b_sql_stderr.log
# Parquet writes completed; the first integrated QA attempt failed only on a correlated DuckDB JSON/SO QA query after writing outputs.

uv run python artifacts/reports/t_f32f1f5b_qa_mutation_affects_transcript_sql.py \
  > artifacts/reports/t_f32f1f5b_qa_stdout.log \
  2> artifacts/reports/t_f32f1f5b_qa_stderr.log
# exit 0; wrote manifest.json, validation.json, and full QA report

uv run python -m manage_db.audit_edge_evidence \
  artifacts/staged/t_f32f1f5b_sql \
  --relations mutation_affects_transcript \
  --json --fail-on-missing \
  > artifacts/reports/t_f32f1f5b_mutation_affects_transcript_audit_edge_evidence.json
# exit 0
```

## Notes / residual risks

- This is a staged candidate only. It must not be copied to canonical `kg/v2/edges` or `kg/v2/evidence` until tester and reviewer approve.
- The SQL builder is scoped to `mutation_affects_transcript`; it intentionally does not rebuild `mutation_in_gene` or `mutation_overlaps_enhancer`.
- A prior Python row-loop attempt was stopped because nested evidence construction on a large part was too slow/high-memory. The final artifact was produced by DuckDB SQL over the local 25-part cache.
- The shared workspace has broken parent git discovery (`fatal: 'work/jkobject.github.io/.git' not recognized as a git repository`), so this task is delivered as staged artifacts/reports rather than a mergeable branch/PR.
