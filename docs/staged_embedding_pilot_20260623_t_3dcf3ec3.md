# Staged embedding pilot summary

Task: `t_3dcf3ec3`
Run id: `embedding_pilot_20260623_t_3dcf3ec3`
Created at: `2026-06-23T13:39:37Z`

## Scope and gate

This is a staged-only pilot under `artifacts/staged/`; it does not write or promote anything under the canonical KG root.
Because the local environment did not have `sentence_transformers`, `transformers`, or `torch`, this run uses a deterministic local `sklearn.HashingVectorizer` surrogate to validate payload construction, metadata, hashing, storage layout, and one-vector-per-edge aggregation. It is not a biological-quality replacement for the accepted foundation-model defaults in `docs/foundation_embedding_policy.md`.

## Outputs

- `node_text_embeddings`: `artifacts/staged/embedding_pilot_20260623_t_3dcf3ec3/features/embeddings/text/mixed_nodes/hashing_vectorizer/pilot_surrogate_v1/part-000.parquet`
  - rows: 3
  - dimension: 384
- `molecule_fingerprint_pilot`: `artifacts/staged/embedding_pilot_20260623_t_3dcf3ec3/features/embeddings/molecule_fingerprint/molecule/rdkit_morgan/pilot_surrogate_v1/part-000.parquet`
  - rows: 0
  - dimension: 2048
  - skipped rows: 2 (`artifacts/staged/embedding_pilot_20260623_t_3dcf3ec3/reports/molecule_fingerprint_skipped_rows.parquet`)
- `edge_evidence_embeddings`: `artifacts/staged/embedding_pilot_20260623_t_3dcf3ec3/features/edge_embeddings/cell_type_responds_to_molecule/hashing_vectorizer/pilot_surrogate_v1/part-000.parquet`
  - rows: 2
  - dimension: 384

## Model/version metadata

- Text/node and edge surrogate: `sklearn.feature_extraction.text.HashingVectorizer` / `scikit-learn-hashing-vectorizer@1.8.0+embedding_policy_v1+pilot_surrogate` / dim `384` / L2 normalized.
- Molecule fingerprint candidate: `rdkit-morgan-radius2-2048@2025.9.1+policy_v1` / dim `2048` sparse on-bits; emitted only when local staged molecule rows include valid SMILES.
- Source feature hashes are SHA-256 hashes of deterministic serialized node/edge payloads; input table hashes are in `manifest.json`.

## Recompute command

```bash
uv run python -m manage_db.build_embedding_pilot --input-dir artifacts/staged/cell_type_responds_to_molecule_sciplex2_20260622 --output-dir artifacts/staged/embedding_pilot_20260623_t_3dcf3ec3 --clean
```

## Runtime/cost and scaling estimate

- Runtime for this local pilot: 0.046s on macOS-26.5.1-arm64-arm-64bit.
- Direct cost: $0 external/API cost; no model downloads; CPU-only local vectorization.
- Pilot scale: 3 node text rows, 2 edge rows, 14 evidence rows in the available SciPlex2 staging artifact.
- Scaling estimate for this surrogate is roughly linear in serialized payload bytes and non-zero token count. For production foundation encoders, expect model inference to dominate; use the accepted policies to batch by modality, shard outputs, and benchmark on a capped 1k/10k-row sample before full KG promotion.

## Residual risks

- No canonical `/mnt/gcs/jouvencekb/kg/v2` mount was available, so this pilot used only the local staged SciPlex2 artifact.
- The local staged molecule nodes lacked SMILES, so no RDKit molecule fingerprint rows were emitted; skipped rows are recorded.
- Protein sequence embeddings were not attempted because no protein sequence feature table or ESM/torch stack was locally available.
- Replace the hashing surrogate with pinned S-BioBERT/ChemBERTa/ESM jobs before any canonical-quality embedding promotion.
