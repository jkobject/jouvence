# Source-native `molecule_targets_protein` staged pilot — ChEMBL mechanisms

Date: 2026-06-22
Task: `t_84bf3876`
Staging root: `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876`
Remote staging root: `gs://jouvencekb/kg/v2/staging/molecule-targets-protein-chembl-20260622-t_84bf3876`

## Prior B3/C3 findings reviewed

Previous Block 1/C2-C3 audits remain binding:

- Current canonical `molecule_targets_gene` has 41,239 molecule→gene rows.
- OpenTargets canonical MoA rows are `CHEMBL` molecule → `ENSG` gene targets, not protein endpoints.
- TxGNN legacy rows are `DrugBank`/`CTD` molecule → `NCBI` gene targets, despite old `molecule_targets_protein` tokens in stale evidence that were later cleaned.
- Therefore no current canonical `molecule_targets_gene` row is split into `molecule_targets_protein`; gene→protein projection remains disallowed.

Relevant docs/reports:

- `docs/block1_molecule_targets_gene_audit.md`
- `docs/block1_relation_source_split_plan.md`
- `docs/block1_validation_report.md`

## Source audit outcome

### OpenTargets 26.03 `drug_mechanism_of_action`

Downloaded/inspected local cache: `.omoc/raw/opentargets/26.03/drug_mechanism_of_action`.

Observed schema has `targets` as `VARCHAR[]` and the values are OpenTargets/Ensembl target IDs (`ENSG...`). Even rows with `targetType='single protein'` use ENSG target IDs, so they remain source-native gene/OpenTargets-target assertions for the KG relation policy. They were not staged into `molecule_targets_protein`.

### ChEMBL mechanism API

Builder added: `manage_db/build_chembl_molecule_targets_protein.py`.

Source inputs:

- ChEMBL `/mechanism.json`: 7,561 mechanism rows.
- ChEMBL `/target/{target_chembl_id}.json`: 1,518 target records.
- KG node anti-join references: `.omoc/gcs-cache/kg-v2/nodes/molecule.parquet`, `.omoc/gcs-cache/kg-v2/nodes/protein.parquet`.

Endpoint policy:

- ChEMBL target components expose protein-native UniProt accessions.
- KG `protein` node IDs are ENSP IDs with `uniprot_id` xrefs.
- This pilot maps ChEMBL UniProt accessions to KG protein nodes only when `nodes/protein.uniprot_id` resolves to exactly one node. Ambiguous UniProt→multiple-ENSP mappings are rejected for review rather than expanded.
- No `molecule_targets_gene` rows or gene IDs are consumed.

## Staged artifacts

Local:

- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/edges/molecule_targets_protein.parquet`
- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/evidence/molecule_targets_protein.parquet`
- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/source_rows/molecule_targets_protein.parquet`
- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/reports/build_summary.json`
- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/reports/validation_report.json`
- `.omoc/staging/molecule-targets-protein-chembl-20260622-t_84bf3876/reports/audit_edge_evidence.json`

Counts:

- source rows after source-native filtering: 2,132
- graph edges after dedupe: 2,119
- evidence rows: 2,132
- distinct molecules: 1,036
- distinct KG protein nodes: 203
- distinct UniProt accessions staged: 203

Rejected source rows/components (from build summary):

- ambiguous UniProt→protein nodes: 10,514
- missing molecule node: 73
- missing ChEMBL target record: 517
- no protein component: 324
- non-human target: 911
- UniProt not in KG protein nodes: 26

## Evidence preservation

Evidence rows preserve:

- action type in `predicate` and edge `display_relation`/evidence JSON,
- mechanism label in `display_relation` and `text_span.mechanism_of_action`,
- ChEMBL target type/class in `text_span.target_class`,
- source DB/dataset in evidence columns and `text_span`,
- source record ID (`ChEMBL:mechanism:molecule_targets_protein:mec_id=...:target=...:uniprot=...`),
- release (`ChEMBL API 2026-06-22`),
- source-provided direct interaction flag in `evidence_score`,
- target confidence fields in `text_span.target_confidence`,
- ChEMBL target ID, UniProt accession, target component ID/relationship/description in `text_span`.

## Validation

Local validation command wrote `reports/validation_report.json`:

- endpoint types: 2,119 `molecule`→`protein` edges for `molecule_targets_protein`
- molecule anti-join: 0 missing molecules
- protein anti-join: 0 missing proteins
- non-ENSP y IDs: 0
- edges without evidence: 0
- evidence without edge: 0
- rows with predicate/source_record/release/score/target_confidence/target_uniprot/mechanism/source_database metadata: 2,132/2,132

`manage_db.audit_edge_evidence` result: OK (`edges_without_evidence=0`, `evidence_without_edge=0`).

## Residual risks / review points

1. The conservative unambiguous-UniProt gate leaves many ChEMBL protein components unstaged. Reviewer should decide whether a future tranche may expand UniProt accessions to all matching ENSP isoforms, choose canonical isoforms, or add UniProt-primary protein nodes/aliases.
2. ChEMBL API release is recorded as access date (`ChEMBL API 2026-06-22`) because the API response does not expose a compact release tag in the fetched mechanism records.
3. This is staged-only; canonical `kg/v2/edges` and `kg/v2/evidence` were not overwritten.
