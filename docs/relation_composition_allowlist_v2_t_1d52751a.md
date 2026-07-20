# Relation-composition allowlist v2 corrective pilot — `t_1d52751a`

Status: **staged-only / review-required**

Normative policy revision: `5dc88d4b5372eb2cf99039d455c556314564450c`

Registry version: `2.0.0`

Corrective base: current `main` merge `6408c329b00a2cadf51545abe63c2f0643950140` (PR #20 head `bdb82d7db5aa3779432c3b04a7cee59278ff4a86`)

Invalidated implementation inspected: PR #18 head `026781a5ae3167f44e2a0e79060b21d33697a5dd`

## Corrective scope

This rebuild does not reuse the invalidated reviewer PASS for PR #18. It restores the 22-template staged executor on the corrective PR #20 base and fixes the three independently reproduced blockers:

1. Edge summaries no longer mask row-level evidence disagreement. `_with_evidence` preserves the edge value and all distinct edge/evidence values while setting `clinical_significance_status` or `pathogenicity_status` to `conflicting`.
2. Protein-changing mutation→disease candidates use a closed support allowlist. Accepted normalized values are `pathogenic`, `likely_pathogenic`, `pathogenic_likely_pathogenic`, `reviewed_causal`, and `causal_reviewed`. Benign, likely-benign, associative/generic, unreviewed causal, unknown, conflicting, and any unrecognized support values generate zero candidates with counted rejection reasons.
3. The output root must be path-disjoint from the primary immutable input root and every staged-input root. Equality, output-descendant, and output-ancestor layouts fail before `_load`; destructive-layout tests compare every input snapshot byte before and after rejection.

The prior fail-closed contract remains in force: observed edge/evidence separation, strict context/sign/provenance/pathway gates, target anti-joins, complete transactional tree swap with rollback, stale-zero cleanup, and a fresh immutable-manifest rehash immediately before publication. Outputs remain under `edges_inferred/`, `evidence_inferred/`, `derived_views/`, and `derived_views_evidence/`. No canonical GCS, observed KG, or LaminDB write is performed.

## Fresh bounded source snapshot

The pilot copied seven small source Parquets read-only from reviewed canonical/staged GCS objects into task-local cache. The largest source object was 945,765 bytes; no bulk or full-KG scan was run.

| Local source | Rows | SHA-256 |
|---|---:|---|
| `source/mutation/mutation_affects_transcript.edges.parquet` | 11,669 | `99bafae0bef52540ea4170beed26f62674ea61d465dd5fc877ce09451902dcd6` |
| `source/mutation/mutation_affects_transcript.evidence.parquet` | 11,669 | `5a87b247acd905779d1659c8c36e38ce5b2b947716ded2072e7b01ba20078551` |
| `source/mutation/mutation_in_gene.evidence.parquet` | 11,669 | `8859c513886c633d137d6fba38a6c83a33a4febc1aee81937cc15e248d50f301` |
| `source/cell/cell_type_found_in_tissue.edges.parquet` | 958 | `8a973db2c80d78958e93c45ea9df7d49f68613707e238637ac30705b0bc9efaa` |
| `source/cell/cell_type_found_in_tissue.evidence.parquet` | 958 | `d851d04c2e0acad873659f24cd3b6c23014bb21265fde4b6fc337c16fc911de3` |
| `source/disease/disease_manifests_in_tissue.edges.parquet` | 19 | `648185b0b614852f5b3d7637dfada519935b895452934c630bd0c279656b4dca` |
| `source/disease/disease_manifests_in_tissue.evidence.parquet` | 29 | `d157afa05a9952c6e439de1744d0d53bc191552c2a2377003c3297dbe7486941` |

The bounded preparer selected 100 exact mutation→transcript rows, two exact gene→transcript mappings, 100 cell-type→tissue rows, and 19 disease→tissue rows. The attribution gate requires the same OpenTargets mutation, approved symbol, release, and consequence payload; containment alone is not consumed.

Immutable snapshot ID: `local-real-staged-immutable-t_1d52751a-v1`

Internal manifest digest: `0a35774e3001f7fd09dc589302c4c99a5b3a36a2a9c208a55d6731641985874a`

## Fresh bounded result

All 22 approved templates were evaluated. `mutation_transcript_gene_attribution_v2` generated 100 diagnostic paths before anti-join. The task-local snapshot intentionally contained no canonical `mutation_associated_gene` target inventory, so all 100 were rejected as `canonical_target_inventory_missing`. Every other template generated zero because its prerequisites were absent. No inferred or derived Parquet was published.

This is a fail-closed staged pilot, not a novelty claim, canonical candidate, or promotion.

Task-local artifact root:

`artifacts/staged/t_1d52751a/`

| Artifact | SHA-256 |
|---|---|
| `pilot_input_snapshot/SOURCE_INVENTORY.json` | `1bde56a34ecaf86d4e52d8f4c8ab481bc8e7fab8f47798679caa9927679c6cd8` |
| `pilot_output/manifest/input_manifest.json` | `46d36b5eb39ba28819701ff9fa8fb4c44a93345cc4a19161ac7632127a341866` |
| `pilot_output/manifest/template_registry_v2.json` | `e1a8b0ad557452a4950c007c673220fb66e66a3af869ef41008f5a4d634ce42e` |
| `pilot_output/manifest/pilot_report.json` | `9738caa6801ab11bfa1cf5e6dfa46a5d7e8988cf26bcf119185244ad912ce066` |
| `prepare_report.json` | `1bde56a34ecaf86d4e52d8f4c8ab481bc8e7fab8f47798679caa9927679c6cd8` |
| `build_stdout.json` | `9738caa6801ab11bfa1cf5e6dfa46a5d7e8988cf26bcf119185244ad912ce066` |

## Validation posture

The focused suite covers all restored v2 behaviors plus executable regressions for edge/evidence pathogenicity conflict, the closed mutation→disease support allowlist and counted negative reasons, and all primary/staged input overlap directions with byte-preservation proof. Ruff, per-file compile, `git diff --check`, generated-file scope, and the exact test outputs are recorded in the Kanban review handoff and PR body.
