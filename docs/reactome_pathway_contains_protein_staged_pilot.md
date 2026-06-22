# Reactome `pathway_contains_protein` staged pilot

_Date: 2026-06-22_

## Scope

This pilot revisits `pathway_contains_protein` after the Block 1 `pathway_contains_gene` audit. It does **not** project existing gene-level pathway membership. It uses Reactome's source-native `UniProt2Reactome_All_Levels.txt` export, whose source rows provide direct UniProt protein endpoints and Reactome pathway IDs.

## Source

- Source: Reactome
- Source dataset: `UniProt2Reactome_All_Levels`
- URL: `https://reactome.org/download/current/UniProt2Reactome_All_Levels.txt`
- Release used: `2026-03-23` from `Last-Modified: Mon, 23 Mar 2026 22:41:11 GMT`
- Raw cache: `.omoc/raw/reactome/uniprot2reactome_all_levels/2026-03-23/UniProt2Reactome_All_Levels.txt`
- License note: Reactome license should be re-reviewed before canonical promotion.

The source TSV columns are UniProt accession, Reactome ID, Reactome URL, pathway name, Reactome evidence code, and species.

## Policy

Accepted rows must satisfy all of the following:

1. `species == "Homo sapiens"` and `reactome_id` starts with `R-HSA-`.
2. Reactome pathway ID exists in the active KG pathway nodes.
3. UniProt accession maps directly and unambiguously to exactly one KG `protein` node through `nodes/protein.uniprot_id`.
4. No ENSG/NCBI gene endpoint is used, and no row is generated from `pathway_contains_gene`.

Rejected rows are materialized with reason codes rather than projected through gene IDs or ambiguous protein mappings.

## Staged artifacts

Local staging root:

- `.omoc/staging/reactome-pathway-contains-protein-20260622-t_9d36e82e/`

Artifacts:

- `edges/pathway_contains_protein.parquet`
- `evidence/pathway_contains_protein.parquet` (extended evidence payload with source-native fields)
- `evidence_canonical/pathway_contains_protein.parquet` (canonical evidence columns for compatibility)
- `mappings/reactome_pathway_contains_protein_rejected.parquet`
- `validation/reactome_pathway_contains_protein_report.json`
- `validation/duckdb_endpoint_support_validation.json`
- `audit_edge_evidence.json`

Remote staging upload:

- `gs://jouvencekb/kg/v2/staging/reactome-pathway-contains-protein-20260622-t_9d36e82e/`

## Counts

| Metric | Count |
| --- | ---: |
| Human R-HSA source rows audited | 159,114 |
| Staged distinct `pathway_contains_protein` edges | 15,436 |
| Staged evidence rows | 18,068 |
| Rejected source rows | 141,046 |

Rejected source rows:

| Reason | Count |
| --- | ---: |
| `ambiguous_uniprot_to_protein` | 117,396 |
| `missing_pathway_node` | 14,609 |
| `unmapped_uniprot_to_protein` | 9,041 |

Evidence code counts in accepted rows:

| Reactome evidence code | Evidence rows |
| --- | ---: |
| `TAS` | 13,731 |
| `IEA` | 4,337 |

## Validation

DuckDB validation on the staged root:

| Check | Result |
| --- | ---: |
| Edge rows | 15,436 |
| Evidence rows | 18,068 |
| Distinct edge keys | 15,436 |
| Edges without evidence | 0 |
| Evidence without edge | 0 |
| Missing pathway node endpoints | 0 |
| Missing protein node endpoints | 0 |
| Edge endpoint types | only `pathway -> protein` |
| Evidence endpoint types | only `pathway -> protein` |

`manage_db.audit_edge_evidence` also passed:

```json
{
  "ok": true,
  "relation_reports": {
    "pathway_contains_protein": {
      "edge_rows": 15436,
      "evidence_rows": 18068,
      "edges_without_evidence": 0,
      "evidence_without_edge": 0,
      "ok": true
    }
  }
}
```

## Implementation

Implemented builder:

- `manage_db/build_reactome_pathway_protein_membership.py`

Tests:

- `tests/test_build_reactome_pathway_protein_membership.py`

Commands run:

```bash
uv run --group dev pytest tests/test_build_reactome_pathway_protein_membership.py -q
uv run --group dev pytest tests/test_kg_schema_cleanup.py tests/test_backfill_edge_evidence.py tests/test_kg_evidence.py -q
uv run python -m manage_db.build_reactome_pathway_protein_membership \
  --protein-nodes .omoc/gcs-cache/kg-v2/nodes/protein.parquet \
  --pathway-nodes .omoc/gcs-cache/kg-v2/nodes/pathway.parquet \
  --output-dir .omoc/staging/reactome-pathway-contains-protein-20260622-t_9d36e82e
uv run --with duckdb python - <<'PY'
# endpoint anti-joins and evidence support checks
PY
uv run python -m manage_db.audit_edge_evidence \
  .omoc/staging/reactome-pathway-contains-protein-20260622-t_9d36e82e \
  --relations pathway_contains_protein --json
```

## Promotion recommendation

Keep this staged-only until review confirms the desired Reactome all-level semantics. The builder is conservative on protein endpoint mapping, but the accepted rows include Reactome all-level pathway annotations, not just leaf physical participants. Canonical promotion should explicitly approve that membership type or switch to a narrower Reactome export/API traversal.
