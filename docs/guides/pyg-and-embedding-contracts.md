# PyG and embedding contracts

[← Documentation index](../README.md) · [KG architecture](kg-architecture-and-evidence.md) · [Lessons learned](lessons-learned.md)

The production representation is sidecar-first. A monolithic `HeteroData` pickle is useful only for bounded pilots or explicitly materialized subsets; it is not the full-scale storage contract.

## PyG representation

Store each relation independently with:

- relation-wise `edge_index` arrays;
- node maps `node_id ↔ node_index`;
- edge row maps `edge_key ↔ edge_pos`;
- reverse-edge mappings via `forward_edge_pos`;
- feature/evidence descriptors in the manifest;
- source identities, hashes, counts, and leakage policy.

Memory-map selected arrays and bound the runtime relation/sample scope. Stage remote sidecars to worker-local storage before using local-path mmap loaders. Do not require a no-cap `heterodata/full_graph.pt` to claim architecture readiness.

A bounded smoke proves executability only. It does not prove full-scale materialization, training stability, biological utility, or model quality.

## Manifest feature states

Every selected node type and relation must distinguish:

| State | Meaning | Allowed fallback |
| --- | --- | --- |
| `source-backed available` | A real sidecar exists for some or all rows | Use the sidecar where joined; report row coverage |
| `absent` | No source-backed sidecar exists | Model-side learned embedding, explicitly declared |
| `deferred` | Modality intentionally postponed | No claim of current coverage |
| `fallback` | Deterministic scaffold or learned representation supports execution | Must not be described as source-derived biological signal |

`available` never means complete coverage unless row-level parity proves it. Do not hide absence with zero vectors or pseudo-source embeddings.

## Node embeddings

Keep modalities separate and fuse downstream:

- protein sequence versus protein text;
- transcript cDNA/UTR versus gene text;
- molecule structure versus molecule text;
- ontology text versus numeric/categorical attributes.

Derived embeddings are immutable versioned features tied to exact source hashes, model revision, tokenizer/preprocessing, pooling, dimension/dtype, code version, and license. Regenerate into a new versioned path rather than silently replacing prior vectors.

## Edge/evidence embeddings

An edge embedding represents an assertion and its accepted evidence, not an arbitrary serialization of every payload.

- numeric evidence uses explicit normalization/encoding;
- categorical/text evidence uses versioned encoders;
- multiple evidence rows aggregate deterministically;
- output identity remains one vector per consumed edge/group;
- rich provenance payload stays in sidecars rather than the dense hot path;
- reverse edges reuse forward identity rather than inventing separate biological evidence.

## Leakage contract

For every feature or embedding, record:

- prediction tasks it may leak;
- temporal/source release cutoff;
- whether it is input, supervision, evaluation-only, or provenance;
- split/masking policy;
- exclusion of labels, split assignments, model predictions, or downstream target evidence from the embedding payload.

Clinical-trial outcome/status/intervention text is canonical metadata/feature material but may reveal `molecule_treats_disease`; it must be masked or partitioned for held-out treatment prediction.

## `clinical_trial` policy resolution

Some older PyG examples mention a `clinical_trial` node type or trial-related graph relations. They are not the current canonical doctrine.

The accepted policy is:

- ClinicalTrials.gov trial records are metadata keyed by NCT;
- edge-to-NCT links are evidence/link metadata for existing treatment assertions;
- trial text and deterministic vectors are feature sidecars;
- no `clinical_trial` node type or default graph adjacency is implied;
- any future trial-node topology requires a new explicit schema/science decision and leakage review.

Therefore, do not copy older commands containing `clinical_trial` into new guides or runbooks unless the conflict has first been resolved by a newer reviewed policy.

## Readiness claims

Use precise boundaries:

- sidecar contract implemented;
- bounded exporter smoke passed;
- selected relation mmap loading validated;
- bounded training smoke passed;
- full production export complete;
- full training/evaluation complete.

Architecture readiness is not the same as full production training.

## Authoritative detailed sources

- [`../pyg_gnn_readiness_gate_t_825cfdcf.md`](../pyg_gnn_readiness_gate_t_825cfdcf.md)
- [`../pyg_manifest_metadata_contract_t_a3b15bc8.md`](../pyg_manifest_metadata_contract_t_a3b15bc8.md)
- [`../pyg_mapping_design.md`](../pyg_mapping_design.md)
- [`../edge_evidence_embedding_policy.md`](../edge_evidence_embedding_policy.md)
- [`../foundation_embedding_policy.md`](../foundation_embedding_policy.md)
- [`../clinical_trials_canonical_features_resolution_t_957a3640.md`](../clinical_trials_canonical_features_resolution_t_957a3640.md)
- [`../../artifacts/reports/t_e4f08d5a/kg_embedding_sidecar_audit.md`](../../artifacts/reports/t_e4f08d5a/kg_embedding_sidecar_audit.md)
- [`../../artifacts/reports/t_3df2bfc3_pyg_manifest_qa.md`](../../artifacts/reports/t_3df2bfc3_pyg_manifest_qa.md)
