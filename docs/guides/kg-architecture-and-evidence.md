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
- [`../dataset_paper_graph_disconnection_t_c07b8b57.md`](../dataset_paper_graph_disconnection_t_c07b8b57.md)
- [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md)
- [`../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md`](../remap_crm_full_support_sidecar_canonical_promotion_t_f2a2952e.md)
- [`../mutation_in_gene_canonical_promotion_t_1cfcd48f.md`](../mutation_in_gene_canonical_promotion_t_1cfcd48f.md)
