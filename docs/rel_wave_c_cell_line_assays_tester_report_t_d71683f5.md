# REL-WAVE-C tester report: experimental pharmacology and cell-line QA

Verdict: PASS

Staging root tested: `.omoc/staging/cell-line-assays-20260623-t_103021f3-from-t_c2b0803c`
Canonical node cache: `.omoc/staging/cell-line-assays-20260623-t_103021f3-canonical-nodes`
Machine-readable QA: `.omoc/reports/t_d71683f5_rel_wave_c_tester_qa.json`

## Per-relation results

### `cell_line_gene_essentiality` — PASS
- edges/evidence: 1433992 / 1433992; unique edge/evidence keys: 1433992 / 1433992
- endpoint anti-joins: missing cell_line=0, missing_gene_endpoints=0
- support/duplicates: unsupported_edges=0, orphan_evidence_keys=0, duplicate_edge_rows=0, duplicate_edge_source_record_rows=0
- evidence source/predicate/threshold: {'CRISPRGeneDependency.csv': 1433992} / {'dependency_probability_at_or_above_threshold': 1433992} / {'dependency_probability >= 0.9': 1433992}
- threshold/sign sanity: dependency_probability min=0.9000002693127153, max=1.0, bad_threshold_rows=0; higher dependency_probability/evidence_score/effect_size means stronger essentiality; min is >=0.9

### `cell_line_responds_to_molecule` — PASS
- edges/evidence: 11040 / 11713; unique edge/evidence keys: 11040 / 11040
- endpoint anti-joins: missing cell_line=0, missing_molecule_endpoints=0
- support/duplicates: unsupported_edges=0, orphan_evidence_keys=0, duplicate_edge_rows=0, duplicate_edge_source_record_rows=0
- evidence source/predicate/threshold: {'sanger-dose-response.csv': 11713} / {'viability_response_auc_at_or_below_threshold': 11713} / {'auc <= 0.7 and R2 >= 0.8': 11713}
- threshold/sign sanity: AUC min=0.0284675503941357, max=0.699997379882058; R2 min=0.8000633760165424, max=0.9999994770141958; evidence_score min=0.300002620117942, max=0.9715324496058643; bad_threshold_rows=0; lower AUC means stronger response; evidence_score=1-AUC so higher score means stronger response
- many-evidence support: 667 edge keys have extra rows (673 extra evidence rows), with no orphan evidence.

### `cell_line_expresses_protein` — PASS
- edges/evidence: 3083 / 3090; unique edge/evidence keys: 3083 / 3083
- endpoint anti-joins: missing cell_line=0, missing_protein_endpoints=0
- support/duplicates: unsupported_edges=0, orphan_evidence_keys=0, duplicate_edge_rows=0, duplicate_edge_source_record_rows=0
- evidence source/predicate/threshold: {'harmonized_MS_CCLE_Gygi.csv': 3090} / {'direct_ms_protein_abundance_top_n_per_cell_line': 3090} / {'top 10 non-null protein abundance values per cell line; direct MS only, no RNA projection': 3090}
- direct-proteomics sanity: RNA-like actual provenance evidence rows=0; protein_abundance min=2.82156194072953, max=12.5117857231801; bad_threshold_rows=0; higher direct MS protein_abundance/evidence_score/effect_size means stronger protein expression
- edge/evidence mismatch validated: True — evidence_minus_edges=7, multi_evidence_edge_count=7, multi_evidence_extra_rows=7, unsupported/orphan=0/0.
- multi-evidence examples: cell_line_expresses_protein|ACH-000040|ENSP00000638941 => P12110, P12110-2; cell_line_expresses_protein|ACH-000087|ENSP00000642179 => P10636-2, P10636-8; cell_line_expresses_protein|ACH-000248|ENSP00000630295 => O75363, O75363-2; cell_line_expresses_protein|ACH-000738|ENSP00000389915 => Q13491-3, Q13491-4; cell_line_expresses_protein|ACH-000747|ENSP00000628328 => P11137, P11137-4; cell_line_expresses_protein|ACH-000785|ENSP00000630295 => O75363, O75363-2; cell_line_expresses_protein|ACH-001307|ENSP00000622826 => Q13642, Q13642-4

### `cell_type_found_in_tissue` — PASS_not_included_deferred
- edge_file_exists=False, evidence_file_exists=False; deferral to ontology Wave D is consistent with builder handoff.

## Canonical write check
- No promotion/canonical write command was run by tester. Builder report states staged-only.
- Checked target relation paths under `/mnt/gcs/jouvencekb/kg/v2/{edges,evidence}`: none of the Wave C relation parquet paths are present there in this mounted canonical root check.

## Reviewer notes / residual risks
- PASS is for staged artifact correctness and evidence support. Reviewer still needs policy acceptance for GDSC molecule-name mapping breadth, many-evidence-per-edge preservation, and proteomics top-10 threshold before promotion.
