# Staged causal feature materialization — `t_abbfe5e7`

Status: **staged feature enrichment built / review-required**

Accepted contract revision: `c9e7a21ea6ab2d3786727ea7065ad80720363e03` (PR #30 exact accepted head)

## Product delta

`manage_db/materialize_causal_edge_features.py` adds deterministic optional feature columns to existing edge/evidence tables without changing relation names, endpoint identities, edge order, source records, or raw evidence columns. Features are derived from evidence rows only; direct edge shortcuts never override evidence.

The fresh local build used the two exact, locally readable source-native inventories reproduced by the accepted contract:

| Relation | Source | Edges before → after | Evidence before → after | Materialized feature status |
| --- | --- | ---: | ---: | --- |
| `molecule_targets_protein` | ChEMBL mechanism | 2,119 → 2,119 | 2,132 → 2,132 | action `single=1,952`, `consensus=10`, `conflicting=1`, `unknown=156` |
| `disease_associated_protein` | UniProtKB DISEASE + humsavar | 3,243 → 3,243 | 35,839 → 35,839 | mechanism `unknown=3,243`; effect direction `unknown=3,243` |

No relation-name aliases were created. Output identity is unchanged byte-for-byte at the `(x_id, y_id, relation)` sequence level. Every source evidence column and source record ID is retained. Optional columns are appended, so readers selecting the legacy columns remain compatible.

## Normalization behavior

### ChEMBL pharmacological action

Evidence keeps the raw ChEMBL `predicate` byte-for-byte and adds:

- `normalized_action_type`
- `normalized_action_direction`
- `normalized_target_modulation`
- `source_assertion_id`
- `materialization_assertion_id` (relation/endpoint/source/dataset/record-scoped aggregation identity; any raw `source_assertion_id` remains unchanged)
- `materialization_assertion_conflict` (fail-closed marker when one scoped assertion ID carries non-identical feature semantics)
- `causal_feature_contract_version`

Edges add deterministic JSON-array columns `action_types`, `action_direction`, and `target_modulation`, plus `action_status`, `evidence_count`, and the contract version. Exact source-record duplicates count once; rows without a usable normalized assertion do not inflate `evidence_count`.

Observed normalized evidence counts:

- negative/decrease: 1,350
- positive/increase: 595
- binding with unknown effect: 31
- unavailable/unreviewed action semantics: 156

The one actual contradiction is preserved, not selected away: `CHEMBL1204165 → ENSP00000305372` has agonist and antagonist assertions, `action_status=conflicting`, and evidence count 2.

### UniProt protein–disease assertions

The builder preserves UniProt disease comments and humsavar variant categories byte-for-byte. Humsavar categories are exposed in the appended `normalized_clinical_significance` field only:

- `likely_pathogenic_or_pathogenic`: 18,412 evidence rows
- `uncertain_significance`: 2,284
- `likely_benign_or_benign`: 137
- unavailable on DISEASE-comment rows: 15,006

No GoF/LoF, disease effect direction, or inheritance is inferred from `LP/P`, missense/stop wording, protein-to-disease direction, or free text. Therefore all 3,243 edge mechanisms and effect directions remain `unknown`. Causal support is conservatively labeled as a source-backed disease assertion, source-backed variant–disease assertion, or mixed source-backed assertions; it is not a functional mechanism claim.

## Immutable staged artifacts

Final root: `artifacts/staged/t_abbfe5e7/`. Pre-review drafts were removed before this final immutable candidate was generated; the builder now rejects any non-empty destination.

- `edges/molecule_targets_protein.parquet`
  - SHA-256 `08b5b4f2abdd4f92c4512f889fb18abe1dedc6a024147b99df09b7da447ced91`
- `evidence/molecule_targets_protein.parquet`
  - SHA-256 `afe5ed235e9c109940a9009d47a88d66d829d7067992aba8b7fa300ef4aa5a88`
- `edges/disease_associated_protein.parquet`
  - SHA-256 `1371f0e627e0cc7db32714864aeaeabbd7b7f2e7ba3aa30b0723ee1ef33eec3d`
- `evidence/disease_associated_protein.parquet`
  - SHA-256 `6a3cb7a53fd0a0ab55071f5e806ad92ede52b2e6c25926ac99d3cbdfe3a6d352`
- `reports/materialization_manifest.json`
  - SHA-256 `3b0e9887c986f7216e0888741b02bd7c9c67cc2bfd128002d7c883e3fbba8c21`
  - complete before→after schemas, input/output checksums, per-source counts, status counts, unavailable fields, conservation receipts, and the fail-closed legacy contraindication receipt

The artifact root is immutable by the builder: rerunning into a non-empty root fails.

## Validation

Artifact validator:

```bash
uv run python scripts/validate_staged_causal_edge_features.py \
  artifacts/staged/t_abbfe5e7/reports/materialization_manifest.json \
  --expected-task-id t_abbfe5e7 \
  --expected-relation molecule_targets_protein \
  --expected-relation disease_associated_protein
```

Result: `{"ok": true, "errors": []}`.

The validator re-reads input and output Parquets, requires the exact task ID and relation set, and independently rematerializes all normalized evidence and edge aggregates from the preserved raw inputs. It also verifies checksums, every original edge/evidence value and column, identity/order, row conservation, relation/endpoint-derived evidence pairing, exact four-state statuses, exact task-root paths, contract version, and the 30,675-pair contraindication exclusion. Refreshing receipt checksums cannot hide raw or semantic corruption.

Focused tests cover:

- conflicting evidence overriding a contradictory direct edge action field;
- unknown polarity/mechanism remaining unknown;
- duplicate source records not inflating independent support;
- conflicting rows sharing one source assertion failing closed without order dependence;
- row-wise source-field fallback without overwriting raw values;
- mismatched stored edge keys and non-task staging roots being rejected;
- already-materialized feature columns being rejected rather than overwritten;
- incomplete endpoint or source-record identities being rejected;
- distinct disease contexts remaining conflicting;
- humsavar/missense/stop text not becoming LoF/GoF;
- toxicity and metabolism/PK remaining separate from efficacy;
- missing disease context remaining unknown;
- unsigned beta remaining unsigned without an explicit source effect direction;
- staged identity and raw source-column preservation;
- validator detection of checksum and relation drift.

## Explicit residual unknowns and exclusions

- Full local-readable snapshots for `molecule_targets_gene`, `disease_associated_gene`, `mutation_associated_disease`, and `mutation_affects_molecule_response` were not present in the task worktree or permitted local artifact inputs. The card forbids GCS/FUSE/canonical reads, so no full files were fetched or fabricated. The implementation supports these relations and their negative gates, but this artifact contains only the two exact accepted protein-native inventories that were locally readable.
- UniProt source rows do not expose an accepted explicit GoF/LoF, disease risk/protection direction, or inheritance normalization in this snapshot; these remain unknown.
- ChEMBL action strings outside the reviewed mapping remain unknown rather than being coerced.
- The legacy 30,675 `molecule_contraindicates_disease` pairs have zero evidence assertions and remain unusable for sign or anti-join completeness.
- No inference generation, cloud write, canonical mutation, GCS/FUSE read, LaminDB write, or new scientific novelty claim occurred.
