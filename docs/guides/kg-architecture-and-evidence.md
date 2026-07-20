# KG architecture, evidence, metadata, and features

[← Documentation index](../README.md) · [Source-native modeling](source-native-modeling.md) · [Review and promotion](review-promotion-and-reviewability.md)

The Jouvence KG separates four durable surfaces. They are related, but they are not interchangeable.

| Surface | Purpose | Changes graph adjacency? | Typical content |
| --- | --- | --- | --- |
| `nodes/`, `edges/` | Canonical biological topology | Yes | Deduplicated entities and graph assertions |
| `evidence/` | Source-level support for an edge | No; supports existing edge identity | Predicate, assay, score, study, biosample, release, source record |
| `metadata/` | Catalog and provenance objects | No by default | Datasets, papers, trial records, manifests, policies |
| `features/` | Raw or derived model/context signals | No by itself | Text, sequences, numeric attributes, embeddings, support summaries |

A fifth optional surface, `proof/`, records reproducible derivation evidence when an assertion depends on controlled coordinate, containment, mapping, or transformation logic.

## Edge identity and evidence multiplicity

An edge is one deduplicated graph assertion. Multiple source records may support the same `edge_key`; they remain separate evidence rows rather than producing duplicate graph edges or relation-name proliferation.

Keep source nuance in evidence:

- native predicate and endpoint identifiers;
- source release and source-record identity;
- assay or measurement type;
- score, direction, effect, confidence, and units;
- tissue, cell, disease, study, or experimental context;
- mapping/derivation policy and version when the endpoint is normalized.

Never synthesize placeholder evidence merely to make edge/evidence parity pass. Unsupported assertions remain unsupported or are excluded.

## Human gene identifier contract

Canonical human `gene` node IDs and every human-gene edge endpoint use Ensembl stable gene IDs (`ENSG...`). NCBI Gene IDs, HGNC IDs, symbols, UniProt accessions, and source-native identifiers are aliases or provenance fields; they are not parallel canonical gene nodes. Endpoint normalization must retain the raw source identifier and the exact mapping source, release, and file hash needed to reproduce the lineage.

Only an unambiguous human mapping may be rewritten automatically. Missing, one-to-many, conflicting, retired-without-replacement, and non-human identifiers are fail-closed: quarantine or exclude them with an explicit reason rather than guessing. Cross-species orthology is a separate source-native relation with organism-qualified endpoints and is excluded from the default human-only canonical graph until that policy and schema are reviewed explicitly.

Identifier migrations are staged graph rewrites, not in-place string edits. They must cover `nodes/`, every relation endpoint, and corresponding evidence keys; deterministically merge post-map edge collisions; preserve evidence multiplicity; pass endpoint anti-joins, duplicate-identity checks, and edge/evidence parity; and carry source/candidate hashes plus a rollback manifest before promotion.

## Causal semantics belong to existing edges

Jouvence keeps broad, stable relation identities. GoF/LoF, pharmacological action, risk/protection, pathogenicity, response direction, inheritance, dose, and context normally refine an existing `A → B` assertion; they do not create a new relation name.

- edge tables carry compact normalized features needed by graph consumers;
- evidence tables retain every source assertion, raw value, study/context, and provenance;
- multi-source edge features use explicit `single`, `consensus`, `conflicting`, or `unknown` aggregation states;
- inference requiring a known sign fails closed on `conflicting` or `unknown`;
- generic missense, coordinate containment, LD, expression, or physical interaction must not be converted into a causal sign without source-backed evidence.

The authoritative field families, examples, inference constraints, and validation gates are in [`../causal_edge_feature_model.md`](../causal_edge_feature_model.md).

The edge records the accepted biological assertion; the evidence records assay/source modality and derivation context. Consequently, direct protein-product expression may support an inferred `x_expresses_gene` edge through an exact protein/transcript/gene mapping, with `support_mode=protein_product_observed` in `evidence_inferred/`. This does not assert an RNA measurement. The reverse RNA/gene-expression→protein-expression projection remains forbidden.

## Feature/context is a valid final representation

Data does not need to become topology to be valuable. Use metadata, feature, evidence, or proof sidecars when the source is contextual, dense, or potentially leaky.

Examples:

- `dataset` and `paper` remain catalog/provenance entities and are excluded from default training adjacency;
- ClinicalTrials.gov records and text remain metadata/evidence/features keyed by NCT and treatment-edge identity, not automatically `clinical_trial` nodes;
- ReMap CRM aggregate support is useful for feature/QA surfaces but motif prediction is not observed TF binding;
- broad VEP consequences and coordinate overlap can remain context even when their endpoint keys are canonical;
- deterministic derivation proofs can justify a promoted relation without becoming model features.

Canonical storage under `metadata/` or `features/` does **not** authorize unrestricted use in PyG. Each surface must state its consumer policy, coverage, source identity, and leakage constraints.

## Consumer contract

Before a consumer uses a surface, its manifest should answer:

1. What is the row identity and join key?
2. Is coverage complete, partial, absent, or intentionally deferred?
3. Is the value source-backed, derived, inferred, or fallback?
4. Does it affect graph adjacency, model features, supervision, evaluation, or provenance only?
5. Can it reveal the target label or a downstream consequence?
6. Which source release, transformation policy, and artifact hash produced it?

## Validation boundary

Technical validity and scientific validity are separate gates.

Technical checks include schema, file readability, endpoint anti-joins, duplicate keys, edge/evidence parity, hashes, and canonical readback.

Scientific checks include source-native semantics, relation naming, density, directionality, context versus observation, leakage, and suitability for message passing.

Both are required for canonical graph topology.

## Authoritative detailed sources

- [`../evidence_and_edge_schema_plan.md`](../evidence_and_edge_schema_plan.md)
- [`../causal_edge_feature_model.md`](../causal_edge_feature_model.md)
- [`../dataset_paper_graph_disconnection_t_c07b8b57.md`](../dataset_paper_graph_disconnection_t_c07b8b57.md)
- [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md)
- [`../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md`](../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md)
- [`../mutation_in_gene_canonical_promotion_t_1cfcd48f.md`](../mutation_in_gene_canonical_promotion_t_1cfcd48f.md)
