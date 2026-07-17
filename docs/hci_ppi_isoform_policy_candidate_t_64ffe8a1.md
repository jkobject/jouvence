# HCI weighted PPI isoform policy and staged HCI90 candidate

Task: `t_64ffe8a1`  
Status: `staged-only/review-required`; no canonical promotion.

## Scope

This task follows the accepted HCI/humanPPI source audit `t_c7ee17b2` and reviewer `t_6764e3b4`. The source remains Zhang et al. 2025 / humanPPI, a computational predicted physical/structural PPI source with expected-precision tiers and model probabilities. This report defines a conservative UniProt→ENSP endpoint policy and stages the full HCI 90%-precision candidate for rows where that policy is unambiguous under current Jouvence protein nodes.

## Raw/source artifacts

The build reused the reviewer-accepted raw files from `artifacts/staged/t_c7ee17b2/raw/` and copied them into task-scoped locations:

- `artifacts/cache/t_64ffe8a1/raw/final_predictions.tar.gz`
- `artifacts/cache/t_64ffe8a1/raw/segment_def`
- `artifacts/cache/t_64ffe8a1/raw/LICENSE.txt`
- `artifacts/staged/t_64ffe8a1/raw/final_predictions.tar.gz`
- `artifacts/staged/t_64ffe8a1/raw/segment_def`
- `artifacts/staged/t_64ffe8a1/raw/LICENSE.txt`

`final_predictions.tar.gz` contains `final_predictions_90.tsv`, `final_predictions_80.tsv`, and `README`. No `.omoc` source/cache path was used.

## Current protein endpoint inventory

Canonical source of truth inspected: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/protein.parquet`.

- Canonical protein nodes: 233,995.
- Protein nodes with non-null `uniprot_id`: 233,869.
- Distinct UniProt accessions represented in current protein nodes: 80,388.
- Rows in `uniprot_to_ensp_pairs.parquet`: 233,869.
- Current protein/transcript node tables do not expose a reviewed Ensembl canonical isoform flag.
- A deterministic `representative_ensp` was computed only for review/inventory; it is not treated as a biologically canonical endpoint in this task.

Inventory artifact paths:

- `artifacts/staged/t_64ffe8a1/mappings/uniprot_to_ensp_inventory.parquet`
- `artifacts/staged/t_64ffe8a1/mappings/uniprot_to_ensp_pairs.parquet`

Canonical-node inventory by UniProt mapping case:

| Mapping case | UniProt accessions |
| --- | ---: |
| `single_isoform` | 60,652 |
| `multi_isoform_same_gene` | 19,551 |
| `multi_isoform_multi_gene` | 185 |

## HCI UniProt endpoint ambiguity

HCI endpoints are source-native UniProt accessions. Mapping was UniProt accession → `nodes/protein.uniprot_id` → canonical ENSP `nodes/protein.id`.

| HCI precision tier | Source rows | Unique source proteins | Rows with both UniProt endpoints in current protein nodes | Rows with both endpoints unambiguous single ENSP | Rows with representative/multi-isoform endpoint excluded by policy | Rows with any missing endpoint | Duplicate UniProt pairs | Accepted subset overlap with canonical BioGRID pair |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 90% | 17,849 | 9,806 | 17,478 | 769 | 16,709 | 371 | 0 | 70 |
| 80% | 29,257 | 12,298 | 28,637 | 1,186 | 27,451 | 620 | 0 | 83 |

HCI90 endpoint mapping cases by source side:

| Source endpoint side | single isoform | representative available / multi-isoform same gene | multi-isoform multi-gene | missing |
| --- | ---: | ---: | ---: | ---: |
| Protein1 | 2,614 | 14,957 | 81 | 197 |
| Protein2 | 2,492 | 15,109 | 60 | 188 |

The dominant blocker remains UniProt→multiple ENSP ambiguity in current KG protein granularity. This task therefore does not explode UniProt pairs to all isoforms and does not use the deterministic representative ENSP for graph edges.

## Proposed policy for HCI computational `protein_interacts_protein`

### Endpoint mapping

Accepted for staged edges:

- HCI 90%-precision source rows where both UniProt endpoints map to exactly one current canonical protein ENSP each via `nodes/protein.uniprot_id`.
- Endpoint identity is undirected: sorted ENSP pair is used for staged edge identity and `edge_key`.
- Source UniProt order, source names, and source row IDs are preserved in evidence fields.

Excluded from staged edges:

- any row with a missing UniProt endpoint in current canonical protein nodes;
- any row where either UniProt endpoint maps to multiple ENSP proteins;
- deterministic representative/canonicalized rows until a reviewed Ensembl/UniProt canonical isoform policy exists.

Represented as inventory/evidence metadata only for now:

- multi-isoform same-gene rows with a deterministic representative ENSP;
- multi-isoform multi-gene rows;
- missing endpoint rows.

### Evidence fields

HCI is computational predicted physical/structural support, not experimental PPI evidence. Preserve source-specific weights instead of collapsing into one generic score:

- `expected_precision_tier`
- `rf2_ppi_probability`
- `alphafold2_probability`
- `alphafold2_top5_probability`
- `alphafold_multimer_probability`
- `source_signal_flags`
- `confident_database_support`
- `all_database_support`
- `string_score`
- template, locality, disease, process, and function annotations
- source UniProt/name/provenance fields

### Credibility relative to BioGRID/IntAct

Use `credibility = 1` for HCI staged edge rows. Treat HCI as lower credibility than source-native experimental/curated BioGRID or IntAct rows. HCI should be useful as weighted computational support, not as proof equivalent to experimental physical interaction evidence.

### Duplicate and overlap handling

- Within HCI: deduplicate by sorted ENSP pair plus relation. The HCI90 policy-accepted subset has 0 duplicate mapped edge keys.
- Against current canonical BioGRID: do not delete HCI evidence. A future canonical promotion would merge HCI evidence under existing edge keys for the 70 overlapping pairs rather than create duplicate graph edges.
- Against future IntAct/STRING: preserve HCI source-specific evidence rows and run source-aware overlap audits before any promotion.

### Leakage/use caveat

`confDBs`, `allDBs`, and `STRING` fields encode external database support and STRING overlap. Downstream model training/evaluation must not use these fields as leakage-prone labels when evaluating recovery of BioGRID/IntAct/STRING-derived PPI edges unless source-aware splits and feature exclusions are explicit.

## Staged HCI90 candidate

Artifacts, no canonical write:

- `artifacts/staged/t_64ffe8a1/edges/protein_interacts_protein_hci90_policy_accepted.parquet`
- `artifacts/staged/t_64ffe8a1/evidence/protein_interacts_protein_hci90_policy_accepted.parquet`
- `artifacts/staged/t_64ffe8a1/candidate_kg/edges/protein_interacts_protein.parquet`
- `artifacts/staged/t_64ffe8a1/candidate_kg/evidence/protein_interacts_protein.parquet`
- `artifacts/staged/t_64ffe8a1/reports/hci90_isoform_policy_candidate_report.json`
- `artifacts/staged/t_64ffe8a1/reports/validation_report.json`
- `artifacts/staged/t_64ffe8a1/reports/hci90_policy_accepted_sample_edges.tsv`
- `artifacts/staged/t_64ffe8a1/reports/hci90_policy_accepted_sample_evidence.tsv`
- `artifacts/staged/t_64ffe8a1/reports/hci90_mapping_sample.tsv`
- `artifacts/staged/t_64ffe8a1/reports/hci80_mapping_sample.tsv`
- build script: `artifacts/staged/t_64ffe8a1/build_hci90_isoform_policy_candidate.py`

Candidate row counts:

- HCI90 accepted staged edges: 769.
- HCI90 accepted staged evidence rows: 769.
- Canonical BioGRID overlap by undirected ENSP pair: 70.
- Current canonical `protein_interacts_protein` readback: 3,550 edge rows / 12,288 evidence rows, edge source `BioGRID`.

Example staged evidence rows include source records `HCI90:5383` (`Q7Z6R9`–`Q92481`), `HCI90:6915` (`O75594`–`Q16552`), `HCI90:15680` (`P09093`–`P15085`), and preserve RF2-PPI / AF2 / AFM probabilities.

## Validation

Commands run:

```text
python -m py_compile artifacts/staged/t_64ffe8a1/build_hci90_isoform_policy_candidate.py
uv run python artifacts/staged/t_64ffe8a1/build_hci90_isoform_policy_candidate.py
uv run python -m manage_db.audit_edge_evidence artifacts/staged/t_64ffe8a1/candidate_kg --json --relations protein_interacts_protein --fail-on-missing
uv run python - <<'PY'
# Parquet row/schema/sample assertions; see task handoff for output.
PY
```

Observed validation:

- candidate edge rows: 769.
- candidate evidence rows: 769.
- duplicate edge keys: 0.
- duplicate evidence edge keys: 0.
- endpoint anti-joins against current canonical `nodes/protein.parquet`: x=0, y=0.
- edges without evidence: 0.
- evidence without edge: 0.
- `manage_db.audit_edge_evidence` on `artifacts/staged/t_64ffe8a1/candidate_kg`: `ok=true`, 769 edges / 769 evidence, 0 support gaps.
- Targeted readback after `t_21e6e11d` doc correction matched `reports/hci90_isoform_policy_candidate_report.json`, `mappings/uniprot_to_ensp_inventory.parquet`, and `mappings/uniprot_to_ensp_pairs.parquet`: 233,995 canonical protein nodes; 233,869 protein rows with non-null `uniprot_id`; 80,388 UniProt accessions; 233,869 UniProt→ENSP pair rows; mapping cases `single_isoform` 60,652, `multi_isoform_same_gene` 19,551, `multi_isoform_multi_gene` 185.

## Residual risks / review questions

1. Most HCI rows are still excluded because current KG protein nodes do not expose a reviewed canonical isoform marker. A full production ingest needs a separate canonical isoform policy or an explicit UniProt/protein-group alias model.
2. The deterministic `representative_ensp` in the inventory is only a review aid; reviewers should not treat it as accepted canonicalization.
3. HCI source fields include database support and STRING overlap; training graph exports need leakage-aware feature handling.
4. HCI is computational weighted support, lower credibility than experimental BioGRID/IntAct evidence.
5. No canonical promotion is authorized by this task.
