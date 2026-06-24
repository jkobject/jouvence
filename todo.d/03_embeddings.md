# 03 — Embeddings

## Current state

- `t_8f039536` — foundation embedding policy: `design done`, but needs correction from Jérémie.
- `t_1dc65ac1` — edge/evidence embedding policy: `design done`, but needs correction from Jérémie.
- `t_3dcf3ec3` — staged embedding pilot: `pilot accepted`/`staged-only`, but only schema/pipeline surrogate.
  - HashingVectorizer surrogate, not production biological embeddings.
  - Local staged-only, no canonical promotion.

## Jérémie corrections

- Official full UniProt `protein_textual_summary.parquet` is validated/promoted and must be used as available text signal.
- Embeddings are not done until actual embeddings exist.
- Edge values/evidence should be encoded by an MLP that outputs an embedding from values.
- Edge embedding input should concatenate/aggregate all edges/evidence between the same two nodes where relevant.
- Nodes/edges without information get learned embeddings.

## Active cards

- `t_6b3c1294` — fix embedding policies with the corrections above.
- `t_f8bae791` — build real node and edge embeddings.
- `t_34836f1c` — validate real embeddings.
- `t_384b9594` — review real embeddings.

## Definition of done

Embeddings are done only when actual vectors exist with model/version/source hashes, and the GNN can consume them or a precise blocker is recorded.
