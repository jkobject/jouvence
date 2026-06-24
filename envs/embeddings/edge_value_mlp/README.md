# Edge/evidence value MLP embeddings

Task scaffold: `t_8892763b`.

Runtime requirements: GPU optional for first bounded runs; torch required.

Install/run with the repo `uv` dependency group rather than mixing model families in one environment.

```bash
uv run --group embeddings-edge python -m manage_db.build_real_embeddings --kg-root <kg_or_staged_root> --output-dir artifacts/staged/<task-id>/edge_value_mlp_smoke --edge-relations molecule_targets_gene --edge-limit-per-relation 1000 --clean
```

Outputs must remain under `artifacts/staged/<task-id>/...` until validation and independent review. Do not write `.omoc`; do not promote to canonical `features/` from a production worker without a reviewer gate.
