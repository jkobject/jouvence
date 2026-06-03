# Credibility Scoring Pipeline

The TxGNN++ knowledge graph relies on a deterministic credibility score to
compare heterogeneous edge evidence. `manage_db/credibility.py` centralizes the
logic so ingest jobs and composed-path builders use the same rules when
deduplicating sources, vetting author independence, and collapsing multi-hop
signals.

## Decision Tree

1. **Curated databases win** — if any evidence originates from a curated source
   in `{'drugbank','chembl_indication','chembl_moa','reactome','go','mondo','hpo'}`
   the edge is promoted to `Credibility.ESTABLISHED_FACT` (3).
2. **Deduplicate repeated evidence** — group evidences by shared `paper_id`
   (or prefix-matched sources pointing to the same paper) and keep the highest
   `raw_score` representative from each group.
3. **Count independent authors** — tally unique `author_group_key` values across
   the deduplicated set; when author groups are missing fall back to distinct
   `paper_id`, then to the remaining source strings.
4. **Require multiple labs for level 2** — two or more distinct author groups
   upgrades the edge to `Credibility.MULTI_EVIDENCE` (2) even without curated
   data.
5. **High-confidence genetics bump** — a single evidence with `raw_score ≥ 0.75`
   in `{'genetic_association','animal_model','known_drug','clinical_trial'}` is
   also deemed `Credibility.MULTI_EVIDENCE` (2); otherwise the edge stays at
   `Credibility.SINGLE_EVIDENCE` (1).

## Worked Examples

- **Established fact (3)** — OpenTargets reports a drug indication and the same
  relationship is confirmed by DrugBank. The curated `drugbank` evidence
  triggers rule 1 and the edge is marked as an established fact.
- **Multiple evidence (2)** — Two PubMed papers from different institutions
  describe the same gene–disease link. Deduplication keeps both labs and rule 4
  raises the credibility to multi-evidence.
- **Single evidence (1)** — A lone animal study with score 0.6 supports a
  molecule–disease edge but no other authors or curated sources exist. The edge
  remains a single-evidence hypothesis.

`tests/test_credibility.py` exercises the full pipeline, including curated
overrides, author deduplication, deterministic ordering, and composed path
generation.
