# REL Wave B protein-native mechanism promotion candidates

Kanban task: `t_15e780b9`
Date: 2026-06-23
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Scope

This report prepares staging-only canonical-promotion candidates for Wave B protein-native / pharmacology mechanism relations from `docs/relation_backlog_prioritized.md`:

- `pathway_contains_protein` from Reactome `UniProt2Reactome_All_Levels`
- `molecule_targets_protein` from ChEMBL mechanism/target-component protein rows
- `disease_associated_protein` from UniProtKB reviewed DISEASE comments plus UniProt humsavar variant rows

No canonical KG Parquet was overwritten. Outputs are local staging candidates under `.omoc/staging/rel-wave-b-20260623-t_15e780b9/` and require independent tester/reviewer gates before any canonical promotion.

## Global gates applied

- Direct protein/isoform endpoints only: no gene-level pathway, target, or disease rows were projected into protein relations.
- Endpoint anti-joins were checked against canonical node files copied from `gs://jouvencekb/kg/v2/nodes/{pathway,molecule,protein,disease}.parquet` into `.omoc/gcs-cache/kg-v2/nodes/` because `/mnt/gcs/jouvencekb/kg/v2` was not mounted in this worker session.
- Edge/evidence support was checked with `manage_db.audit_edge_evidence` for all three relations.
- Source metadata and provenance are preserved in evidence rows and/or evidence `text_span` JSON.
- Candidate QA is machine-readable at `.omoc/reports/t_15e780b9_rel_wave_b_protein_native_qa.json`.

## Candidate artifacts

| Relation | Staging root | Edges | Evidence rows | Edge/evidence audit | Endpoint QA |
| --- | --- | ---: | ---: | --- | --- |
| `pathway_contains_protein` | `.omoc/staging/rel-wave-b-20260623-t_15e780b9/reactome-pathway-contains-protein` | 15,436 | 18,068 | pass: 0 edges without evidence, 0 evidence without edge | pass: pathway/protein anti-joins 0/0 |
| `molecule_targets_protein` | `.omoc/staging/rel-wave-b-20260623-t_15e780b9/molecule-targets-protein-chembl` | 2,119 | 2,132 | pass: 0/0 | pass: molecule/protein anti-joins 0/0 |
| `disease_associated_protein` | `.omoc/staging/rel-wave-b-20260623-t_15e780b9/disease-associated-protein-uniprot` | 3,243 | 35,839 | pass: 0/0 | pass: protein/disease anti-joins 0/0 |

Primary files per candidate root:

- `edges/<relation>.parquet`
- `evidence/<relation>.parquet`
- relation-specific diagnostics/reports under `reports/`, `validation/`, `mappings/`, or `diagnostics/`

## Relation-specific semantics

### `pathway_contains_protein`

Source: Reactome `UniProt2Reactome_All_Levels`
Endpoint direction: `pathway -> protein`

This candidate uses Reactome source-native UniProt accessions mapped directly to canonical KG `protein` nodes via exact unambiguous `nodes/protein.uniprot_id` matches. It rejects missing pathway nodes, unmapped UniProt accessions, and ambiguous UniProt-to-protein mappings instead of projecting through genes.

Important semantic gate: the source is Reactome all-level pathway membership. It contains pathway annotations across the Reactome hierarchy, not only leaf-level physical participants. Canonical promotion should explicitly accept all-level membership semantics or request a narrower leaf/participant-only Reactome build.

Preserved evidence metadata includes `membership_type`, `source_pathway_id`, `source_pathway_url`, `source_pathway_name`, `source_protein_id`, `reactome_evidence_code`, `species`, mapping confidence/method, source release, and Reactome license note.

### `molecule_targets_protein`

Source: ChEMBL mechanism API and target component records
Endpoint direction: `molecule -> protein`

This candidate consumes ChEMBL molecule mechanism rows and ChEMBL target components that expose protein-native UniProt accessions. It maps UniProt accessions to KG `protein` nodes only when the mapping is unambiguous. It does not consume canonical `molecule_targets_gene`, OpenTargets ENSG MoA rows, or other gene-level target rows.

Preserved evidence metadata includes source record ID (`mec_id`, ChEMBL target, UniProt accession), `predicate`/action type, mechanism of action, target class, target component ID/relationship/description, target UniProt accession, direct interaction / molecular mechanism / disease efficacy / max phase confidence JSON, source dataset, release, and PubMed references when present. Some ChEMBL-specific fields are stored in the canonical evidence `text_span` JSON rather than as top-level evidence columns.

### `disease_associated_protein`

Sources: UniProtKB reviewed human DISEASE comments and UniProt humsavar missense variant records
Endpoint direction: `protein -> disease`

This candidate materializes only source-native protein/isoform disease assertions tied to UniProt accessions or UniProt variant FTIds. It does not project OpenTargets or other gene disease associations into protein disease associations. Non-materialized source decisions are documented in the candidate root's `reports/source_native_audit.json`.

Preserved evidence metadata includes predicate, source/source_dataset/source_record_id, UniProt accession/entry/ENSP/isoform fields, disease source ID/name/acronym/description, variant FTId, amino-acid change, variant category, dbSNP ID, ECO/PMID evidence where present, mapping confidence/method, and source-native endpoint policy. UniProtKB/humsavar sources do not provide a quantitative association score; the canonical `evidence_score` column is present but intentionally blank, and the QA JSON records `source_score_available=false`.

## Validation commands run

```bash
uv run python -m manage_db.build_reactome_pathway_protein_membership \
  --node-root gs://jouvencekb/kg/v2 \
  --output-dir .omoc/staging/rel-wave-b-20260623-t_15e780b9/reactome-pathway-contains-protein

uv run python -m manage_db.build_chembl_molecule_targets_protein \
  --kg-path .omoc/gcs-cache/kg-v2 \
  --raw-dir .omoc/raw/chembl/molecule_targets_protein \
  --staging-root .omoc/staging/rel-wave-b-20260623-t_15e780b9/molecule-targets-protein-chembl \
  --release "ChEMBL API 2026-06-23"

uv run python -m manage_db.build_uniprot_disease_associated_protein \
  --output-root .omoc/staging/rel-wave-b-20260623-t_15e780b9/disease-associated-protein-uniprot \
  --protein-nodes .omoc/gcs-cache/kg-v2/nodes/protein.parquet \
  --disease-nodes .omoc/gcs-cache/kg-v2/nodes/disease.parquet

uv run python -m manage_db.audit_edge_evidence .omoc/staging/rel-wave-b-20260623-t_15e780b9/reactome-pathway-contains-protein --relations pathway_contains_protein --json
uv run python -m manage_db.audit_edge_evidence .omoc/staging/rel-wave-b-20260623-t_15e780b9/molecule-targets-protein-chembl --relations molecule_targets_protein --json
uv run python -m manage_db.audit_edge_evidence .omoc/staging/rel-wave-b-20260623-t_15e780b9/disease-associated-protein-uniprot --relations disease_associated_protein --json
```

Additional QA generated `.omoc/reports/t_15e780b9_rel_wave_b_protein_native_qa.json` with endpoint anti-join and metadata-preservation checks. Its top-level `ok` is `true`.

## Residual risks / tester-reviewer gates

1. Reactome all-level vs leaf-level semantics remain the main review decision for `pathway_contains_protein`.
2. ChEMBL conservative UniProt mapping rejects ambiguous UniProt-to-multiple-protein-node mappings. Reviewer should decide whether future tranches should expand isoforms or choose canonical protein nodes.
3. UniProtKB/humsavar disease evidence is protein-native but scoreless; this candidate preserves predicate/source/variant/measurement-like metadata, not a quantitative score.
4. This worker did not claim canonical promotion. Independent tester should rerun endpoint/evidence audits and reviewer should approve semantics before any canonical write.
