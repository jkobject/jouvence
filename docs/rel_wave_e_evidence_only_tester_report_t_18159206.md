# REL Wave E evidence-only pharmacology QA tester report

Tester task: `t_18159206`
Builder task: `t_cd7fec1f`
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
Date: 2026-06-23

## Verdict

PASS for REL-WAVE-E evidence-only pharmacology candidates.

This tester run independently recomputed row counts, distinct tuple-key support, semantic distributions, staged snapshot vs current canonical edge-key equality, and candidate file inventory from the actual Parquet files. The audit used the current canonical KG FUSE root `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`, not only the builder's staged snapshots.

Machine-readable tester audit:

- `artifacts/reports/t_18159206_rel_wave_e_evidence_only_audit.json`

Builder inputs checked:

- Markdown report: `docs/rel_wave_e_evidence_only_backfill_candidate_report_t_cd7fec1f.md`
- QA JSON: `.omoc/reports/t_cd7fec1f_rel_wave_e_evidence_only_qa.json`
- Manifest: `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/manifest.json`

## Commands / environment

Executed from `/Users/jkobject/.openclaw/workspace/work/txgnn` using the repo uv environment:

```bash
uv run python - <<'PY'
# independent DuckDB/PyArrow audit; output written to
# artifacts/reports/t_18159206_rel_wave_e_evidence_only_audit.json
PY
```

Relevant environment:

- Host: macOS
- Canonical KG root: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`
- Candidate directory: `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f`

## File inventory / placeholder edge check

PASS.

Candidate Parquet inventory contains only:

- `evidence/molecule_synergizes_molecule.parquet`
- `evidence/molecule_treats_disease.parquet`
- `source_edges/molecule_synergizes_molecule.parquet`
- `source_edges/molecule_treats_disease.parquet`
- `source_edges/molecule_contraindicates_disease.parquet`

No `edges/` candidate Parquets were present. The `source_edges/` files are canonical edge snapshots used for support checks, not proposed placeholder or overwrite outputs. Manifest also reports `canonical_write_claimed=false`, `evidence_only=true`, and `edge_outputs_written=[]`.

Canonical evidence files for the three targeted relations were absent at the current canonical FUSE root before promotion:

- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_synergizes_molecule.parquet`: absent
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_treats_disease.parquet`: absent
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/evidence/molecule_contraindicates_disease.parquet`: absent

## `molecule_synergizes_molecule`

PASS.

Counts recomputed from actual Parquets:

| Metric | Count |
| --- | ---: |
| Candidate evidence rows | 2,672,628 |
| Candidate evidence distinct `edge_key` | 2,672,628 |
| Candidate evidence distinct tuple keys | 2,672,628 |
| Source edge snapshot rows | 2,672,628 |
| Source edge snapshot distinct tuple keys | 2,672,628 |
| Current canonical edge rows | 2,672,628 |
| Current canonical edge distinct tuple keys | 2,672,628 |

Support checks:

| Check | Count |
| --- | ---: |
| Evidence keys without current canonical edge | 0 |
| Current canonical edge keys with evidence | 2,672,628 |
| Current canonical edge keys without evidence | 0 |
| Snapshot keys not in current canonical | 0 |
| Current canonical keys not in snapshot | 0 |

Quality checks were all zero: wrong relation rows, wrong endpoint type rows, blank endpoints, missing `edge_key`, and `edge_key` mismatch rows.

Semantic checks passed:

- Candidate evidence `predicate`: `synergistic interaction` for 2,672,628 rows.
- Candidate evidence `source`: `TxGNN` for 2,672,628 rows.
- Candidate evidence `source_dataset`: `TxGNN Dataverse kg.csv datafile 7144484 / DrugBank drug_drug` for 2,672,628 rows.
- Candidate evidence `evidence_type`: `database_record` for 2,672,628 rows.
- Source edge snapshot `display_relation`: `synergizes with` for 2,672,628 rows.

Interpretation: the candidate is a complete evidence-only support file for the current canonical `molecule_synergizes_molecule` edge-key set and preserves the interaction/effect label plus source metadata. No evidence-without-edge keys were found.

## `molecule_treats_disease`

PASS.

Counts recomputed from actual Parquets:

| Metric | Count |
| --- | ---: |
| Candidate evidence rows | 481 |
| Candidate evidence distinct `edge_key` | 481 |
| Candidate evidence distinct tuple keys | 481 |
| Source edge snapshot rows | 14,135 |
| Source edge snapshot distinct tuple keys | 14,135 |
| Current canonical edge rows | 14,135 |
| Current canonical edge distinct tuple keys | 14,135 |

Support checks:

| Check | Count |
| --- | ---: |
| Evidence keys without current canonical edge | 0 |
| Current canonical edge keys with evidence | 481 |
| Current canonical edge keys without this candidate evidence | 13,654 |
| Snapshot keys not in current canonical | 0 |
| Current canonical keys not in snapshot | 0 |

Quality checks were all zero: wrong relation rows, wrong endpoint type rows, blank endpoints, missing `edge_key`, and `edge_key` mismatch rows.

Semantic checks passed:

- Candidate evidence `source`: `OpenTargets` for 481 rows.
- Candidate evidence `source_dataset`: `clinical_indication` for 481 rows.
- Candidate evidence `evidence_type`: `clinical_indication` for 481 rows.
- Candidate evidence `direction`: `positive_indication` for 481 rows.
- Candidate evidence predicates are clinical-indication stages only:
  - `clinical indication; stage=APPROVAL`: 306
  - `clinical indication; stage=PHASE_3`: 107
  - `clinical indication; stage=PHASE_2`: 36
  - `clinical indication; stage=UNKNOWN`: 17
  - `clinical indication; stage=PHASE_2_3`: 6
  - `clinical indication; stage=PHASE_1`: 5
  - `clinical indication; stage=PREAPPROVAL`: 2
  - `clinical indication; stage=IND`: 1
  - `clinical indication; stage=PHASE_1_2`: 1

Interpretation: the candidate is a partial evidence-only backfill for 481 existing canonical `molecule_treats_disease` edge keys. The remaining 13,654 canonical edge keys are unsupported by this specific evidence candidate, as documented by the builder. No evidence-without-edge keys were found.

## `molecule_contraindicates_disease`

PASS for source-selection-only gate.

Counts recomputed from actual Parquets:

| Metric | Count |
| --- | ---: |
| Candidate contraindication evidence file exists | 0 / false |
| Source edge snapshot rows | 30,675 |
| Source edge snapshot distinct tuple keys | 30,675 |
| Current canonical edge rows | 30,675 |
| Current canonical edge distinct tuple keys | 30,675 |
| Snapshot keys not in current canonical | 0 |
| Current canonical keys not in snapshot | 0 |

The canonical contraindication edge snapshot has `display_relation=contraindication` for 30,675 rows. No `evidence/molecule_contraindicates_disease.parquet` candidate was produced.

Interpretation: positive OpenTargets `clinical_indication` rows were not reused for contraindications. The builder report correctly leaves contraindication evidence as future source-selection work requiring explicit contraindication predicates.

## Builder report count validation

PASS.

The builder Markdown report and `.omoc` QA JSON row counts match the actual staged/candidate files and current canonical edge files for all checked metrics:

- `molecule_synergizes_molecule`: 2,672,628 candidate evidence rows and 2,672,628 canonical edge rows.
- `molecule_treats_disease`: 481 candidate evidence rows and 14,135 canonical edge rows; 13,654 current canonical edge keys not supported by this partial evidence candidate.
- `molecule_contraindicates_disease`: 30,675 current canonical edge rows and no evidence candidate.

## Blockers / reviewer notes

No tester blockers found.

Reviewer should still treat this as evidence-only staging approval, not canonical promotion authorization. Canonical writes remain gated by reviewer/owner approval and an explicit promotion task.
