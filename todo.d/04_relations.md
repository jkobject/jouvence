# 04 — Relations

## Inferred edges / derived links

New user-requested analysis:

- `t_f0ad9dff` — `INFERRED-EDGES-POLICY`: analyze relation-chain templates for obvious inferred links from the KG.
- `t_ee00835b` — validate inferred-edge policy/prototype counts and leakage guardrails.
- `t_af066273` — review inferred-edge policy and first-family recommendation.

Definition: inferred links must remain labeled/separate from observed canonical edges, with explicit evidence/provenance and GNN leakage guardrails. Do not promote inferred candidates into observed canonical relation files by default.


## Current source of truth

- `t_0b1f53d9` — relation audit: `validated`/reviewed.
- Approved docs:
  - `docs/kg_schema_overview.md`
  - `docs/relation_coverage_current.md`
  - `notebooks/kg_schema_overview.ipynb`

Counts:

- 67 active declared relations
- 37 canonical active edge relations
- 30 declared relations not canonical yet
- 20 staged-only/deferred
- 6 schema-only/missing

## Prioritized relation plan

- `t_cf77187d` — relation backlog/fanout: `design done`.
- `docs/relation_backlog_prioritized.md` exists.

## Mutation-specific path

- `t_60b3e504` — mutation policy: `design done`.
- `t_79f8684d` — 25k policy-aware staged tranche: `pilot accepted`/`staged-only` for QA only; not canonical; not full all-part rebuild.
- `t_f32f1f5b` — all-25-part `mutation_affects_transcript` staged candidate accepted after validation/review.
- `t_225ae18c` — `mutation_affects_transcript` canonical promotion completed and independently accepted.
- `mutation_in_gene` — remains staged/deferred pending explicit policy/acceptance; do not infer canonical status from the transcript promotion.
- `mutation_overlaps_enhancer` — remains staged/context/feature-only unless stronger allele-specific regulatory/enhancer-activity evidence is selected by a new policy.
- `t_4b1227b3` — canonical promotion only after relation-specific explicit review acceptance; not a blanket genomic-direct promotion.

## Other active relation waves

- Wave B protein-native mechanisms: `t_15e780b9` (`review-required` producer accepted for downstream validation) → `t_145b3cb9` → `t_c3eb09e3`.
- Wave C pharmacology/cell-line context: `t_103021f3` (`review-required` producer accepted for downstream validation) → `t_d71683f5` → `t_a7c7a5d1`.
- Wave E evidence-only pharmacology: `t_cd7fec1f` (`review-required`; linked tester `t_18159206`) → `t_18159206` → `t_fcb5b69f`.

## Definition of done

A relation is not done until it is either:

- canonical promoted + reviewed, or
- explicitly accepted as staged/deferred with a reason and no misleading downstream claim.
