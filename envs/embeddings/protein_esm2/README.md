# Protein ESM2 sequence embeddings

Task scaffold: `t_8892763b`.

Runtime requirements: GPU strongly recommended; smoke can use esm2_t12_35M_UR50D.

Install/run with the repo `uv` dependency group rather than mixing model families in one environment.

```bash
uv run --group embeddings-protein python -m manage_db.build_protein_sequence_embeddings --kg-root <kg_or_staged_root> --output-dir artifacts/staged/<task-id>/protein_esm2_smoke --model esm2_t12_35M_UR50D
```

Outputs must remain under `artifacts/staged/<task-id>/...` until validation and independent review. Do not write `.omoc`; do not promote to canonical `features/` from a production worker without a reviewer gate.
