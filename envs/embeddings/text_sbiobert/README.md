# Text / ontology summary embeddings

Task scaffold: `t_8892763b`.

Runtime requirements: CPU okay for smoke; GPU recommended for full run.

Install/run with the repo `uv` dependency group rather than mixing model families in one environment.

```bash
uv run --group embeddings-text python -m manage_db.build_real_embeddings --kg-root <kg_or_staged_root> --output-dir artifacts/staged/<task-id>/text_sbiobert_full --text-limit-per-table 100000000 --skip-edge-embeddings --clean
```

Outputs must remain under `artifacts/staged/<task-id>/...` until validation and independent review. Do not write `.omoc`; do not promote to canonical `features/` from a production worker without a reviewer gate.
