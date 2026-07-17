# Source-native modeling doctrine

[← Documentation index](../README.md) · [KG architecture](kg-architecture-and-evidence.md) · [Lessons learned](lessons-learned.md)

Model what a source measures or asserts, not what an identifier projection makes imaginable.

## Core rules

- A gene-level measurement remains gene-level.
- A transcript relation requires a source-native transcript, UTR, or isoform endpoint.
- A protein relation requires a direct protein/isoform identifier or measurement.
- A motif hit is predicted support, not observed binding.
- Coordinate overlap is context unless external evidence supports the stronger claimed consequence.
- Population frequency is not pathogenicity.
- Prediction, correlation, association, containment, observation, and causality remain distinct semantics.
- Literature and dataset catalog records do not become biomedical training adjacency by default.
- Native coordinates and identifiers remain in evidence even when canonical IDs are derived.

## Measurement-to-representation guide

| Source assertion | Allowed representation | Do not silently upgrade to |
| --- | --- | --- |
| Gene/RNA-level abundance or effect | Gene/RNA feature or relation with matching endpoint | Protein-level effect |
| Transcript consequence with native ENST | Transcript relation plus evidence | All-gene or all-protein expansion |
| Protein/isoform measurement | Protein relation when endpoint is direct and canonical | Gene relation presented as protein evidence |
| Motif occurrence | Predicted support/feature | Observed `tf_binds_enhancer` |
| Coordinate overlap | Context/proof/candidate relation according to policy | Causal regulatory effect |
| VEP target or neighborhood annotation | Evidence/context unless containment is independently proven | Physical `mutation_in_gene` |
| Population allele frequency | Population feature/evidence | Clinical pathogenicity assertion |
| Clinical-trial record or outcome text | Metadata/evidence/feature with leakage policy | Treatment truth label or graph node by default |
| Dataset/paper catalog row | Metadata/provenance | Message-passing node/edge |
| Model-inferred link | Explicit inferred/predicted surface | Observed canonical source assertion |

## Mapping and derivation

Mapping may normalize an assertion, but it must not change its biological level.

A projection, liftOver, interval join, aggregation, or identifier conversion must retain:

- native source endpoint and coordinates;
- target canonical endpoint;
- transformation policy and version;
- accepted/rejected classes;
- source release and input identities;
- derivation proof or validation report when needed;
- explicit `observed`, `derived`, `predicted`, or `context` status.

If the intended relation cannot be supported without an unjustified expansion, keep the data staged or as a feature/context sidecar.

## Stable relation names, source-specific evidence

Prefer broad, stable relation names whose semantics remain truthful across sources. Put source-specific predicate, assay, score, tissue, method, and release details in evidence.

Do not create a new relation merely to encode a source name or a minor predicate variant. Do create or rename a relation when endpoint type or biological assertion is genuinely different.

## Promotion questions

Before promotion, ask:

1. Does the relation name match the source-native assertion?
2. Are endpoint types directly supported rather than expanded by convenience?
3. Is directionality source-backed?
4. Is the row observational, associative, predictive, or derived?
5. Is a dense contextual surface being mistaken for useful adjacency?
6. Does every transformation have a documented, versioned proof trail?

## Authoritative detailed sources

- [`../source_native_expansion_policy.md`](../source_native_expansion_policy.md)
- [`../structural_variation_source_schema_design_t_baad8ddb.md`](../structural_variation_source_schema_design_t_baad8ddb.md)
- [`../inferred_edges_policy.md`](../inferred_edges_policy.md)
- [`../mutation_genomic_relations_promotion_policy.md`](../mutation_genomic_relations_promotion_policy.md)
- [`../../todo.d/04_relations.md`](../../todo.d/04_relations.md)
- [`../../todo.d/05_remap.md`](../../todo.d/05_remap.md)
