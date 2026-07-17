# ReMap CRM canonical-readiness decision

Kanban task: `t_9c0e6a68`  
Date: 2026-06-24  
Decision status: design decision / no canonical writes

## 2026-06-24 reassessment after user correction: CRM/ReMap evidence should target `tf_binds_enhancer`

Kanban task: `t_f558cee3`  
Status: `design update + staged-only prototype`; no canonical writes.

Post-unblock user decision: because ReMap CRM is derived from ReMap ChIP-seq regulatory peak evidence, CRM/ReMap plus recoverable peak/TF/context/metadata and optional motif co-location is the best available source-native evidence for this KG's `tf_binds_enhancer` relation. The correct policy is therefore not to demote the work to a permanent support-only sidecar. Instead, build `tf_binds_enhancer` with explicit evidence classes and caveats: CRM-derived rows can be graph-label material when the evidence table records how the CRM assertion was reconstructed/decomposed and distinguishes ChIP/ReMap support, motif support, antibody/protein metadata coverage, context coverage, and leakage policy.

Jérémie's clarification is correct: ReMap CRM is derived from ReMap ChIP-seq signal and can be decomposed enough to recover peak/TF/context support when joined back to the ReMap peak catalogs. The CRM BED itself is still not a per-experiment evidence table: it carries a CRM interval, comma-separated regulator symbols, and an aggregate score/count-like value, but not source peak IDs, experiment accessions, antibody/protein metadata, or cell/biotype context.

Bounded prototype artifact:

- Script: `artifacts/staged/t_f558cee3/remap_crm_peak_decomposition_prototype.py`
- Report: `artifacts/staged/t_f558cee3/reports/remap_crm_peak_decomposition_prototype_report.md`
- JSON: `artifacts/staged/t_f558cee3/reports/remap_crm_peak_decomposition_prototype_report.json`
- Outputs: `artifacts/staged/t_f558cee3/support_candidates/*.parquet`

Prototype scope and observed counts:

- First 80 chr1 CRM intervals from `artifacts/staged/t_b599d3bb/full_local/source_cache/remap2022_crm_selected.bed`, coordinate window `chr1:9829-909043`.
- CRM regulator mentions in subset: 2,405.
- Same-TF ReMap `all` peak overlaps reconstructed by coordinate join: 6,876 rows.
- CRM rows with at least one same-TF ReMap `all` peak support row: 80/80.
- Distinct recovered ReMap `all` source accessions: 1,846.
- Distinct recovered ReMap `all` biotypes: 1,421.
- Same-TF ReMap `nr` peak overlaps: 2,492 rows; distinct `nr` biotypes: 672.
- ReMap biotype metadata XLSX was reachable and matched 230 biotype rows for the bounded sample.

Decomposability assessment:

- Underlying ReMap peaks/experiments: recoverable from `remap2022_all_macs2_hg38_v1_0.bed.gz` by reconstructed same-chromosome interval overlap plus same TF symbol. This is not a source-provided CRM→peak foreign key, so evidence must record the reconstruction policy and cannot imply CRM-native provenance.
- TF identity / target symbol / Ensembl mapping: CRM and peak rows expose TF/regulator symbols; existing KG symbol mapping can map accepted symbols to TF gene endpoints. The graph endpoint should remain `gene` for TF/regulator, preferably Ensembl `ENSG`, with ambiguous/rejected symbols quarantined.
- Antibody/protein metadata: not present in the inspected CRM, `all`, or `nr` BED rows. BED names recover source accession, TF symbol, and biotype; they do not expose antibody lot/target/protein accession. Any antibody-level claim requires an additional ReMap/ENCODE/GEO metadata source, not the BED alone.
- Assay/biosample/cell/tissue metadata: `all` recovers `source_accession.TF.biotype`; `nr` recovers `TF:biotype`; the ReMap biotype XLSX can add descriptions/ontology-like metadata where present. CRM alone does not carry context.
- Motif co-location: not available in current local artifacts. It is computable as a separate staged JASPAR/HOCOMOCO motif-hit table joined by same TF gene, same enhancer, same genome build, and motif/peak overlap. Motif-only rows remain support candidates and must not create active edges.

Updated recommendation:

- Keep the already promoted `features/remap_crm_tf_enhancer_support.parquet` as its accepted bounded feature/QA sidecar; do not rewrite that artifact in this card.
- The next staged candidate should use the canonical relation label `tf_binds_enhancer`, not a support-only replacement label, because ReMap CRM is ChIP-seq-derived regulatory binding evidence. The edge label is justified if every active edge has an evidence row proving at least one source-backed ReMap/CRM support path for the same TF and enhancer interval.
- Strongest evidence class: ReMap `all` peak-primary rows overlapping an accepted enhancer, with CRM support and motif support attached. These rows carry `evidence_type = observed_binding` or `observed_binding_peak` because the source record is an observed ReMap peak and preserves source accession/biotype.
- Acceptable CRM-derived evidence class: CRM regulator/enhancer rows linked back to same-TF ReMap peak support by the reconstructed coordinate policy, or otherwise explicitly marked as `crm_reconstructed_binding_support`. These can support active `tf_binds_enhancer` under the user-approved ontology, but the evidence row must say the CRM did not itself preserve a source peak foreign key, experiment accession, antibody field, or cell context.
- Motif co-location is strengthening evidence for the same `tf_binds_enhancer` edge, not an alternate relation. Motif-only candidate rows may be retained as evidence/features but should not be the sole active-edge support unless a later human policy explicitly accepts motif-only predicted binding.

Proposed schema for the next staged peak-supported candidate:

- Edge table, staged only until reviewed: `edges/tf_binds_enhancer.parquet` with `x_id` TF gene, `x_type = gene`, `y_id` enhancer, `y_type = enhancer`, `relation = tf_binds_enhancer`, `source = ReMap2022`, and `supporting_observed_evidence_count`.
- Evidence table: `evidence/tf_binds_enhancer.parquet` with `edge_key`, `source_dataset`, `source_release`, `evidence_type` (`observed_binding`, `crm_support`, or `motif_support`), `predicate`, `tf_id_namespace`, `source_tf_id`, `tf_gene_id`, `enhancer_id`, `genome_build`, harmonized and original coordinates, `source_record_id`, and `original_id`.
- ReMap observed fields: `remap_file`, `remap_peak_name`, `remap_source_accession`, `remap_tf_symbol`, `remap_biotype`, optional mapped biosample fields from biotype XLSX, `assay = ReMap regulatory ChIP peak`, `peak_score`, `strand`, `summit_start`, `summit_end`, `item_rgb`, `overlap_bp`, `peak_fraction_overlap`, `enhancer_fraction_overlap`, `summit_within_enhancer`, and `context_match_level`.
- CRM support fields on linked evidence/feature rows: `crm_source_record_id`, `crm_chromosome`, `crm_start`, `crm_end`, `crm_regulators`, `crm_regulator_count`, `crm_score`, `crm_overlap_bp`, `crm_fraction_overlap`, and `crm_to_peak_link_policy = reconstructed_coordinate_overlap_same_tf`.
- Antibody/protein fields: nullable `antibody_target`, `antibody_id`, `antibody_lot`, `protein_accession`, and `metadata_source`; populate only if a separate source metadata table is joined, otherwise leave null and report coverage as zero.
- Motif fields: nullable `motif_source`, `motif_id`, `motif_tf_symbol`, `motif_family`, `motif_model_type`, `motif_threshold`, `motif_score`, `motif_pvalue`, `motif_start`, `motif_end`, `motif_overlaps_peak`, `supported_observed_evidence_id`, and `motif_only_candidate`.
- Leakage policy: ReMap peak/CRM/motif regulatory evidence must be excluded from supervised labels for `tf_binds_enhancer`, `enhancer_regulates_gene`, disease/drug prediction, or any target constructed from overlapping regulatory evidence unless the split policy explicitly prevents leakage.

Next recommended card:

- `REMAP-CRM-TF-BINDS-ENHANCER-PILOT: stage bounded tf_binds_enhancer candidate from ReMap CRM/peaks with motif and metadata evidence fields`.
- Non-goals: no canonical write in the pilot, no `tf_regulates_gene`, no silent motif-only active edges, no claim that CRM BED rows contain antibody/protein metadata unless a separate metadata source is joined.
- Scope: bounded chromosome/window first; materialize deduped `edges/tf_binds_enhancer` candidates and `evidence/tf_binds_enhancer` rows; run endpoint anti-joins, evidence support audit, duplicate edge/evidence checks, context/metadata coverage report, and reviewer acceptance before any canonical promotion planning.

## Short answer

The accepted ReMap CRM sidecar remains useful as a bounded QA/support feature, but the corrected ontology direction is that ReMap CRM/peak/motif evidence should feed a staged `tf_binds_enhancer` edge/evidence candidate. CRM-derived caveats belong in `evidence/tf_binds_enhancer` fields, not in a permanent support-only relation name.

Recommended safe target:

- Stage, but do not canonically write in this card, `edges/tf_binds_enhancer.parquet` plus `evidence/tf_binds_enhancer.parquet` from ReMap CRM/peak evidence.
- Preserve the already promoted `features/remap_crm_tf_enhancer_support.parquet` as its accepted bounded support/QA sidecar; do not reinterpret or overwrite that object here.
- Do not write or infer `edges/tf_regulates_gene.parquet` from CRM support.

This is a policy/readiness decision only. Any canonical `tf_binds_enhancer` write requires a separate staged pilot, validation, and reviewer approval.

## Evidence consumed

Primary artifact/report:

- `docs/remap_crm_tf_binds_enhancer_support_allchrom_5kperchrom_t_b599d3bb_report.md`
- Staged GCS prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-allchrom-5kperchrom-20260623-t_b599d3bb/all_chrom_5k_per_chrom/`
- Local staged root: `artifacts/staged/t_b599d3bb/all_chrom_5k_per_chrom`

Relevant accepted artifact facts:

- Source: ReMap 2022 CRM hg38 file `remap2022_crm_macs2_hg38_v1_0.bed.gz`.
- Scope: all chromosomes, bounded to up to 5,000 CRM intervals per chromosome; chrY had 2,571 CRM intervals and no accepted enhancer overlaps in this tranche.
- CRM intervals selected: 117,571.
- Regulator mentions: 3,241,105.
- Accepted TF mentions: 3,172,778.
- Distinct accepted TF gene IDs before materialization: 1,176.
- Distinct supported TF IDs after enhancer-overlap filtering: 1,169.
- Interval/enhancer overlaps: 6,232,552 accepted rows.
- Candidate support rows before compacting: 1,442,646,529.
- Compact support summary rows: 2,915,130.
- Endpoint anti-joins: TF gene endpoint anti-join 0; enhancer endpoint anti-join 0.
- Explicit semantic guards in report: `observed_binding_rows: 0`, `tf_regulates_gene_rows: 0`, `no_edges_directory: True`, `no_evidence_directory: True`, `ok: True`.
- Reported caveats: CRM rows do not preserve per-experiment source accession; CRM column 5 is treated as aggregated support/count-like score, not raw per-experiment peak score; sampled CRM rows lack cell/biotype context.

Current relation context:

- `docs/relation_coverage_current.md` lists `tf_binds_enhancer` as active but `staged-only/deferred`, with the note: do not promote all-peak ReMap or motif-only support as canonical TF→enhancer edges without an approved CRM/endpoint policy.
- `docs/relation_coverage_current.md` lists `tf_regulates_gene` as `schema-only/missing`: choose a concrete source and endpoint/evidence policy before any build.
- Older backlog wording says the accepted ReMap-family CRM sidecar has `crm_aggregated_support` semantics and is not itself primary observed-binding material. This remains true for that feature object, but is superseded for future edge work by the user-approved `tf_binds_enhancer` evidence policy in this section.

## Canonical target decisions

### 1. Canonical `tf_binds_enhancer` edge/evidence candidate

Decision: appropriate next target after a bounded staged pilot and review.

Suggested table names:

- `edges/tf_binds_enhancer.parquet`
- `evidence/tf_binds_enhancer.parquet`

Suggested row semantics:

- A graph edge asserts that a TF/regulator gene product binds an accepted enhancer/regulatory interval, supported by ReMap CRM/peak evidence on the same TF and interval.
- Evidence rows carry the specific support class: `observed_binding_peak`, `crm_reconstructed_binding_support`, `motif_support`, and, if found later, `antibody_metadata_support` or equivalent.
- The strongest active edge support is ReMap `all` observed peak evidence. CRM-derived support is acceptable for the relation under the corrected user policy when the evidence row explicitly records that the CRM-to-peak/source support was reconstructed or metadata-limited.

Minimum required schema/gates before canonical write:

- Endpoint columns: TF gene ID and enhancer ID must anti-join 0 against canonical `nodes/gene.parquet` and `nodes/enhancer.parquet`.
- Coordinate columns: CRM, peak, motif, and enhancer coordinates must be explicitly hg38/GRCh38; reject mixed build or unmapped contigs; no liftover is implicit.
- Provenance columns: source database (`ReMap`), source release (`2022`), source file URL/checksum if available, CRM coordinate key/source record ID, ReMap peak name/source accession when recoverable, source task/report references, and reconstruction policy.
- TF mapping columns: original symbol, accepted Ensembl gene ID, mapping source, mapping status, and ambiguity/rejection counts must be preserved or linkable; ambiguous/rejected symbols stay out of active edge rows but are reported.
- Evidence model: active edges must have at least one evidence row whose class is ReMap/CRM ChIP-derived binding support. Motif-only evidence remains non-active unless a later explicit human decision accepts predicted-binding-only edges.
- Antibody/protein fields are nullable and must report coverage; do not imply antibody or protein accession support from BED rows alone.
- Scale/fullness: either a bounded pilot with explicit scope or a full/unbounded feasible build; table metadata must not imply full ReMap if the promoted artifact is bounded.
- GNN leakage/use policy: ReMap peak/CRM/motif regulatory evidence must be excluded from supervised labels for `tf_binds_enhancer`, `enhancer_regulates_gene`, disease/drug prediction, or any target constructed from overlapping regulatory evidence unless the split policy explicitly prevents leakage.
- Audit: write a promotion report under `docs/`, a machine-readable validation report under `artifacts/reports/` or canonical report namespace, run endpoint/evidence/duplicate audits, and require tester/reviewer approval before canonical write.

What is still missing today:

- A staged edge/evidence materialization that uses the corrected relation-label policy.
- Full TF symbol mapping and endpoint anti-joins against current canonical gene/enhancer nodes.
- Motif scan/hit table and optional antibody/protein metadata source if those fields are to be populated rather than reported null.
- Reviewer acceptance of the staged evidence-class policy.

### 2. Existing support/QA feature sidecar

Decision: preserve as already accepted; do not overwrite in this card.

Existing table:

- `features/remap_crm_tf_enhancer_support.parquet`

This table remains a bounded `crm_aggregated_support` feature/QA sidecar from prior accepted work. It is not the final edge/evidence schema, but it is useful for QA, triage, and supporting features and can inform the next `tf_binds_enhancer` pilot.

### 3. Support-only / inferred relation namespace

Decision: no longer the default recommendation.

A support-only relation such as `edges_inferred/remap_crm_supports_tf_enhancer.parquet` may still be useful for tooling that needs non-label topology, but it should not replace the user-approved `tf_binds_enhancer` path for ReMap CRM/peak evidence.

### 4. Canonical TF-regulates-gene edge (`tf_regulates_gene`)

Decision: not appropriate from the current CRM support artifact.

Why not:

- CRM support links TF/regulator mentions and enhancer intervals; it does not name regulated target genes or expression effects.
- Overlapping a TF-supported CRM to an enhancer is not the same as TF→gene regulation.
- Even combining CRM support with canonical `enhancer_regulates_gene` would create a derived inference chain, not a source-native TF→gene assertion.
- Current relation docs list `tf_regulates_gene` as `schema-only/missing` and require a concrete source with explicit TF→target regulation, direction/sign/effect/assay.

What would be required:

- Source semantics: TF target source with explicit regulator→target gene assertions, or a reviewed inference policy that labels rows as inferred and preserves all support components.
- Endpoint validation: TF gene and target gene anti-joins 0 against canonical gene nodes.
- Evidence model: direction, sign/effect when available, assay/source database, score/confidence, record IDs, and whether the assertion is direct or inferred.
- CRM vs peak distinction: current CRM support may be one feature in an inference model, but cannot be the only evidence for canonical direct TF regulation.
- Motif/assay support: motif and enhancer support must be separate evidence fields, not relabelled as regulation.
- GNN leakage/use policy: inferred TF→gene edges are high leakage risk for downstream gene/disease/drug predictions and require an explicit split policy before graph inclusion.

Blocked path:

- Do not infer or write `tf_regulates_gene` from this CRM support artifact.

## Next safe step

Create a staged pilot follow-up for the corrected edge/evidence target:

- Title: `REMAP-CRM-TF-BINDS-ENHANCER-PILOT: stage bounded tf_binds_enhancer candidate from ReMap CRM/peaks with motif and metadata evidence fields`
- Assignee: `dev`
- Exact staged targets: `edges/tf_binds_enhancer.parquet` candidate and `evidence/tf_binds_enhancer.parquet` candidate under `artifacts/staged/<task-id>/`, not canonical KG paths.
- Input: accepted staged CRM support artifact from `t_b599d3bb`, source ReMap `all`/`nr`/`crm` files, ReMap biotype metadata, TF mapping files, canonical gene/enhancer nodes, and optional motif hit tables if staged.
- Required gates: endpoint anti-joins, hg38 coordinate audit, TF mapping ambiguity report, evidence class counts, CRM reconstruction-policy coverage, motif-only active-edge guard, antibody/protein metadata coverage report, duplicate edge/evidence checks, leakage policy, promotion report, tester validation, reviewer approval.
- Explicit non-goals: no canonical write, no `tf_regulates_gene`, no claim of antibody/protein metadata where unavailable, no silent motif-only active edges.

This follow-up can execute only after this readiness decision is validated and reviewed. If reviewer rejects the evidence-class policy, the pilot card should be corrected before any canonical write.
