# REL Wave B protein-native mechanism tester report

Kanban task: `t_145b3cb9`
Parent builder task: `t_15e780b9`
Tester timestamp: 2026-06-23 16:35:13 CEST
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Verdict

FAIL / `tofix`: the builder handoff names staging artifacts and a machine-readable QA JSON, but those files/directories are absent from the shared workspace. Because the candidate edge/evidence Parquets are not available, the required endpoint anti-joins, edge/evidence support checks, duplicate edge-key checks, source-native metadata validation, and no-gene-projection checks cannot be independently reproduced.

## Expected builder artifacts from parent handoff

- `.omoc/reports/t_15e780b9_rel_wave_b_protein_native_qa.json`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/reactome-pathway-contains-protein/edges/pathway_contains_protein.parquet`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/reactome-pathway-contains-protein/evidence/pathway_contains_protein.parquet`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/molecule-targets-protein-chembl/edges/molecule_targets_protein.parquet`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/molecule-targets-protein-chembl/evidence/molecule_targets_protein.parquet`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/disease-associated-protein-uniprot/edges/disease_associated_protein.parquet`
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9/disease-associated-protein-uniprot/evidence/disease_associated_protein.parquet`

## Evidence collected

### Builder report present

`docs/rel_wave_b_protein_native_mechanism_candidate_report.md` exists and claims:

- `pathway_contains_protein`: 15,436 edges / 18,068 evidence rows, 0 endpoint anti-join misses, 0 edge/evidence support defects.
- `molecule_targets_protein`: 2,119 edges / 2,132 evidence rows, 0 endpoint anti-join misses, 0 edge/evidence support defects.
- `disease_associated_protein`: 3,243 edges / 35,839 evidence rows, 0 endpoint anti-join misses, 0 edge/evidence support defects.

These claims could not be reproduced because the Parquets and JSON report are missing.

### Missing files/directories

Commands run from `/Users/jkobject/.openclaw/workspace/work/txgnn`:

```bash
python - <<'PY'
from pathlib import Path
root=Path('/Users/jkobject/.openclaw/workspace/work/txgnn')
print('omoc exists', (root/'.omoc').exists())
PY
```

Observed: `omoc exists False`.

```bash
# searched under repo, /Users/jkobject/.openclaw, and /tmp for:
# rel-wave-b-20260623-t_15e780b9
# t_15e780b9_rel_wave_b_protein_native_qa.json
# reactome-pathway-contains-protein
# molecule-targets-protein-chembl
# disease-associated-protein-uniprot
```

Observed: zero hits for the expected Wave B staging root, QA JSON, or relation candidate directories.

`search_files` observations:

- `.omoc/reports/t_15e780b9_rel_wave_b_protein_native_qa.json`: file not found.
- `.omoc/staging/rel-wave-b-20260623-t_15e780b9`: path not found.
- no relation Parquets under `.omoc`; `.omoc` does not exist in the repo workspace.

### Canonical KG write check

Read-only `gsutil ls -l` checks against `gs://jouvencekb/kg/v2`:

```bash
for rel in pathway_contains_protein molecule_targets_protein disease_associated_protein; do
  gsutil ls -l "gs://jouvencekb/kg/v2/edges/${rel}.parquet" || true
  gsutil ls -l "gs://jouvencekb/kg/v2/evidence/${rel}.parquet" || true
done
```

Observed for all six canonical edge/evidence paths: `CommandException: One or more URLs matched no objects.`

This supports the builder claim that these three relations were not promoted to canonical KG. It does not validate the absent staging outputs.

## PASS/FAIL by relation

| Relation | Verdict | Reason |
| --- | --- | --- |
| `pathway_contains_protein` | FAIL / blocked by missing artifact | Expected staging root and Parquets absent; cannot rerun endpoint anti-joins, duplicate edge-key check, evidence support check, source metadata validation, or no-projection check. |
| `molecule_targets_protein` | FAIL / blocked by missing artifact | Expected staging root and Parquets absent; cannot validate ChEMBL protein-native endpoints/metadata or anti-join against molecule/protein nodes. |
| `disease_associated_protein` | FAIL / blocked by missing artifact | Expected staging root and Parquets absent; cannot validate UniProt/humsavar protein-native disease assertions, scoreless evidence metadata, or anti-join against protein/disease nodes. |

## Blockers for reviewer / builder

1. Re-materialize or attach the exact candidate staging tree under the shared workspace:
   `.omoc/staging/rel-wave-b-20260623-t_15e780b9/`.
2. Re-materialize or attach the machine-readable QA JSON:
   `.omoc/reports/t_15e780b9_rel_wave_b_protein_native_qa.json`.
3. Then rerun independent tester checks:
   - endpoint anti-joins against canonical pathway/molecule/protein/disease nodes;
   - edge/evidence support both directions;
   - duplicate `(x_id, relation, y_id)` or schema-specific edge-key checks;
   - anti-projection checks against canonical `pathway_contains_gene`, `molecule_targets_gene`, and `disease_associated_gene` rows;
   - metadata field presence/source-native values and row counts against the builder report;
   - canonical write check.

## Reviewer note

The only positive verification possible in this run is that the canonical GCS paths for the three protein relations are absent, so no unintended canonical promotion was detected. The candidate outputs themselves are not testable until the missing staging artifacts are restored.
