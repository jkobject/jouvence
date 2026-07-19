# Jouvence inferred biological relation algebra v1 — bounded pilot

Task: `t_eb1c393b`

Status: **staged-only / review-required**. This producer makes no scientific-novelty or literature-validation claim and performed no canonical, LaminDB, or GCS writes.

## Implementation

`manage_db/inferred_relation_algebra.py` contains a versioned typed registry and bounded engine for the approved v1 rules:

- conditional candidates: C1 variant→protein→disease, C2 variant→gene→disease, C3 variant→enhancer→gene→disease, and C5 pharmacogenomic direct molecule→disease;
- abductive candidates: signed gene/protein target-mechanism H1, with tissue/expression H2 only as reinforcement.

Every registry entry declares typed/directed premises and conclusion, epistemic class, required and forbidden evidence, context keys, sign algebra, quantifier, and fail-closed counterexamples.

The final approved allowlist explicitly excludes all former structural controls: D1 ontology closure, D2 HPO generalization, D3 gene→transcript→protein product, and Reactome closure. C4 TF→enhancer→gene, H3 cell-line response→disease, H4 synthetic-rescue/interaction, and PRISM are also excluded. PRISM remains a separate observed cell-line→molecule dataset.

The engine refuses unknown rules, canonical `edges/` or `evidence/` output roots, output inside the immutable input snapshot, and input files above the configured row bound. Each requested rule transactionally replaces its owned edge/evidence pair on every run. Empty rules produce no placeholder Parquet and remove any pair left by an earlier snapshot, so the manifest inventory cannot retain stale rule output.

Evidence metadata can satisfy gates only when values are non-conflicting. Internally multi-valued evidence is represented separately as `support_evidence_conflicts`, never collapsed into an ordinary gate value. Literal `conflicting` values and structured conflicts fail closed in context, compatibility, sign, and strong-inference consumers. A C3 path whose three premises each contain incompatible liver/brain biosample evidence is retained only as a weak `hypothesis`, with the conflict values preserved under `context_conflicts`; it cannot become `strong`.

## Output contract

Artifacts are written only as:

- `edges_inferred/<relation>/<rule_id>.parquet`
- `evidence_inferred/<relation>/<rule_id>.parquet`

Candidate rows include support edge and evidence IDs/hashes, full support path, immutable snapshot/generations, context intersection, `known|conflicting|unknown` sign status, strength, canonical-observed overlap, explicit anti-join status, absence-is-not-negation flag, and deterministic derivation hash. Corresponding inferred evidence rows carry the same derivation hash.

CLI: `scripts/build_inferred_relation_algebra.py`. Required arguments pin the input root, snapshot ID, object generations, selected rules, and row bounds.

## Immutable bounded pilot

Input snapshot:

- local read-only extraction: `artifacts/staged/t_eb1c393b/pilot_input_snapshot/`
- source: `gs://jouvencekb/kg/v2`
- snapshot manifest SHA-256: `7398e47bbdac025410413084b64025858b8a60135d23ec618fcb5b15d48604ba`
- edge and evidence object generations: recorded separately per relation in `snapshot_manifest.json` and embedded, namespaced, in every candidate
- bounds: at most 100,000 rows per local input file; 5,000 engine anchors per rule; C3 extraction scanned 100,000 overlap rows and 12/118 enhancer-regulation row groups.

Pilot output: `artifacts/staged/t_eb1c393b/pilot_output/`

| Rule | Candidates | Strong | Hypothesis | Observed overlap | Fail-closed paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1 `variant_protein_disease_v1` | 681 | 0 | 681 | 0 | 0 |
| C2 `variant_gene_disease_v1` | 2,127 | 0 | 2,127 | 1 | 0 |
| C3 `variant_enhancer_gene_disease_v1` | 23 | 0 | 23 | 0 | 0 |
| C5 `pharmacogenomic_variant_drug_disease_v1` | 0 | 0 | 0 | 0 | 1,426 |
| H1/H2 gene `signed_target_mechanism_gene_drug_disease_v1` | 0 | 0 | 0 | 0 | 1,690 |

The zero strong C1/C2/C3 rows are expected fail-closed behavior: the bounded canonical support lacks enough compatible functional/causal/context evidence to cross the strong gates. C5 produced no positive-efficacy candidate because response evidence was missing, conflicting, or not sensitivity/benefit-compatible in this bounded tranche. H1/H2 produced none because H1 lacked a complete opposite-known-sign causal mechanism path; expression did not generate candidates independently. Protein H1 was not run because the pinned canonical snapshot has no observed `molecule_targets_protein` or `disease_associated_protein` premise file; its semantics remain implemented and tested.

This pilot is a deterministic producer/control run, not novelty validation. The top samples in `pilot_output/manifest/pilot_report.json` are deterministic endpoint/hash samples only.

## Validation

`pilot_output/manifest/validation.json` records:

- 2,831 inferred edges and 2,831 corresponding derivation evidence rows;
- zero duplicate `(x_id, y_id, relation, rule_id)` rows;
- zero edge/evidence derivation-hash mismatches;
- zero missing full paths or snapshot IDs;
- no canonical `edges/` or `evidence/` output.

Automated coverage includes an exact six-rule allowlist with D1/D2/D3 absence, isoform/context mismatch, LD/intronic-only strong-gate rejection, C3 alternative-target uncertainty and internally conflicting biosamples, pharmacogenomic resistance, missing/conflicting signs, H2 non-generation, RNA-not-protein reinforcement, excluded C4/H3/H4/PRISM/pathway motifs, metadata-only support, observed anti-join/absence semantics, immutable-input protection, bounded input enforcement, deterministic hashes, transactional same-root nonzero→zero edge/evidence replacement, output pairing, and CLI behavior.

Independent review must judge biological rule semantics and false-positive guards before acceptance. No artifact is authorized for canonical promotion.
