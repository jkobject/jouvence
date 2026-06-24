# Mutation genomic direct bounded candidate report

Kanban task: `t_8eeb17bc`
Date: 2026-06-23
Policy source: `docs/mutation_genomic_relations_promotion_policy.md` (`t_60b3e504`)
Builder: `manage_db/build_staged_mutation_genomic_edges.py`

## Scope and promotion stance

This report prepares staged canonical-promotion candidates for the Wave A genomic-direct relations without writing to canonical `kg/v2/edges` or `kg/v2/evidence`.

The prior dense pilot is not promoted as-is. This build applies the stricter policy gates:

- `mutation_in_gene`: OpenTargets VEP `transcriptConsequences[].targetId` only after allowed transcript/gene-local Sequence Ontology filtering; upstream/downstream/intergenic/regulatory rows excluded; canonical mutation/gene endpoints required. This remains staged because an independent gene-coordinate containment table has not been selected for the final containment proof.
- `mutation_affects_transcript`: OpenTargets VEP `transcriptConsequences[].transcriptId` only after allowed transcript-local consequence filtering and `isEnsemblCanonical == true`; canonical mutation/transcript endpoints required.
- `mutation_overlaps_enhancer`: exact point-to-interval overlap against current canonical enhancer nodes only after the downstream mutation-support gate; overlap evidence is contextual and non-causal.

No L2G/GWAS disease/gene association semantics are used to populate `mutation_in_gene` or `mutation_affects_transcript`.

## Staged candidate artifacts

Durable local stage root, preserved after reviewer acceptance of `t_cd9d5107` by cleanup task `t_20eca510`:

```text
artifacts/staged/t_cd9d5107/mutation-genomic-direct-bounded-20260623-t_8eeb17bc-smoke
```

Remote staging root (staging only; no canonical `kg/v2/edges` or `kg/v2/evidence` writes):

```text
gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/
```

Machine-readable reports and durable manifest:

```text
artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_qa.json
artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_audit_edge_evidence.json
artifacts/reports/t_8eeb17bc_variant_urls.txt
artifacts/reports/t_cd9d5107_mutation_genomic_direct_smoke_durable_manifest.json
artifacts/reports/t_cd9d5107_gcs_listing.txt
```

Legacy `.omoc/staging/mutation-genomic-direct-bounded-20260623-t_8eeb17bc-smoke/` was only the scratch/restoration location. Downstream workers should use the durable local or GCS staging roots above.

This run used the first OpenTargets Platform 26.03 `variant` part with `--max-variants 25000` as a bounded staged candidate/smoke tranche. It is intentionally named `smoke` and must not be represented as the full 25-part OpenTargets rebuild.

Source part:

```text
https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/variant/part-00000-489af5f8-1f32-49c6-88b5-2f5c71927329-c000.snappy.parquet
```

Canonical KG endpoint/support root used for QA:

```text
/Users/jkobject/mnt/gcs/jouvencekb-kg/v2
```

## Build counts

From `manifest.json`:

| Metric | Count |
| --- | ---: |
| Input variants | 25,000 |
| Canonical mutation matches | 11,780 |
| Exploded transcript consequence rows | 762,741 |
| Excluded upstream/downstream/intergenic/regulatory rows | 751,072 |
| Rows after allowed consequence filter | 11,669 |
| Rows after canonical transcript filter | 11,669 |
| Staged mutation nodes | 11,780 |
| Enhancer interval slice scanned | 115,543 |

Staged edge/evidence rows:

| Relation | Edges | Evidence | Endpoint rejects |
| --- | ---: | ---: | ---: |
| `mutation_in_gene` | 11,669 | 11,669 | gene rejects: 0 |
| `mutation_affects_transcript` | 11,669 | 11,669 | transcript rejects: 0 |
| `mutation_overlaps_enhancer` | 1,670,937 | 1,670,937 | enhancer anti-join missing: 0 |

## QA results

DuckDB endpoint/support QA (`artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_qa.json`) passed for all three relations:

| Relation | Duplicate edge keys | Edges without evidence | Evidence without edge | Missing mutation x | Missing y endpoint |
| --- | ---: | ---: | ---: | ---: | ---: |
| `mutation_in_gene` | 0 | 0 | 0 | 0 | 0 |
| `mutation_affects_transcript` | 0 | 0 | 0 | 0 | 0 |
| `mutation_overlaps_enhancer` | 0 | 0 | 0 | 0 | 0 |

`manage_db.audit_edge_evidence` also passed on the stage root (`artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_audit_edge_evidence.json`):

| Relation | Edge rows | Evidence rows | Edges without evidence | Evidence without edge |
| --- | ---: | ---: | ---: | ---: |
| `mutation_in_gene` | 11,669 | 11,669 | 0 | 0 |
| `mutation_affects_transcript` | 11,669 | 11,669 | 0 | 0 |
| `mutation_overlaps_enhancer` | 1,670,937 | 1,670,937 | 0 | 0 |

Targeted tests:

```text
uv run python -m py_compile manage_db/build_staged_mutation_genomic_edges.py
uv run --group dev pytest tests/test_build_staged_mutation_genomic_edges.py tests/test_variant_enhancer_missing_edge_plan.py -q
# 6 passed in 0.25s
```

## Cleanup/staging verification (`t_20eca510`)

After reviewer `t_1597cf7a` accepted the restored `t_cd9d5107` artifacts, cleanup task `t_20eca510` copied the accepted smoke outputs out of legacy `.omoc` scratch into durable workspace paths and remote GCS staging.

Local durable verification manifest:

```text
artifacts/reports/t_cd9d5107_mutation_genomic_direct_smoke_durable_manifest.json
```

The manifest records SHA256, byte size, JSON readability, and Parquet row counts for the durable local copy. Key row-count checks:

| Artifact | Rows |
| --- | ---: |
| `edges/mutation_in_gene.parquet` | 11,669 |
| `edges/mutation_affects_transcript.parquet` | 11,669 |
| `edges/mutation_overlaps_enhancer.parquet` | 1,670,937 |
| `evidence/mutation_in_gene.parquet` | 11,669 |
| `evidence/mutation_affects_transcript.parquet` | 11,669 |
| `evidence/mutation_overlaps_enhancer.parquet` | 1,670,937 |
| `nodes/mutation.parquet` | 11,780 |

GCS staging/readback verification:

```text
gsutil -m rsync -r artifacts/staged/t_cd9d5107/mutation-genomic-direct-bounded-20260623-t_8eeb17bc-smoke gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/smoke
gsutil -m cp artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_qa.json artifacts/reports/t_8eeb17bc_mutation_genomic_bounded_smoke_audit_edge_evidence.json artifacts/reports/t_8eeb17bc_variant_urls.txt artifacts/reports/t_cd9d5107_mutation_genomic_direct_smoke_durable_manifest.json gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/reports/
gsutil ls -l -r gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/** > artifacts/reports/t_cd9d5107_gcs_listing.txt
gsutil cat gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/smoke/validation.json | python -m json.tool
gsutil cat gs://jouvencekb/kg/staging/rel-wave-a/mutation-genomic-direct/t_cd9d5107/reports/t_cd9d5107_mutation_genomic_direct_smoke_durable_manifest.json | python -m json.tool
```

The final GCS listing contains 17 objects totaling 248,475,277 bytes (236.96 MiB), including the smoke Parquets, copied QA reports, durable audit, manifest, and this Markdown report. JSON readback succeeded for `smoke/validation.json`, `reports/t_cd9d5107_durable_audit_edge_evidence.json`, and the durable manifest. No canonical `gs://jouvencekb/kg/v2/edges` or `gs://jouvencekb/kg/v2/evidence` writes were performed.

## `mutation_overlaps_enhancer` canonical-material decision

`mutation_overlaps_enhancer` should remain staged/contextual, not canonical edge material from this smoke tranche.

Reviewer decision (`t_289a2e9b`, recorded by tofix `t_59b13c08`): the bounded downstream-supported gate is useful for staging/context, and all mechanical QA passed, but the density is still high: 11,780 supported canonical mutation matches produce 1,670,937 deduplicated enhancer-overlap edges from one OT variant part. This relation is non-causal interval context; it does not prove altered enhancer activity or target-gene regulation. Keep it feature/context/staging unless a new reviewed policy selects stronger allele-specific regulatory/enhancer-activity evidence with source-native regulatory semantics, density controls, endpoint anti-joins, duplicate-key checks, edge/evidence support audits, and explicit separation from L2G/GWAS association relations.

Unbounded all-variant enhancer overlap should remain feature/context only and must not be promoted.

## Residual risks and next gates

1. This is a first-part bounded staged candidate/smoke tranche, not the full 25-part OpenTargets rebuild requested by the policy plan. Full-scale execution should reuse the same gates but may produce very large enhancer-overlap outputs.
2. `mutation_in_gene` is policy-filtered VEP gene-local context, not independently proven physical containment. Final canonical promotion should either select a trusted gene-coordinate interval source or keep this relation staged.
3. `mutation_affects_transcript` currently requires `isEnsemblCanonical == true`; noncanonical transcript consequences are intentionally excluded from graph edges and retained only as source context if separately stored.
4. The builder writes staged artifacts only. No canonical coverage docs were updated and no canonical KG files were written.

## Reproduction commands

```bash
python - <<'PY' > .omoc/reports/t_8eeb17bc_variant_urls.txt
import urllib.request, re
url='https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/variant/'
html=urllib.request.urlopen(url, timeout=30).read().decode('utf-8','ignore')
for name in re.findall(r'href="([^"]+\\.parquet)"', html):
    print(url+name)
PY

FIRST_URL=$(head -n 1 .omoc/reports/t_8eeb17bc_variant_urls.txt)
uv run python -m manage_db.build_staged_mutation_genomic_edges \
  --variant-file "$FIRST_URL" \
  --kg-cache-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --stage-root .omoc/staging/mutation-genomic-direct-bounded-20260623-t_8eeb17bc-smoke \
  --max-variants 25000

uv run python -m manage_db.audit_edge_evidence \
  .omoc/staging/mutation-genomic-direct-bounded-20260623-t_8eeb17bc-smoke \
  --relations mutation_in_gene mutation_affects_transcript mutation_overlaps_enhancer \
  --json --fail-on-missing
```

Note: the first build command timed out after writing staged Parquets and `manifest.json`, before writing `validation.json`. The DuckDB QA report and copied stage `validation.json` provide the completed endpoint/evidence validation for the written artifacts.
