# Jouvence inferred biological relation algebra v1 — bounded pilot

Task: `t_eb1c393b`

Status: **staged-only / review-required**. This producer makes no scientific-novelty or literature-validation claim and performed no canonical, LaminDB, or GCS writes.

## Implementation

`manage_db/inferred_relation_algebra.py` contains a versioned typed registry and bounded engine for the approved v1 rules:

- conditional candidates: C1 variant→protein→disease, evidence-restricted C2 variant→gene→disease, and C5 pharmacogenomic direct molecule→disease;
- abductive candidates: signed gene/protein target-mechanism H1, with tissue/expression H2 only as reinforcement.

Every registry entry declares typed/directed premises and conclusion, epistemic class, required and forbidden evidence, context keys, sign algebra, quantifier, and fail-closed counterexamples.

The final approved allowlist explicitly excludes all former structural controls: D1 ontology closure, D2 HPO generalization, D3 gene→transcript→protein product, and Reactome closure. C3 variant→enhancer→gene→disease, C4 TF→enhancer→gene, H3 cell-line response→disease, H4 synthetic-rescue/interaction, and PRISM are also excluded. PRISM remains a separate observed cell-line→molecule dataset. C3 is not an optional or weak-hypothesis lane: it is unregistered, rejected by the CLI/engine allowlist, and every fresh build removes both deprecated C3 rule-owned Parquets from a reused output root.

C2 v1.1 emits only exact variant→gene attributions classified as `coding_pathogenic`, `splice`, `colocalized_eqtl`, or `l2g`. Coding/pathogenic rows require a qualifying coding consequence or pathogenic/likely-pathogenic attribution assigned to that exact gene. Splice rows require a direct donor/acceptor/region consequence. Regulatory-statistical rows require either an explicit colocalized-eQTL method/study/tissue path or an explicit OpenTargets L2G model/source/score path. Simple containment, generic intronic/transcript consequence plus containment, LD alone, nearest-gene assignment, ambiguous multi-gene assignment without explicit qualifying statistical support, and missing/conflicting attribution emit nothing. Colocalized-eQTL/L2G candidates remain `statistical_conditional` unless separate causal disease evidence exists. Every C2 row carries its typed family, preserved support details, evidence records, and full derivation path.

The engine refuses unknown rules, canonical `edges/` or `evidence/` output roots, output inside the immutable input snapshot, and input files above the configured row bound. Each requested rule transactionally replaces its owned edge/evidence pair on every run. Empty rules produce no placeholder Parquet and remove any pair left by an earlier snapshot, so the manifest inventory cannot retain stale rule output.

Evidence metadata can satisfy gates only when values are non-conflicting. Every direct field, alias, sole `support_evidence_fields` value, and `support_evidence_conflicts` set is resolved together as one typed `EvidenceValue` with `missing`, `single`, or `conflicting` status, so direct-versus-evidence disagreement cannot be erased or mistaken for an ordinary string or missing data. Internally multi-valued evidence is preserved separately as `support_evidence_conflicts`, never collapsed into an ordinary gate value. Literal `conflicting` values and structured conflicts fail closed in context, compatibility, sign, causal support, and attribution-family consumers.

## Output contract

Artifacts are written only as:

- `edges_inferred/<relation>/<rule_id>.parquet`
- `evidence_inferred/<relation>/<rule_id>.parquet`

Candidate rows include support edge and evidence IDs/hashes, full support path, immutable snapshot/generations, context intersection, `known|conflicting|unknown` sign status, strength, canonical-observed overlap, explicit anti-join status, absence-is-not-negation flag, and deterministic derivation hash. Corresponding inferred evidence rows carry the same derivation hash.

CLI: `scripts/build_inferred_relation_algebra.py`. Required arguments pin the input root, snapshot ID, object generations, exact producer revision, selected rules, and row bounds.

## Immutable bounded pilot

Input snapshot:

- local read-only extraction: `artifacts/staged/t_eb1c393b/pilot_input_snapshot/`
- source: `gs://jouvencekb/kg/v2`
- snapshot manifest SHA-256 and engine snapshot ID: `7398e47bbdac025410413084b64025858b8a60135d23ec618fcb5b15d48604ba`
- edge and evidence object generations: recorded separately per relation in `snapshot_manifest.json` and embedded, namespaced, in every candidate
- bounds: at most 100,000 rows per local input file and 5,000 engine anchors per rule. The immutable input snapshot still contains historical C3 premise extracts, but the v1.1 registry does not read them and the product output contains no C3 inventory or artifact.

Pilot output: `artifacts/staged/t_eb1c393b/pilot_output/`

| Rule/family | Candidates | Strong | Conditional/hypothesis | Observed overlap | Fail-closed paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1 `variant_protein_disease_v1` | 681 | 0 | 681 hypothesis | 0 | 0 |
| C2 `coding_pathogenic` | 400 | 0 | 400 conditional | included below | included below |
| C2 `splice` | 129 | 0 | 129 conditional | included below | included below |
| C2 `colocalized_eqtl` | 0 | 0 | 0 | 0 | included below |
| C2 `l2g` | 0 | 0 | 0 | 0 | included below |
| C2 total `variant_gene_disease_v1` | 529 | 0 | 529 conditional | 1 | 3,219 |
| C5 `pharmacogenomic_variant_drug_disease_v1` | 0 | 0 | 0 | 0 | 1,426 |
| H1/H2 gene `signed_target_mechanism_gene_drug_disease_v1` | 0 | 0 | 0 | 0 | 1,690 |

The bounded snapshot contains qualifying coding and splice consequences, so C2 emits those families. It contains no complete colocalized-eQTL method/study/tissue attribution and no explicit L2G model/source/score attribution in the selected `mutation_in_gene` slice, so those families honestly report zero rather than weakening their gates. The 3,219 rejected C2 paths cover containment/generic non-qualifying consequence or otherwise missing/conflicting attribution. C5 produced no positive-efficacy candidate because response evidence was missing, conflicting, or not sensitivity/benefit-compatible in this bounded tranche. H1/H2 produced none because H1 lacked a complete opposite-known-sign causal mechanism path; expression did not generate candidates independently. Protein H1 was not run because the pinned canonical snapshot has no observed `molecule_targets_protein` or `disease_associated_protein` premise file; its semantics remain implemented and tested.

This pilot is a deterministic producer/control run, not novelty validation. The top samples in `pilot_output/manifest/pilot_report.json` are deterministic and include endpoints, hashes, typed C2 support details where applicable, and complete derivation paths.

## Validation

`pilot_output/manifest/validation.json` records:

- 1,210 inferred edges and 1,210 corresponding derivation evidence rows;
- zero duplicate `(x_id, y_id, relation, rule_id)` rows;
- zero edge/evidence derivation-hash mismatches;
- zero missing full paths or snapshot IDs;
- zero observed-overlap/anti-join status inconsistencies;
- exact materialized/manifest inventory equality and no C3 edge/evidence Parquet;
- no canonical `edges/` or `evidence/` output.

Automated coverage includes an exact five-rule allowlist with C3/D1/D2/D3 absence, C3 unregistered/unmaterializable behavior and same-root stale-pair cleanup, positive coding/pathogenic/splice/colocalized-eQTL/L2G fixtures, adversarial containment/generic intronic/LD/nearest-gene/ambiguous/missing/conflicting C2 attribution, isoform/context mismatch, pharmacogenomic resistance, missing/conflicting signs, H2 non-generation, RNA-not-protein reinforcement, excluded C4/H3/H4/PRISM/pathway motifs, metadata-only support, observed anti-join/absence semantics, immutable-input protection, bounded input enforcement, deterministic hashes, transactional same-root nonzero→zero edge/evidence replacement, output pairing, and CLI behavior.

Independent review must judge biological rule semantics and false-positive guards before acceptance. No artifact is authorized for canonical promotion.
