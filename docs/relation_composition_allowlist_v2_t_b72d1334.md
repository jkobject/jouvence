# Relation-composition allowlist v2 — staged pilot `t_b72d1334`

Status: **staged-only / review-required**

Normative policy revision: `5dc88d4b5372eb2cf99039d455c556314564450c`

Registry version: `2.0.0`

## Scope and storage contract

This implementation executes only the allowlisted motifs below. Unsupported template IDs fail before reading inputs. Candidate biological edges are written only under `edges_inferred/` and their derivations under `evidence_inferred/`. Coherence/existential views use `derived_views/` and `derived_views_evidence/`. The executor refuses an output root containing an observed `edges/` or `evidence/` path component.

Every candidate preserves a deterministic typed path, premise relation/endpoints, available source/evidence IDs, context and mapping fields, snapshot ID, template ID, epistemic class, support multiplicity, derivation hash, and observed/staged overlap flags. A candidate edge is dropped when its canonical target inventory is unavailable, so an unavailable anti-join cannot be mistaken for an empty anti-join.

## Inventory before execution

The bounded local real-data pilot used existing staged artifacts only; it performed no canonical, GCS, LaminDB, or cloud write.

| Available source family | Relation/artifact | Rows in source | Pilot rows | Relevant columns |
|---|---|---:|---:|---|
| OpenTargets 26.03 canonical transcript consequences | `mutation_affects_transcript` edges/evidence | 2,599,922 | 100 | typed endpoints, relation, source, source record, predicate, release, consequence JSON |
| OpenTargets 26.03 target genomic containment evidence | `mutation_in_gene` evidence | 2,599,525 | join-only | typed endpoints, source record, predicate, release, consequence/approved-symbol JSON |
| Cell Ontology/UBERON | `cell_type_found_in_tissue` edges/evidence | 958 | 100 | typed endpoints, ontology source record, mapping confidence, context |
| Disease/tissue staged context | `disease_manifests_in_tissue` edges/evidence | 19/29 | 19/29 | typed endpoints, source/evidence identifiers, predicate, release |

The pilot preparer retained transcript→gene mappings only where OpenTargets records shared the exact mutation, approved symbol, release, and consequence payload. Plain genomic containment was not consumed as a composition premise. This yielded 100 real mutation→transcript rows and six exact gene→transcript mappings.

The bounded snapshot had no canonical `mutation_associated_gene` target inventory and lacked most other motif prerequisites. The executor therefore evaluated the registry, generated diagnostic pre-anti-join paths where possible, then failed closed instead of emitting candidate edges.

## Stable allowlist mapping

| Template ID | Premises | Target | Storage | Epistemic class | Expected zero/rejection conditions |
|---|---|---|---|---|---|
| `mutation_transcript_gene_attribution_v2` | mutation→transcript + gene→transcript | `mutation_associated_gene` | inferred edge | inferred-obvious | containment only, assembly mismatch, missing mapping |
| `mutation_protein_gene_attribution_v2` | mutation→protein + transcript→protein + gene→transcript | `mutation_associated_gene` | inferred edge | inferred-obvious | isoform/assembly mismatch, missing mapping |
| `mutation_disease_phenotype_candidate_v2` | mutation→disease + disease→phenotype | `mutation_associated_phenotype` | inferred edge | inferred-weak | shared phenotype only, source circularity, context mismatch |
| `mutation_disease_phenotype_triangle_v2` | prior two premises + direct mutation→phenotype | `mutation_disease_phenotype_coherence` | derived view | coherence-only | incomplete triangle |
| `cell_type_tissue_gene_existential_v2` | cell type→tissue + cell type→gene | `tissue_expresses_gene` | inferred edge | inferred-obvious | context mismatch, missing supporting population |
| `mutation_protein_disease_candidate_v2` | exact mutation→protein + mutation→disease | `disease_associated_protein` | inferred edge | inferred-weak | isoform mismatch, unknown/conflicting pathogenicity |
| `mutation_protein_gene_disease_candidate_v2` | exact mutation→protein→transcript→gene + mutation→disease | `disease_associated_gene` | inferred edge | inferred-weak | mapping mismatch, unknown pathogenicity |
| `mutation_protein_gene_phenotype_candidate_v2` | exact mutation→protein→transcript→gene + mutation→phenotype | `gene_associated_phenotype` | inferred edge | inferred-weak | mapping/context mismatch |
| `tissue_protein_to_gene_expression_v2` | tissue→protein + exact protein→transcript→gene | `tissue_expresses_gene` | inferred edge | inferred-obvious | missing/mismatched mapping; RNA→protein reverse forbidden |
| `cell_type_protein_to_gene_expression_v2` | cell type→protein + exact mapping | `cell_type_expresses_gene` | inferred edge | inferred-obvious | missing/mismatched mapping; reverse forbidden |
| `cell_line_protein_to_gene_expression_v2` | cell line→protein + exact mapping | `cell_line_expresses_gene` | inferred edge | inferred-obvious | missing/mismatched mapping; reverse forbidden |
| `protein_disease_to_gene_disease_v2` | protein→disease + exact mapping | `disease_associated_gene` | inferred edge | inferred-obvious | missing/mismatched mapping |
| `gene_disease_to_protein_disease_strict_v2` | gene→disease + exact mapping + explicit protein/isoform support | `disease_associated_protein` | inferred edge | inferred-weak | missing explicit isoform support; gene→all isoforms forbidden |
| `pathway_associated_member_feature_v2` | pathway→gene + gene→disease | `pathway_associated_member` | derived view | coherence-only | unassociated member/every-member projection |
| `pathway_associated_protein_member_feature_v2` | pathway→protein + protein→disease | `pathway_associated_member` | derived view | coherence-only | unassociated member/every-member projection |
| `pathway_disease_candidate_v2` | pathway→gene + gene→disease | `disease_involves_pathway` | inferred edge | inferred-weak | insufficient independent members/sources, circularity, >500-member fan-out |
| `disease_phenotype_tissue_localization_v2` | disease→phenotype + same disease→tissue | `phenotype_observed_in_tissue` | inferred edge | inferred-weak | disease-anchor loss/Cartesian path, circularity, context mismatch |
| `disease_phenotype_tissue_triangle_v2` | prior two premises + direct tissue→phenotype | `disease_phenotype_tissue_coherence` | derived view | coherence-only | incomplete triangle |
| `signed_gene_target_treatment_v2` | signed molecule→gene + causal signed gene→disease | `molecule_treats_disease` | inferred edge | inferred-weak | missing/conflicting/same sign, context mismatch |
| `signed_protein_target_treatment_v2` | signed molecule→protein + causal signed protein→disease | `molecule_treats_disease` | inferred edge | inferred-weak | missing/conflicting/same sign, isoform mismatch |
| `allelic_triangulation_treatment_v2` | molecule→gene + exact mutation→gene + mutation→disease | `molecule_treats_disease` | inferred edge | inferred-weak | containment/weak attribution, missing/conflicting sign/context |
| `pharmacogenomic_efficacy_treatment_v2` | mutation→disease + mutation→molecule response | `molecule_treats_disease` | inferred edge | inferred-weak | resistance, toxicity, dosage, PK, missing/conflicting disease context/direction |

No template exists for C3 enhancer composition, RNA/gene→protein expression, generic response→phenotype, shared-phenotype disease identity, or every-member pathway projection. Stale rule-owned files matching these rejected motifs are removed on every run.

## Real staged pilot result

Command: `uv run python scripts/build_relation_composition_allowlist.py ...` against `artifacts/staged/t_b72d1334/pilot_input_snapshot`.

- Immutable snapshot ID: `local-real-staged-immutable-t_b72d1334-v1`
- Internal input-manifest digest: `a0807e07641f82b665d896cbdca6ccdcd9fd6965fd3a4f754ca2339342fc88a1`
- Real generated paths before anti-join: 100 for `mutation_transcript_gene_attribution_v2`; zero for the other 21 templates because prerequisites were absent.
- Final inferred edge rows: **0**. All 100 generated paths were rejected as `canonical_target_inventory_missing`; this is the intended fail-closed result, not a claim that the canonical target set is empty.
- Real sampled generated path: mutation `10_100001413_G_T` → gene `ENSG00000107554` via transcript `ENST00000324109`; derivation hash `0cfbf02e24288ab15c5995177ce59c4e1934298c11078acf6d3ad9349c924569`. It is diagnostic/pre-anti-join only and was not emitted.
- Output `edges_inferred/*.parquet` count: 0; stale prior output was cleaned.
- No scientific novelty or canonical-observed claim is made.

Staged artifact file hashes:

| Artifact | SHA-256 |
|---|---|
| `pilot_input_snapshot/SOURCE_INVENTORY.json` | `2c3850758d6e3c07c97eb6412ba3a71c52e416d67e020e8f4a07585e588b48a6` |
| `pilot_output/manifest/input_manifest.json` | `a756f6ec34cafcd1e8b47425c39bde52294fb25de6e2523c5d1fd9c03b24579a` |
| `pilot_output/manifest/template_registry_v2.json` | `e1a8b0ad557452a4950c007c673220fb66e66a3af869ef41008f5a4d634ce42e` |
| `pilot_output/manifest/pilot_report.json` | `2338a655cac1018e6c3ff2d752ab3fb1c8ab3d635d565cad70e0596558a773f9` |

## Validation

- `uv run pytest -q tests/test_relation_composition_allowlist.py tests/test_kg_schema_cleanup.py` -> **27 passed**.
- `uv run ruff check manage_db/relation_composition_allowlist.py scripts/build_relation_composition_allowlist.py scripts/prepare_relation_composition_pilot.py tests/test_relation_composition_allowlist.py` → all checks passed.
- Repository-wide collection is not clean in this environment: the unmodified PyG export tests require the optional `torch` package. With that file ignored, 308 tests passed, seven skipped, and 11 unrelated embedding/watchdog tests failed; none import or exercise the files changed here.
- Focused coverage includes endpoint direction, existential quantifier, assembly/isoform mismatch, source circularity, conflicting signs, protein→gene expression semantics, reverse/C3 exclusions, containment rejection, pathway fan-out, disease-anchored anti-Cartesian joins, observed/staged anti-joins, missing canonical target inventory, stale zero cleanup, and deterministic hashes.
