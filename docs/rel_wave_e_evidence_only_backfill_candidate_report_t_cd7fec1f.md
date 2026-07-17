# REL Wave E evidence-only pharmacology backfill candidates

Kanban task: `t_cd7fec1f`  
Parent REL-PLAN: `t_cf77187d`  
Generated: 2026-06-23  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Scope and non-goals

This builder task prepares **evidence-only** canonical update candidates for relations that already have canonical edge files:

- `molecule_synergizes_molecule`
- `molecule_treats_disease`

It also records source-selection requirements for `molecule_contraindicates_disease`.

No placeholder edges were created. No canonical files were written or promoted. The candidate output consists only of evidence parquet files copied from previously staged evidence backfills plus local snapshots of the canonical edge files used for support checks.

## Candidate artifact paths

Candidate directory:

- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/`

Evidence-only candidate files:

- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/evidence/molecule_synergizes_molecule.parquet`
- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/evidence/molecule_treats_disease.parquet`

Canonical edge snapshots used for support checks:

- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/source_edges/molecule_synergizes_molecule.parquet`
- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/source_edges/molecule_treats_disease.parquet`
- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/source_edges/molecule_contraindicates_disease.parquet`

Machine-readable QA:

- `.omoc/reports/t_cd7fec1f_rel_wave_e_evidence_only_qa.json`

Manifest:

- `artifacts/staged/rel_wave_e_evidence_only_20260623_t_cd7fec1f/manifest.json`

## Source inputs

The local `/mnt/gcs/jouvencekb/kg/v2` FUSE mount was not available during this run, so inputs were copied read-only with `gcloud storage cp`.

Canonical edge snapshots:

- `gs://jouvencekb/kg/v2/edges/molecule_synergizes_molecule.parquet`
- `gs://jouvencekb/kg/v2/edges/molecule_treats_disease.parquet`
- `gs://jouvencekb/kg/v2/edges/molecule_contraindicates_disease.parquet`

Staged evidence inputs:

- `gs://jouvencekb/kg/v2/staging/molecule-synergizes-evidence-20260622-t_4e12f7c7/evidence/molecule_synergizes_molecule.parquet`
- `gs://jouvencekb/kg/v2/staging/opentargets-clinical-drug-evidence-20260622-t_ceee5d53/evidence/molecule_treats_disease.parquet`

Existing canonical evidence files were absent for all three targeted relations at the time of listing:

- `gs://jouvencekb/kg/v2/evidence/molecule_synergizes_molecule*`: no object matched
- `gs://jouvencekb/kg/v2/evidence/molecule_treats_disease*`: no object matched
- `gs://jouvencekb/kg/v2/evidence/molecule_contraindicates_disease*`: no object matched

## QA summary

### `molecule_synergizes_molecule`

Candidate semantics: drug-combination synergistic interaction evidence.

Counts and support:

| Metric | Value |
| --- | ---: |
| Canonical edge rows | 2,672,628 |
| Canonical edge keys | 2,672,628 |
| Candidate evidence rows | 2,672,628 |
| Candidate evidence keys | 2,672,628 |
| Evidence keys without canonical edge | 0 |
| Canonical edge keys supported by candidate evidence | 2,672,628 |
| Canonical edge keys not supported by this candidate | 0 |
| Wrong relation rows | 0 |
| Wrong endpoint type rows | 0 |
| Null/blank endpoint rows | 0 |
| Missing `edge_key` rows | 0 |
| Evidence x IDs missing from cached molecule nodes | 0 |
| Evidence y IDs missing from cached molecule nodes | 0 |

Semantic distributions:

- Canonical edge `display_relation`: `synergizes with` for 2,672,628 rows.
- Evidence `predicate`: `synergistic interaction` for 2,672,628 rows.
- Evidence `source`: `TxGNN` for 2,672,628 rows.
- Evidence `source_dataset`: `TxGNN Dataverse kg.csv datafile 7144484 / DrugBank drug_drug` for 2,672,628 rows.
- Evidence `evidence_type`: `database_record` for 2,672,628 rows.

Interpretation: this candidate is a complete evidence-only backfill for the current canonical `molecule_synergizes_molecule` edge key set and preserves the drug-combination effect semantics required by the relation policy. It does not add or rewrite edges.

### `molecule_treats_disease`

Candidate semantics: positive OpenTargets clinical indication evidence only.

Counts and support:

| Metric | Value |
| --- | ---: |
| Canonical edge rows | 14,135 |
| Canonical edge keys | 14,135 |
| Candidate evidence rows | 481 |
| Candidate evidence keys | 481 |
| Evidence keys without canonical edge | 0 |
| Canonical edge keys supported by candidate evidence | 481 |
| Canonical edge keys not supported by this candidate | 13,654 |
| Wrong relation rows | 0 |
| Wrong endpoint type rows | 0 |
| Null/blank endpoint rows | 0 |
| Missing `edge_key` rows | 0 |
| Evidence x IDs missing from cached molecule nodes | 0 |
| Evidence y IDs missing from cached disease nodes | 0 |

Canonical edge display relations in the edge snapshot:

- `indication`: 9,355 rows
- `off-label use`: 2,476 rows
- `linked to`: 2,304 rows

Candidate evidence distributions:

- Evidence `source`: `OpenTargets` for 481 rows.
- Evidence `source_dataset`: `clinical_indication` for 481 rows.
- Evidence `evidence_type`: `clinical_indication` for 481 rows.
- Evidence `direction`: `positive_indication` for 481 rows.
- Predicate/stage counts:
  - `clinical indication; stage=APPROVAL`: 306
  - `clinical indication; stage=PHASE_3`: 107
  - `clinical indication; stage=PHASE_2`: 36
  - `clinical indication; stage=UNKNOWN`: 17
  - `clinical indication; stage=PHASE_2_3`: 6
  - `clinical indication; stage=PHASE_1`: 5
  - `clinical indication; stage=PREAPPROVAL`: 2
  - `clinical indication; stage=IND`: 1
  - `clinical indication; stage=PHASE_1_2`: 1

Interpretation: this candidate is a partial evidence-only backfill for the subset of current canonical `molecule_treats_disease` edges with staged OpenTargets positive clinical indication evidence. It supports 481 existing canonical edge keys and leaves 13,654 canonical edge keys unsupported by this specific candidate. It does not add or rewrite edges and must not be interpreted as complete evidence coverage for all canonical `molecule_treats_disease` edges.

## `molecule_contraindicates_disease` source-selection note

Canonical `molecule_contraindicates_disease` edges exist in the snapshot:

- rows: 30,675
- distinct keys: 30,675

No contraindication evidence candidate was produced in this Wave E builder run. Positive clinical indication rows from OpenTargets are evidence for `molecule_treats_disease` only and were deliberately not reused for `molecule_contraindicates_disease`.

Acceptable source-selection directions for a future contraindication-specific evidence task:

1. Structured product-label / curated drug-label contraindication fields.
2. OpenTargets or any other source table only if the source row explicitly labels a contraindication predicate, not a positive indication or off-label use.
3. DrugBank, ChEMBL, or other curated records only when the source predicate is contraindication-specific and preserves disease/molecule mappings and provenance.

Explicitly rejected for this Wave E evidence candidate:

- OpenTargets positive `clinical_indication` rows used here for `molecule_treats_disease`.
- TxGNN broad positive treats/indication rows.

## Tester checklist

An independent tester should verify:

1. Re-run key support checks from `.omoc/reports/t_cd7fec1f_rel_wave_e_evidence_only_qa.json` against the current canonical edge files.
2. Confirm evidence-only candidate files are the only proposed promotion files and that no edge parquet is proposed for canonical overwrite.
3. Confirm `molecule_synergizes_molecule` evidence preserves synergistic drug-combination semantics and has 0 evidence-without-edge keys.
4. Confirm `molecule_treats_disease` evidence has `direction=positive_indication`, `source=OpenTargets`, `source_dataset=clinical_indication`, and is not reused for contraindications.
5. Confirm the contraindication note remains source-selection only unless a contraindication-specific source is provided.

## Promotion status

Status: builder candidate ready for tester/reviewer gates.

This report does not claim canonical promotion. It only identifies evidence-only candidate outputs that support existing canonical edge keys and separates contraindication-specific evidence requirements from positive indication evidence.
