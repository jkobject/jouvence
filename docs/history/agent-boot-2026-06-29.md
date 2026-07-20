# Historical agent boot snapshot — 2026-06-29

> Superseded by the root [`AGENTS.md`](../../AGENTS.md). This snapshot is historical evidence only; do not use it as active operating instructions.

## Project

TxGNN is a Python ML research library for zero-shot drug repurposing on a heterogeneous biomedical KG. This repo is being expanded into the Jouvence KG with OpenTargets, HPA, TxData, source-backed evidence, LaminDB cataloging, PyG/GNN export, and learned/foundation embeddings.

## Operating posture recorded on 2026-06-23

Old `.omoc` paths were already legacy-only. Workers were directed to the canonical KG root `gs://jouvencekb/kg/v2`, bounded local inspection through `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`, task-scoped `artifacts/staged/<task-id>/` and `artifacts/cache/<task-id>/`, human-readable reports under `docs/`, and remote staging under `gs://jouvencekb/kg/staging/...`.

Python was managed with `uv`; the intended LaminDB instance was `jkobject/jouvencekb`. The shared `work/txgnn` directory was not an independent Git checkout, so reviewable work was required to use a clone/worktree of `https://github.com/jkobject/TxGNN` rather than `git init` in the artifact workspace.

## Recorded source-of-truth documents

- [`../kg_schema_overview.md`](../kg_schema_overview.md)
- [`../relation_coverage_current.md`](../relation_coverage_current.md)
- [`../../reproduce/15_kg_schema_overview.ipynb`](../../reproduce/15_kg_schema_overview.ipynb)
- [`../relation_backlog_prioritized.md`](../relation_backlog_prioritized.md)

The 2026-06-29 snapshot recorded 67 active declared relations, 40 canonical active edge relations, 18 canonical relations with evidence, 22 without evidence, 27 not yet canonical, 100,080,390 canonical edge rows, and 55,523,691 node rows. These numbers are dated and must not be treated as live status.

## Recorded incomplete areas

- LaminDB artifact registry sync existed, but exact-ID schema/query coverage remained incomplete.
- PyG/GNN had a bounded export pilot, not a full HeteroData/GNN execution proof.
- Embeddings had policy and surrogate pilots, not complete real embeddings.
- All-peak ReMap observed binding was stopped/deferred; CRM support remained support/QA rather than canonical observed binding.
- Mutation relations had mixed reviewed, promoted, and review-required states documented in dated task reports.

## Modeling and promotion doctrine retained from the snapshot

- Relation names must match source-native assertions and endpoint types.
- Gene-level rows remain gene relations unless the source is native to protein, TF, or transcript endpoints.
- Edges are deduplicated graph assertions; evidence rows carry source predicates, scores, papers, studies, assays, and provenance.
- Placeholder Parquets must not be created merely to satisfy schema coverage.
- Promotion required staged construction, endpoint anti-joins, evidence when available, edge/evidence audits, coverage updates, targeted tests, and independent review before canonical writes.

Use the current [`AGENTS.md`](../../AGENTS.md), [`TODO.md`](../../TODO.md), and [`docs/README.md`](../README.md) instead of this historical summary.
