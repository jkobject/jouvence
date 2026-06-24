# Learned molecule SMILES embeddings

Task scaffold: `t_8892763b`.

Runtime requirements: CPU/GPU; RDKit canonicalization must be pinned.

Install/run with the repo `uv` dependency group rather than mixing model families in one environment.

```bash
uv run --group embeddings-molecule python -m manage_db.build_molecule_smiles_embeddings --kg-root <kg_or_staged_root> --output-dir artifacts/staged/<task-id>/molecule_smiles_chemberta
```

Outputs must remain under `artifacts/staged/<task-id>/...` until validation and independent review. Do not write `.omoc`; do not promote to canonical `features/` from a production worker without a reviewer gate.
