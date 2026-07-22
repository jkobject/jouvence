# 04 — Relations

_Status snapshot: 2026-07-22 15:18 CEST._

Kanban board `txgnn` remains the live source of truth; older relation counts below are retained only where explicitly dated.

## Inferred edges / derived links

New user-requested analysis:

- `t_f0ad9dff` — `INFERRED-EDGES-POLICY`: analyze relation-chain templates for obvious inferred links from the KG.
- `t_ee00835b` — validate inferred-edge policy/prototype counts and leakage guardrails.
- `t_af066273` — review inferred-edge policy and first-family recommendation.

Definition: inferred links must remain labeled/separate from observed canonical edges, with explicit evidence/provenance and GNN leakage guardrails. Do not promote inferred candidates into observed canonical relation files by default.


## Current source of truth

- `t_0b1f53d9` — relation audit: `validated`/reviewed.
- `t_c07b8b57` — dataset/paper graph disconnection: `validated` policy/export guardrail.
  - Decision: `dataset` and `paper` nodes/relations are provenance/catalog metadata only and must be excluded from training/inference graph adjacency by default.
  - `t_9ad833bf` / `t_fa4e9f85` accepted the backup/checksum gate for `nodes/dataset.parquet`, `nodes/paper.parquet`, `edges/dataset_contains_cell_line.parquet`, and `edges/dataset_contains_tissue.parquet`.
  - `t_d97c4547` / reviewer `t_dccaa7d4`: `validated`; selected the reversible retain-with-labels option, adding canonical policy sidecars at `metadata/dataset_paper_graph_policy_t_d97c4547.{json,md}` and leaving the affected Parquets in place as metadata-only/non-training inventory.
- `t_9c86ca89` / reviewer `t_cc1dd3c6` — literature paper/author/citation policy: `validated`.
  - Decision: keep publication identifiers as evidence metadata in the biomedical KG; if a Paper/Author/Citation layer is retained, store it as a separate `literature_index` namespace/export, not default TxGNN training adjacency.
  - Current canonical `nodes/paper.parquet` has 2,958,199 OpenTargets-sourced PMID rows; no canonical `paper_cites_paper` or `paper_produced_dataset` edge files exist. OpenAlex is the preferred source for any future metadata-only literature index; large ingest requires explicit approval.
- Approved docs:
  - `docs/kg_schema_overview.md`
  - `docs/relation_coverage_current.md`
  - `docs/dataset_paper_graph_disconnection_t_c07b8b57.md`
  - `docs/literature_metadata_policy_t_9c86ca89.md`
  - `reproduce/15_kg_schema_overview.ipynb`

Counts:

- 67 active declared relations
- 40 canonical active edge relations, including three `canonical promoted`/`review-required` relations awaiting independent acceptance
- 27 declared relations not canonical yet
- 18 staged-only/deferred
- 5 schema-only/missing

## Prioritized relation plan

- `t_cf77187d` — relation backlog/fanout: `design done`.
- `docs/relation_backlog_prioritized.md` exists.

## Mutation-specific path

- `t_60b3e504` — mutation policy: `design done`.
- `t_79f8684d` — 25k policy-aware staged tranche: `pilot accepted`/`staged-only` for QA only; not canonical; not full all-part rebuild.
- `t_f32f1f5b` — all-25-part `mutation_affects_transcript` staged candidate accepted after validation/review.
- `t_225ae18c` — `mutation_affects_transcript` canonical promotion completed and independently accepted.
- `t_1cfcd48f` — `mutation_in_gene` relation-specific canonical promotion completed from full all-25-part containment-gated candidate (`t_2bb8e7de`) and independently accepted by consolidated reviewer `t_2d1f767d`. Canonical paths: `gs://jouvencekb/kg/v2/edges/mutation_in_gene.parquet`, `gs://jouvencekb/kg/v2/evidence/mutation_in_gene.parquet`, and `gs://jouvencekb/kg/v2/proof/mutation_in_gene_containment_proof.parquet`. Report: `docs/mutation_in_gene_canonical_promotion_t_1cfcd48f.md`.
- `mutation_overlaps_enhancer` — coordinate-overlap alone remains context/support-only and not canonical observed regulatory evidence. `t_00551bc3` relation-specifically promoted the reviewed support-gated `t_73c67c1b` candidate with 1,664,278 edge/evidence rows; consolidated reviewer `t_2d1f767d` independently accepted the immutable canonical revision. Report: `docs/mutation_overlaps_enhancer_canonical_promotion_t_00551bc3.md`.
- `t_4b1227b3` — canonical promotion only after relation-specific explicit review acceptance; not a blanket genomic-direct promotion.

## Other active relation waves

- Wave B protein-native mechanisms ended **rejected** by `t_c3eb09e3`: required staged Parquets and machine-readable QA were unavailable for independent reproduction; no promotion-readiness credit.
- Wave C pharmacology/cell-line context: `t_a7c7a5d1` accepted staged promotion readiness for three cell-line relations; no canonical write is claimed.
- Wave E evidence-only pharmacology: `t_fcb5b69f` accepted evidence-update readiness for synergy and the bounded 481-key positive treatment subset; no canonical write is claimed, and contraindication remains source-selection-only.

## Clinical trial support evidence/features

- `t_c4f67957` — ClinicalTrials.gov source-backed production candidate for the selected OpenTargets clinicalReportIds/NCT seed: accepted as `staged production candidate`, not global all-CTGov coverage.
- `t_f8841ff7` / reviewer `t_03ffa23d` — `validated` canonical CTGov support/evidence/features without changing `edges/molecule_treats_disease.parquet`; scope remains the bounded selected seed, not global CTGov.
- `t_957a3640` / reviewer `t_e2404763` — accepted structured trial metadata/features and the full 6,092-row canonical fallback sidecar. Its exact live object is `features/embeddings/clinical_trials_gov_trial_text/hashing_vectorizer/full_staged_fallback_v1/part-000.parquet`; no single-file fallback manifest exists. Foundation clinical text embeddings remain `blocked-with-resource`.

## Definition of done

A relation is not done until it is either:

- canonical promoted + reviewed, or
- explicitly accepted as staged/deferred with a reason and no misleading downstream claim.
