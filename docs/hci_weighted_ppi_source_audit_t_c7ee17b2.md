# Computing the Human Interactome source audit and bounded PPI pilot

Task: `t_c7ee17b2`  
Scope: source audit plus bounded staged prototype for weighted `protein_interacts_protein`; no canonical write.

## Recommendation

Use the peer-reviewed successor of the candidate preprint as the citable source:

- Preprint candidate: Zhang et al., “Computing the Human Interactome,” bioRxiv DOI `10.1101/2024.10.01.615885`.
- Peer-reviewed successor: Zhang et al., “Predicting protein-protein interactions in the human proteome,” *Science* 390(6771), 2025, DOI `10.1126/science.adt1630`.
- Data portal: `http://prodata.swmed.edu/humanPPI` and `https://conglab.swmed.edu/humanPPI/humanPPI_download.html`.
- Code: `https://github.com/CongLabCode/RoseTTAFold2-PPI`.
- License file on the data portal: Creative Commons Attribution 4.0 International (`https://conglab.swmed.edu/humanPPI/LICENSE.txt`).

The HCI/humanPPI 90%-precision predictions are semantically compatible with `protein_interacts_protein` only as computational predicted physical/structural PPI evidence. They should not be merged as the same evidence class as BioGRID/IntAct experimental or curated records. Preserve the model-specific probabilities and the expected-precision tier as evidence fields.

## Existing canonical state checked

Current canonical files under `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`:

- `nodes/protein.parquet`: 233,995 protein nodes; 80,388 distinct UniProt accessions represented in `uniprot_id`.
- `edges/protein_interacts_protein.parquet`: 3,550 canonical edge rows.
- `evidence/protein_interacts_protein.parquet`: 12,288 canonical evidence rows.
- Current canonical `source` for those edges is BioGRID, per file readback and `docs/part2_biogrid_ppi_canonical_promotion_report.md`.

Current docs still contain a wording inconsistency (`relation_coverage_current.md` says “Canonical IntAct direct PPI is now present” while the canonical readback and promotion report show BioGRID physical PPI). For this task I treated the Parquet readback plus BioGRID promotion report as the observed source of truth and did not edit the broader coverage table.

## HCI/humanPPI data availability

Downloaded for the bounded pilot:

- `final_predictions.tar.gz` from `https://conglab.swmed.edu/humanPPI/downloads/final_predictions.tar.gz` (14,127,380 bytes, server last-modified 2025-08-01).
- `segment_def` from `https://conglab.swmed.edu/humanPPI/downloads/segment_def` (524,563 bytes).
- `LICENSE.txt` from `https://conglab.swmed.edu/humanPPI/LICENSE.txt`.

The `final_predictions` archive contains:

- `final_predictions_90.tsv`: 17,849 rows; expected precision 90%; peer-reviewed abstract reports 17,849 interactions.
- `final_predictions_80.tsv`: 29,257 rows; expected precision 80%; superset of 90% set.

Source endpoint namespace is UniProt accession (`Protein1`, `Protein2`). The data also includes UniProt gene names, RF2-PPI probability, AlphaFold2 probability, AlphaFold-Multimer probability, source signal flags, STRING score, database-support summaries (`confDBs`, `allDBs`), locality/disease/process/function annotations, and template fields.

## Mapping results against canonical protein nodes

Mapping was UniProt accession → canonical `protein.uniprot_id` → canonical ENSP `protein.id`. Because Jouvence KG protein primary IDs are ENSP and many UniProt accessions map to multiple ENSP isoforms, a full ingest needs an explicit isoform/protein-canonicalization policy. I staged only a conservative unambiguous sample where both UniProt endpoints map to exactly one ENSP each.

| Precision file | Source rows | Unique source proteins | Both UniProt endpoints in canonical protein nodes | Both endpoints unambiguous single ENSP | Missing endpoint rows | Ambiguous endpoint rows | Representative-ENSP rows already matching canonical BioGRID pair |
|---|---:|---:|---:|---:|---:|---:|---:|
| 90% | 17,849 | 9,806 | 17,478 | 769 | 371 | 16,709 | 70 |
| 80% | 29,257 | 12,298 | 28,637 | 1,186 | 620 | 27,451 | 83 |

The high ambiguity is expected from current KG protein-node granularity, not necessarily from HCI. It means a production ingest should not blindly explode every UniProt pair to all ENSP isoforms without a reviewed isoform policy.

## Bounded staged prototype

Staged artifacts, no canonical write:

- `artifacts/staged/t_c7ee17b2/edges/protein_interacts_protein_hci90_unambiguous_sample100.parquet`
- `artifacts/staged/t_c7ee17b2/evidence/protein_interacts_protein_hci90_unambiguous_sample100.parquet`
- `artifacts/staged/t_c7ee17b2/reports/hci_mapping_summary.json`
- `artifacts/staged/t_c7ee17b2/reports/hci90_sample_rows.tsv`
- build script: `artifacts/staged/t_c7ee17b2/build_hci_pilot.py`

Pilot shape:

- 100 edge rows and 100 evidence rows from `final_predictions_90.tsv`.
- Only rows where both UniProt endpoints map unambiguously to one canonical ENSP each.
- Excluded rows already matching the existing canonical BioGRID PPI pair under representative ENSP mapping.
- Evidence fields preserve HCI-specific signals rather than collapsing to one generic score:
  - `expected_precision_tier`
  - `rf2_ppi_probability`
  - `alphafold2_probability`
  - `alphafold2_top5_probability`
  - `alphafold_multimer_probability`
  - `source_signal_flags`
  - `confident_database_support`
  - `all_database_support`
  - `string_score`
  - source UniProt/name fields

Example staged evidence rows include PLN–KCNE4, GPR37–LRRTM3, LCE2B–LCE2D, CEBPE–BATF3, and KRT1–KRT26 after UniProt→ENSP mapping.

## Source comparison

| Source | Best role for Jouvence KG | Weight/confidence | Endpoint caveat | Recommendation |
|---|---|---|---|---|
| BioGRID | Experimental/curated physical PPI evidence already canonical for current tranche | Mostly evidence classes/experimental systems, not a unified prediction score | Current canonical is small, direct protein mapping already validated | Keep as high-credibility experimental evidence; do not overwrite with predictive weights. |
| IntAct | Experimental molecular interaction evidence; useful expansion candidate | MI score/evidence details depending on export; negative evidence exists in staged sample | Existing bounded IntAct staging was deferred; requires reviewed cleanup before promotion | Revisit after source-native endpoint/evidence policy is tightened. |
| HCI / humanPPI | Structural/computational predicted human PPI with usable model probabilities | RF2-PPI, AF2, AFM probabilities plus expected precision tier and database support | UniProt→ENSP ambiguity dominates; not experimental | Good next weighted PPI source, but ingest as computational evidence with credibility lower than curated experimental sources. Prefer 90%-precision set first. |
| STRING v12 physical links | Broad scored physical subnetwork, CC-BY 4.0, easy download | Combined and channel-specific scores | STRING is an integrative database; some evidence channels may recapitulate BioGRID/IntAct/literature and create duplicates | Strong candidate for a separate scored physical-support evidence layer after channel-specific de-duplication. |
| HuRI / HI-union | Experimental Y2H gene-level interactome maps | Binary experimental calls; not a continuous weight in the downloaded TSV | Downloads are ENSG gene pairs, not protein/isoform endpoints | Better suited to `gene_interacts_gene` or a reviewed gene→protein projection policy; do not directly promote to `protein_interacts_protein`. |
| IID | Integrated/tissue-aware PPI context | Integrated confidence/context varies by file | Needs current access/license and endpoint audit | Useful later for tissue context/support, not first choice for clean weighted core PPI. |

## Next promotion gates before production/full done

1. Decide a UniProt→ENSP policy for protein interactions:
   - conservative canonical representative only,
   - all ENSP isoforms with evidence-level UniProt provenance,
   - or add/route through UniProt/protein-group aliases if schema evolves.
2. Ingest the HCI 90%-precision set first as computational evidence, with `credibility=1` or an equivalent low/medium predictive-evidence policy.
3. Preserve all HCI model probabilities and expected-precision tier in evidence. Do not collapse HCI, BioGRID, IntAct, and STRING into one untyped `score`.
4. De-duplicate against existing BioGRID/IntAct/STRING evidence at evidence level, not by deleting source-specific rows.
5. Run endpoint anti-joins and `manage_db.audit_edge_evidence` on the candidate before any canonical promotion card.
6. Require independent review before writing canonical `edges/protein_interacts_protein.parquet` or `evidence/protein_interacts_protein.parquet`.

## Commands run

```text
uv run python artifacts/staged/t_c7ee17b2/build_hci_pilot.py
python -m py_compile artifacts/staged/t_c7ee17b2/build_hci_pilot.py
uv run python - <<'PY'
import pyarrow.parquet as pq
for p in ['artifacts/staged/t_c7ee17b2/edges/protein_interacts_protein_hci90_unambiguous_sample100.parquet','artifacts/staged/t_c7ee17b2/evidence/protein_interacts_protein_hci90_unambiguous_sample100.parquet']:
    pf=pq.ParquetFile(p)
    assert pf.metadata.num_rows == 100, (p, pf.metadata.num_rows)
print('PASS parquet row count sanity: 100 edge rows, 100 evidence rows')
PY
```

Validation observed: `PASS parquet row count sanity: 100 edge rows, 100 evidence rows`.
