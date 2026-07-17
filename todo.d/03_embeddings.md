# 03 — Node features and embeddings

_Last verified: 2026-07-15. Kanban board `txgnn` remains the live source of truth._

## Review verdict

The statement “every possible node has a sequence, description and source-backed embedding” is **false**. Coverage must be reported by node type and modality. A sequence is biologically appropriate only for sequence-bearing entities; nodes without a reviewed payload use an explicit **learned model-side fallback**, not a fabricated canonical embedding.

## Active node types and source-feature coverage

There are 15 active canonical node types: `paper`, `gene`, `transcript`, `protein`, `pathway`, `molecule`, `mutation`, `disease`, `cell_type`, `tissue`, `phenotype`, `cell_line`, `organism`, `dataset`, `enhancer`.

### Canonical source-backed feature tables

| Node type | Canonical sequence/structure feature | Canonical description/text feature | Honest status |
| --- | --- | --- | --- |
| protein | `protein_sequence`: 112,051 rows | `protein_textual_summary`: 162,163 rows / 69.30% protein coverage | source-backed but not every protein has both modalities |
| transcript | `transcript_sequence`: 187,268 rows | none | sequence coverage partial versus 507,365 transcript nodes |
| gene | none canonical; staged `gene_genomic_sequence`: 78,164 rows and `gene_genomic_interval`: 78,644 rows | `gene_textual_summary`: 212,029 / 267,830 | genomic candidate is staged-only and does not cover NCBI-only/long-locus cases |
| molecule | `molecule_fingerprint`: 18,614; source SMILES/text available for 22,230 / 31,007 | `molecule_textual_summary`: 22,230 | no fabricated structure for molecules without valid SMILES |
| disease | n/a | 26,395 / 41,859 | partial text coverage |
| pathway | n/a | 37,492 / 48,575 | mostly GO; Reactome descriptions remain incomplete/deferred |
| phenotype | n/a | 13,810 / 16,449 | partial HPO text coverage |
| tissue | n/a | 11,942 / 16,061 | partial UBERON text coverage |
| cell_type | n/a | 3,135 / 3,513 | partial ontology text coverage |
| cell_line | n/a | 1,140 / 1,183 | high but incomplete text coverage |
| enhancer | no canonical sequence | none | coordinates exist; sequence extraction/embedding deferred |
| mutation | no canonical local-context sequence | none | coordinate/ref/alt context feature policy still missing |
| organism | n/a | no official table | one human node; low-priority fallback/metadata |
| paper | n/a | no official text embedding table | graph-disconnected metadata; text/license policy deferred |
| dataset | n/a | no official text embedding table | graph-disconnected metadata |

Sequences are therefore **not expected for every node type**, and are not complete even for every sequence-bearing node.

## Real embedding artifacts

Validated/reviewed staged-only outputs include:

- **protein ESM2 t33:** 112,051 / 112,051 source sequence rows, 1,280 dimensions, zero skipped/failed rows, finite/non-zero, duplicate keys 0;
- **transcript Nucleotide Transformer:** 187,268 / 187,268 source transcript-sequence rows, accepted staged-only full artifact, 512 dimensions;
- full staged real text S-BioBERT modality and learned molecule-SMILES modality were reported by the promotion-readiness audit as full/staged real outputs;
- real bounded node text vectors and edge/value/evidence MLP vectors were independently validated;
- PyG wiring for real node embeddings, learned node/edge fallback tensors and consumed `edge_attr` passed bounded implementation review.

Important boundaries:

- most embedding outputs remain **staged-only**, not canonically promoted under `kg/v2/features/embeddings/`;
- there is not one source-backed vector for each of the 55,523,691 physical nodes;
- enhancer and mutation dominate node count and currently rely on learned fallback in model materialization because reviewed source embedding modalities are absent;
- edge/value MLP output has executable bounded proof, but full all-relation production embedding materialization and model calibration are not complete;
- learned fallback is a model parameter/initialization, not biological source evidence.

## 16 GB implication

Do not load one dense vector for every node into RAM. Dense float32 lower bounds for 55,523,691 nodes are approximately:

- 256 dimensions: 52.95 GiB;
- 512 dimensions: 105.90 GiB;
- 768 dimensions: 158.85 GiB.

The reviewed design fits a 16 GB worker only through versioned sidecars, mmap/sharding, selected-relation loading, bounded minibatches and learned fallback materialized only for the active sampled subgraph. Full dense all-node embedding materialization in 16 GB is not supported.

## Remaining review gaps

1. Promote or explicitly retain staged-only versions of full real embedding modalities with one coherent manifest/index.
2. Produce a per-node-type coverage manifest: canonical rows, source-feature rows, real embedding rows, skipped rows, fallback-required rows.
3. Decide reviewed sequence/context features for enhancer and mutation; decide whether staged gene genomic features should be promoted.
4. Confirm full text/SMILES output counts and canonical promotion status in a fresh promotion-readiness audit.
5. Run a larger PyG model test that consumes these modalities under a measured 16 GB budget.

## Definition of done

- every active training node type has either a reviewed source-backed modality with row-level coverage or an explicitly measured learned-fallback requirement;
- every real embedding has model revision, source hash, dimension, dtype, pooling/windowing, skipped-row accounting and immutable manifest;
- no missing payload is hidden with zero vectors or mislabeled as biological information;
- PyG consumes the intended modalities and a reviewed training/evaluation job runs within the target memory budget.
