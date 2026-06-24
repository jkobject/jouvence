# REL-WAVE-C candidate report: experimental pharmacology and cell-line context

Kanban task: `t_103021f3`
Parent REL-PLAN: `t_cf77187d`
Staging source inspected: `gs://jouvencekb/kg/v2/staging/cell-line-assays-2026-06-22-t_c2b0803c`
Local inspected copy: `.omoc/staging/cell-line-assays-20260623-t_103021f3-from-t_c2b0803c`
QA JSON: `.omoc/reports/t_103021f3_cell_line_assays_wave_c_qa.json`

This report prepares canonical-promotion candidates for the Wave C cell-line pharmacology assay relations. It does **not** claim canonical promotion. The artifacts remain staged-only pending independent tester and reviewer gates.

## Candidate outputs

| Relation | Edge rows | Evidence rows | Source-native assertion | Candidate status |
| --- | ---: | ---: | --- | --- |
| `cell_line_gene_essentiality` | 1,433,992 | 1,433,992 | DepMap/Project Achilles CRISPR gene dependency/essentiality for a cell line and gene | Candidate-ready for independent QA; threshold policy explicit |
| `cell_line_responds_to_molecule` | 11,040 | 11,713 | GDSC/Sanger dose-response viability response for a cell line and molecule | Candidate-ready for independent QA; canonical promotion should review molecule-name mapping breadth |
| `cell_line_expresses_protein` | 3,083 | 3,090 | Direct CCLE/Gygi mass-spectrometry protein abundance for a cell line and protein | Candidate-ready for independent QA; edge/evidence mismatch is explained as many-evidence support |
| `cell_type_found_in_tissue` | - | - | Cell Ontology/UBERON ontology/anatomy mapping | Deferred to ontology Wave D; not mixed into this pharmacology/cell-line assay batch |

## Direct measurement policy

- `cell_line_gene_essentiality`: source-native dependency/essentiality measurement only. Evidence preserves dependency probability, study/source, threshold, cell-line mapping, and gene mapping metadata.
- `cell_line_responds_to_molecule`: source-native drug-screen viability response only. Evidence preserves AUC, IC50, published values, dose-response R2, source dataset/study, threshold, cell-line mapping, and molecule mapping metadata.
- `cell_line_expresses_protein`: direct mass-spectrometry proteomics only. No RNA or mRNA-derived rows are accepted for this relation.
- mRNA/RNA-seq expression was explicitly rejected for `cell_line_expresses_protein` in `source_audit.json`.

## Endpoint and support QA

The QA script copied canonical node Parquets from `gs://jouvencekb/kg/v2/nodes/{cell_line,gene,molecule,protein}.parquet` into `.omoc/staging/cell-line-assays-20260623-t_103021f3-canonical-nodes/` and validated staged edges/evidence against those node IDs.

| Relation | Missing cell-line endpoints | Missing y endpoints | Unsupported edges | Orphan evidence | Duplicate edge rows | Passed |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `cell_line_gene_essentiality` | 0 | 0 genes | 0 | 0 | 0 | yes |
| `cell_line_responds_to_molecule` | 0 | 0 molecules | 0 | 0 | 0 | yes |
| `cell_line_expresses_protein` | 0 | 0 proteins | 0 | 0 | 0 | yes |

`all_endpoint_and_support_checks_passed=true` in `.omoc/reports/t_103021f3_cell_line_assays_wave_c_qa.json`.

## Score, effect, threshold, and assay audit

### `cell_line_gene_essentiality`

- Source: `DepMap/CRISPRGeneDependency`.
- Assay: CRISPR gene dependency.
- Predicate: `dependency_probability_at_or_above_threshold`.
- Threshold: `dependency_probability >= 0.9`.
- Raw rows seen: 1,208; rows with canonical cell line: 1,182.
- Source gene columns: 18,531; mapped gene columns: 18,477.
- Dependency/evidence score summary: count 1,433,992; min 0.9000002693; max 1.0; mean 0.981251; median 0.993571.
- Direction/effect semantics: higher dependency probability means stronger essentiality/dependency support for the `cell_line→gene` edge.

### `cell_line_responds_to_molecule`

- Source: `DepMap/Sanger GDSC dose response`.
- Assay: dose-response viability.
- Predicate: `viability_response_auc_at_or_below_threshold`.
- Threshold: `auc <= 0.7 and R2 >= 0.8`.
- Raw rows seen: 387,626; mapped rows before threshold: 99,625; unique mapped molecule names: 150.
- AUC summary: count 11,713; min 0.0284675504; max 0.6999973799; mean 0.540327; median 0.573285.
- Evidence score is `1 - AUC`: count 11,713; min 0.3000026201; max 0.9715324496; mean 0.459673; median 0.426715.
- Dose-response R2 summary: count 11,713; min 0.8000633760; max 0.9999994770; mean 0.963574; median 0.982449.
- Direction/effect semantics: lower AUC means stronger viability response; evidence score inverts AUC so higher score means stronger response.
- Evidence rows exceed edges by 673 because 667 deduplicated `cell_line→molecule` edges have multiple direct GDSC evidence rows. This is supported many-evidence-per-edge, not orphan evidence.

### `cell_line_expresses_protein`

- Source: `DepMap/Harmonized MS CCLE Gygi`.
- Assay: mass-spectrometry protein abundance.
- Predicate: `direct_ms_protein_abundance_top_n_per_cell_line`.
- Threshold: `top 10 non-null protein abundance values per cell line; direct MS only, no RNA projection`.
- Raw rows seen: 375; rows with canonical cell line: 309.
- Source protein columns: 12,558; mapped protein columns: 12,460.
- Protein abundance/evidence score summary: count 3,090; min 2.8215619407; max 12.5117857232; mean 5.305020; median 5.228133.
- Direction/effect semantics: higher mass-spec abundance means stronger direct protein-expression support for the `cell_line→protein` edge.

## `cell_line_expresses_protein` edge/evidence mismatch

The staged artifact has 3,083 deduplicated edges and 3,090 evidence rows. The QA audit found:

- unique edge keys: 3,083;
- unique evidence edge keys: 3,083;
- unsupported edges: 0;
- orphan evidence rows: 0;
- duplicate edge rows: 0;
- multi-evidence edge count: 7;
- multi-evidence extra rows: 7.

Therefore the 7-row difference is not a missing/extra support error. It is many-evidence-per-edge support: seven canonical `cell_line→protein` edge keys have two distinct direct-MS source records/columns mapping to the same canonical protein endpoint. The detailed source records are preserved in `.omoc/reports/t_103021f3_cell_line_assays_wave_c_qa.json` under `relations.cell_line_expresses_protein.multi_evidence_detail`.

Sample multi-evidence edge keys:

- `cell_line_expresses_protein|ACH-000248|ENSP00000630295`: 2 evidence rows
- `cell_line_expresses_protein|ACH-000785|ENSP00000630295`: 2 evidence rows
- `cell_line_expresses_protein|ACH-000747|ENSP00000628328`: 2 evidence rows
- `cell_line_expresses_protein|ACH-000738|ENSP00000389915`: 2 evidence rows
- `cell_line_expresses_protein|ACH-001307|ENSP00000622826`: 2 evidence rows
- `cell_line_expresses_protein|ACH-000087|ENSP00000642179`: 2 evidence rows
- `cell_line_expresses_protein|ACH-000040|ENSP00000638941`: 2 evidence rows

Recommendation: keep the 3,090 evidence rows rather than collapsing evidence, because each is direct proteomics support for the same deduplicated graph assertion. Tester/reviewer should verify whether canonical evidence policy prefers many-evidence-per-edge preservation, but no endpoint/support fix is required.

## `cell_type_found_in_tissue` deferral

`cell_type_found_in_tissue` is not included in this candidate batch. It is ontology/anatomy context, not experimental pharmacology/cell-line assay evidence. It should be handled with Wave D ontology relations (`cell_type_subtype_of_cell_type`, `cell_type_found_in_tissue`, and related Cellosaurus/metadata context) so reviewers can assess ontology release/provenance and hierarchy semantics together.

## Residual risks and reviewer questions

1. `cell_line_responds_to_molecule` currently maps molecules by unique case-insensitive canonical molecule names. This produced clean endpoint/support QA but may be narrower than a full PRISM/GDSC candidate; reviewer should decide whether this breadth is enough for canonical promotion or remains staged until identifier mapping is expanded.
2. The GDSC relation has many-evidence-per-edge support (673 extra evidence rows). This is expected for repeated study/source rows but should be accepted explicitly under evidence policy.
3. Proteomics uses top 10 non-null protein abundance values per cell line. Reviewer should accept or revise this threshold before canonical promotion.
4. No canonical writes were made. The candidate remains staged-only.

## Commands run

```bash
gsutil -m rsync -r gs://jouvencekb/kg/v2/staging/cell-line-assays-2026-06-22-t_c2b0803c .omoc/staging/cell-line-assays-20260623-t_103021f3-from-t_c2b0803c
gsutil cp gs://jouvencekb/kg/v2/nodes/{cell_line,gene,molecule,protein}.parquet .omoc/staging/cell-line-assays-20260623-t_103021f3-canonical-nodes/
uv run python .omoc/scripts/audit_wave_c_cell_line_assays_t_103021f3.py
```

Additional compile/test/audit commands are recorded in the Kanban handoff.
