# Literature metadata/index policy — t_9c86ca89

Status: `review-required` policy/doc update. No canonical KG files were rewritten in this card.

## Decision

Keep literature as provenance/catalog metadata and, if needed, a separate literature metadata/index graph. Do not connect Paper/Author/Citation nodes to the TxGNN biomedical training/inference graph by default.

Operational policy:

- Biomedical KG assertions keep publication identifiers in evidence metadata fields such as `paper_id`, `pmid`, `doi`, `pmc_id`, `source_record_id`, `source_dataset`, `dataset_id`, and source-specific raw metadata.
- `paper` nodes in the current canonical KG are legacy/provenance metadata, not message-passing nodes.
- `author` nodes and paper citation edges should not be added to `v2/nodes/` or `v2/edges/` consumed by default PyG/HeteroData training export.
- If a literature graph is retained, write it under a separate namespace/export such as `v2/literature_index/` or a dedicated LaminDB/catalog table, with explicit opt-in for literature analytics only.
- Do not use paper co-mention, citation, shared author, or author/institution connectivity as biomedical edges or as default GNN adjacency; those are bibliographic signals and create severe hub/leakage risks.

This extends the earlier dataset/paper graph-disconnection decision in `docs/dataset_paper_graph_disconnection_t_c07b8b57.md`: dataset/paper metadata remains useful, but it is not part of biomedical graph adjacency.

## Current canonical paper inventory

Audited source of truth: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`.

Command evidence:

```bash
uv run python - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq
root = Path('/Users/jkobject/mnt/gcs/jouvencekb-kg/v2')
for rel in ['nodes/paper.parquet', 'edges/paper_cites_paper.parquet', 'edges/paper_produced_dataset.parquet', 'evidence/paper_cites_paper.parquet']:
    p = root / rel
    print(rel, p.exists(), p.stat().st_size if p.exists() else None)
pf = pq.ParquetFile(root / 'nodes/paper.parquet')
print(pf.metadata.num_rows, pf.schema_arrow.names)
print(pf.read_row_group(0).slice(0, 5).to_pandas())
PY
```

Observed result:

| Artifact | Rows | Schema / status | Policy |
| --- | ---: | --- | --- |
| `nodes/paper.parquet` | 2,958,199 | `id`, `doi`, `pmc_id`, `arxiv_id`, `year`, `source`; sample IDs are `PMID:*`; `source='OpenTargets'` | Keep as legacy/provenance metadata only; exclude from training graph. |
| `edges/paper_cites_paper.parquet` | absent | no canonical citation edge file | Do not canonical-promote into biomedical `edges/`. |
| `edges/paper_produced_dataset.parquet` | absent | no canonical paper→dataset edge file | Keep paper/dataset provenance outside training adjacency. |
| `evidence/paper_cites_paper.parquet` | absent | no canonical evidence file | Optional only in separate literature-index export. |

Current staged-only pilot from `v2/staging/paper-dataset-provenance-20260622-t_649cee71`:

| Staged artifact | Rows | Notes |
| --- | ---: | --- |
| `nodes/paper.parquet` | 18 | OpenAlex metadata for OpenTargets/DepMap provenance seed and referenced works. |
| `nodes/dataset.parquet` | 3 | OpenTargets dataset metadata sidecar. |
| `edges/paper_cites_paper.parquet` | 16 | OpenAlex `referenced_works` pilot; metadata/literature only. |
| `edges/paper_produced_dataset.parquet` | 4 | Curated OpenTargets/DepMap provenance links; metadata only. |
| matching `evidence/*.parquet` | same row counts | includes `license`, `source_url`, `openalex_work_id`, `paper_id`, `doi`, `pmid`, and raw metadata. |

The staged validation report says `canonical_promotion=false`, `only_metadata_or_literature_relations=true`, and `no_paper_comention_biological_assertions=true`.

## Source audit

Live checks run in this card:

- OpenAlex API `https://api.openalex.org/works?per-page=1`: `meta.count=317,596,832` works.
- OpenAlex API `https://api.openalex.org/authors?per-page=1`: `meta.count=118,689,100` authors.
- PubMed E-utilities `db=pubmed&term=all[sb]`: `count=40,758,165` PubMed records.
- PMC E-utilities `db=pmc&term=all[sb]`: `count=12,307,177` PMC records.
- Semantic Scholar Datasets API release `2026-06-16`: papers `200M` records, authors `75M` records, citations `2.4B` records, abstracts `100M` records; full data requires an API key, and dataset README sections state ODC-BY licensing for these collections.

| Source | Coverage / IDs | Citations | Authors | Access / license notes | Policy fit |
| --- | --- | --- | --- | --- | --- |
| OpenAlex | Global scholarly works; API count in this run: 317.6M works. Work objects provide OpenAlex IDs, DOI, PMID, PMCID/arXiv where available, title/date, `authorships`, `referenced_works`, `cited_by_count`. | Direct outgoing references via `referenced_works`; cited-by count and snapshot/API support. | First-class Author entity; API count in this run: 118.7M authors; author IDs are stable OpenAlex URLs with ORCID where available. | OpenAlex documentation states the complete dataset is free under CC0. Good for metadata/index graph. | Best default source for an optional literature-index graph because it covers Paper/Author/Citation in one CC0 metadata layer. |
| Semantic Scholar Academic Graph | Release `2026-06-16`; `papers` dataset says 200M records with core attributes and external IDs. | `citations` dataset says 2.4B records with citing/cited paper IDs, influential flag, contexts, intents. | `authors` dataset says 75M records with `authorId`, joinable to paper author fields. | Full data requires API key; READMEs state ODC-BY for checked datasets; individual abstracts/citation contexts may need extra care. | Useful alternative/enrichment, but not first choice for this KG until access-key and redistribution constraints are approved. |
| PubMed | E-utilities count in this run: 40.8M records. Strong PMID identity and biomedical bibliographic metadata. | PubMed itself is not a full citation graph source. | Author names/affiliations in article metadata, but no clean global author identity graph comparable to OpenAlex/S2. | NCBI public access; records are bibliographic abstracts/metadata, not necessarily full text. | Good for PMID normalization/evidence metadata; insufficient alone for Paper/Author/Citation graph. |
| PMC / Europe PMC | PMC E-utilities count in this run: 12.3M records; Europe PMC REST was already access-audited in staged pilot. Strong PMCID/PMID/DOI crosswalk and open-access/full-text metadata. | Europe PMC has cited-by/reference APIs, but coverage/rights vary by source and full text licensing. | Article metadata includes author strings/ORCIDs where available, but author disambiguation is not the main product. | Must distinguish metadata from article full text and preserve article-level licenses. | Good source for PMCID/full-text metadata and evidence crosswalks; not enough reason to wire papers/authors into biomedical training graph. |

## Separate literature-index schema, if retained

Namespace: `literature_index`, not default `nodes/` + `edges/` used by TxGNN training.

Suggested files:

- `literature_index/nodes/paper.parquet`
  - required: `paper_id`, `primary_id_namespace`, `pmid`, `pmc_id`, `doi`, `arxiv_id`, `openalex_work_id`, `semantic_scholar_paper_id`, `title`, `publication_date`, `publication_year`, `source`, `source_record_id`, `license`, `source_url`, `updated_at`.
  - `paper_id` may be canonicalized as `PMID:*` when PMID exists, else `DOI:*`, else `OpenAlex:W*`, with xref columns preserved.
- `literature_index/nodes/author.parquet`
  - required: `author_id`, `openalex_author_id`, `semantic_scholar_author_id`, `orcid`, `display_name`, `source`, `source_record_id`, `license`, `updated_at`.
  - Use source-native disambiguated author IDs only; do not create one node per raw author string unless explicitly marked unresolved.
- `literature_index/edges/paper_has_author.parquet`
  - required: `paper_id`, `author_id`, `author_position`, `is_corresponding`, `raw_author_name`, `raw_affiliation_strings`, `source`, `source_record_id`, `license`.
- `literature_index/edges/paper_cites_paper.parquet`
  - required: `citing_paper_id`, `cited_paper_id`, `source`, `source_record_id`, `citation_direction='citing_to_cited'`, optional `citation_context`, `citation_intent`, `is_influential`, `license`.
- Optional: `literature_index/edges/author_affiliated_with_institution.parquet` only if an institution namespace is explicitly approved.

Export rules:

1. Default biomedical graph export ignores `literature_index/*` entirely.
2. Evidence loaders may join `paper_id`/PMID/DOI to literature metadata for display, provenance, retrieval, or audit, but must not emit biomedical adjacency from citation/authorship alone.
3. A future literature ingest must include row-count estimates, license/access review, storage budget, endpoint-ID policy, and leakage review before any large download.

## Follow-up decision

No large ingest is needed to satisfy current TxGNN biomedical graph scope. Therefore this card does not create a large-ingest follow-up task.

If the user later wants a literature search/index product, request explicit approval for a separate OpenAlex-first `literature_index` ingest rather than promoting paper/author/citation into canonical biomedical KG adjacency.
