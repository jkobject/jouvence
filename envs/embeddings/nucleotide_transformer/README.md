# Transcript cDNA nucleotide embeddings

Task scaffold: `t_8892763b`.

Runtime requirements: GPU recommended; length/window audit required before full run.

Install/run with the repo `uv` dependency group rather than mixing model families in one environment.

```bash
uv run --group embeddings-nucleotide python -m manage_db.build_nucleotide_sequence_embeddings --kg-root <kg_or_staged_root> --output-dir artifacts/staged/<task-id>/transcript_nucleotide_smoke --model <pinned-nucleotide-transformer>
```

Outputs must remain under `artifacts/staged/<task-id>/...` until validation and independent review. Do not write `.omoc`; do not promote to canonical `features/` from a production worker without a reviewer gate.
