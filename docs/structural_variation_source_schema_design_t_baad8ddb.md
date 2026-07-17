# Structural-variation source/schema design for Jouvence KG

Task: `t_baad8ddb`
Date audited: 2026-07-08 CEST
Scope: design/source audit only. No ingestion, canonical KG write, bulk KG scan, LaminDB sync, PyG/GNN export, embedding job, ReMap job, or macOS GCS-FUSE scan was performed.

## Inputs read

- `AGENTS.md` operating constraints: VM-only for heavy TxGNN jobs; no canonical writes without explicit review; use broad relations with source nuance in evidence.
- `TODO.md` operating rules and mutation current-state section: current OpenTargets mutation direct relations include `mutation_affects_transcript`, `mutation_in_gene`, and support-gated `mutation_overlaps_enhancer`; coordinate-only enhancer overlap is context/support-only, not observed regulatory evidence.
- `docs/database_gap_analysis_202606.md`, especially “Concrete source decision matrix — 2026-06-22 follow-up”: DGV/dbVar/gnomAD-SV/ClinGen/ClinVar-SV are a clear design-first gap; no DGV/dbVar/gnomAD-SV provenance is exposed in current canonical mutation rows.
- Existing card `t_97c6a56d`: same design-only acceptance criteria, currently still `todo`; this task is the bounded Mac-disk-safe continuation, not an unblock of broad capacity guard `t_c9674d3f`.

## Source URLs checked

Tool note: configured `web_search`/`web_extract` are unavailable in this profile because Firecrawl is not configured, so this audit used direct small HTTP/HEAD probes through Python `urllib`; no bulk source files were downloaded.

| Source | URL(s) checked on 2026-07-08 | Access/license observation | Role in SV tranche |
| --- | --- | --- | --- |
| dbVar | https://www.ncbi.nlm.nih.gov/dbvar/ ; https://ftp.ncbi.nlm.nih.gov/pub/dbVar/data/Homo_sapiens/by_study/ | NCBI public website/FTP are reachable. The FTP directory exposes per-study CSV/GVF/TSV/VCF/XML/genotype/remap subdirectories and was last modified on the audit date. NCBI pages are US government `.gov`; still preserve submitter/study attribution and do not assume consent for controlled dbGaP-derived individual-level data. | Primary public archive for submitted human structural variation studies and clinical/population SV records; use as source-backed evidence and source ID crosswalks, not as automatically curated pathogenicity. |
| ClinVar SV | https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/ ; https://www.ncbi.nlm.nih.gov/clinvar/docs/variation_report/ ; https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz | ClinVar documentation and GRCh38 VCF endpoint are reachable; VCF endpoint exists but was only HEAD-checked (content length ~192 MB, not downloaded). ClinVar is an NCBI public archive of submitted clinical assertions; preserve submitter, review status, condition, clinical significance, variation/accession IDs, and assertion criteria. | Main open clinical-assertion source for SVs and other variants when VCF/XML fields indicate SV type/coordinates. Best feeds `mutation_associated_disease` and `mutation_associated_phenotype` evidence. |
| ClinGen dosage / curated CNV pathogenicity | https://www.clinicalgenome.org/docs/terms-of-use/ ; https://search.clinicalgenome.org/kb/gene-dosage | ClinGen terms/citation page is reachable; Dosage Sensitivity Curations page is reachable. Treat as public curated clinical genomics resource requiring citation/attribution and preservation of curation status/date. | Highest-priority curated dosage/pathogenicity layer for haploinsufficiency/triplosensitivity of genes/regions. Should not be collapsed into population frequency. |
| gnomAD-SV | https://gnomad.broadinstitute.org/terms ; https://gnomad.broadinstitute.org/about | Browser pages are reachable but JS-heavy in direct HTTP extraction, so current terms must be re-checked by reviewer/implementation before redistribution. Broad/gnomAD terms page URL is recorded; do not ingest until exact terms and release path are confirmed. | Population/control allele-frequency and sample-count source. Use for background prevalence, filtering, and benign/common evidence; not clinical pathogenicity by itself. |
| DGV / DGVa / EVA SV | https://www.ebi.ac.uk/dgva/about | EBI DGVa/EVA page states EVA is an open-access database of all types of genetic variation data from all species and that users can download data from any study. The Toronto DGV-specific license/download terms should still be checked before any DGV-specific ingestion because this task did not bulk-inspect DGV files. | Population/control SV catalog; useful for benign/common structural variation and overlap statistics. Keep separate from disease assertions. |
| DECIPHER | https://www.deciphergenomics.org/about/data-sharing | Public browser/search page reachable, but DECIPHER contains patient/clinical genomic data and should be treated as restricted/license-gated. Do not ingest or redistribute DECIPHER patient-level/variant assertions without explicit project license/terms approval. | No-go by default; use only as a future licensed clinical source. |

## Content-class comparison and priority

1. Clinical/curated priority: ClinGen dosage + ClinVar-SV.
   - Why: best fit for disease/phenotype assertions and clinical interpretability.
   - Evidence value: clinical significance, dosage sensitivity, review status, condition terms, assertion date, submitter/curator, PubMed/criteria where available.
   - Risk: clinical assertions can conflict and change; keep each assertion in evidence rows, do not collapse all sources into a single truth label.

2. Public archive/source crosswalk priority: dbVar.
   - Why: captures many submitted SV studies and identifiers, including clinical and population studies.
   - Evidence value: study/source IDs, sample/platform/method, coordinates, variant type, genotype/allele observations where exposed.
   - Risk: dbVar is an archive; pathogenicity/clinical assertions depend on submitted interpretation and should be provenance-scoped.

3. Population/control priority: gnomAD-SV and DGV/DGVa.
   - Why: essential background frequency/commonness and benign control variation.
   - Evidence value: allele frequency, allele count, sample count, population stratification, variant type/size, release, filters/confidence.
   - Risk: never map population frequency alone to pathogenicity; use it for evidence context, common-variant filtering, and confidence scoring.

4. Restricted/no-go default: DECIPHER.
   - Why: clinically valuable but patient/clinical dataset terms are not broadly open.
   - Policy: record as license-gated; no ingestion until explicit approval documents permitted use/redistribution.

## Proposed `mutation` node metadata extensions for SVs

Keep the existing broad `mutation` node family, but add nullable/source-preserving SV metadata rather than creating placeholder node types.

Required stable fields:

- `variant_type`: normalized Sequence Ontology/SV type, e.g. `deletion`, `duplication`, `copy_number_gain`, `copy_number_loss`, `inversion`, `insertion`, `translocation`, `complex_structural_alteration`, `mobile_element_insertion`, `tandem_duplication`.
- `variant_subtype`: source-native subtype when more specific than the normalized type.
- `assembly`: `GRCh37`, `GRCh38`, or source-specific assembly label.
- `chromosome`, `start`, `end`: 1-based closed coordinates for interval representation; record `coordinate_system` if source uses VCF 1-based POS + INFO/END semantics.
- `breakend_1`, `breakend_2`: structured strings or JSON for translocations/BNDs where a single interval is insufficient.
- `length_bp`: signed or absolute length; prefer source-native length plus computed length when coordinates are valid.
- `reference_allele`, `alternate_allele`, `allele_repr`: keep VCF symbolic alleles (`<DEL>`, `<DUP>`, `BND`) and sequence alleles where present.
- `source_variant_ids`: JSON/list preserving dbVar `nsv/essv/ssv` IDs, ClinVar VCV/RCV/Variation IDs, gnomAD variant IDs, DGV IDs, ClinGen region/gene curation IDs.
- `source_study_ids`: study/accession IDs such as dbVar study, BioProject/BioSample/dbGaP where public.
- `source_release`: source release/date/build.
- `method_platform`: array or JSON for array CGH, SNP array, WGS short-read, long-read, optical mapping, curated literature, submitter assertion, etc.
- `confidence`: source-native quality/filter/confidence plus normalized `high|medium|low|unknown` if justifiable.

Evidence-specific fields, not node-level defaults:

- `allele_frequency`, `allele_count`, `allele_number`, `sample_count`, `population`, `cohort`, `ancestry`, `case_control_status` for DGV/gnomAD/dbVar population evidence.
- `clinical_significance`, `review_status`, `condition_id`, `condition_label`, `mode_of_inheritance`, `dosage_score`, `haploinsufficiency_score`, `triplosensitivity_score`, `assertion_status`, `curation_date` for ClinVar/ClinGen clinical evidence.
- `submitter`, `curator`, `citation`, `pmid`, `study_design`, `phenotyping_method` where available.

## Relation mapping

Use existing broad relations where their assertion semantics remain true; source-specific nuance belongs in evidence.

| Relation | SV mapping decision |
| --- | --- |
| `mutation_in_gene` | Use for interval containment/overlap against gene loci when the source asserts or coordinate validation supports gene membership. For broad CNVs spanning many genes, keep evidence with overlap basis (`fully_contains_gene`, `partial_overlap`, `breakpoint_in_gene`) and avoid implying the same mechanism for all genes. |
| `mutation_affects_transcript` | Use only when source-native transcript consequence, VEP/SO consequence, or reviewed transcript impact exists. Do not infer transcript effect from any interval overlap alone; overlap can create a support/context candidate that must be validated separately. |
| `mutation_overlaps_enhancer` | Keep as context/support-only unless external evidence specifically supports regulatory consequence. Existing project doctrine says coordinate-only enhancer overlap is not observed regulation. SVs may generate candidate overlaps, but canonical edge promotion would require the same support-gated policy used by the current mutation-overlaps-enhancer work. |
| `mutation_associated_disease` | Use for ClinVar-SV, ClinGen curated dosage/pathogenicity, and dbVar clinical assertions when disease endpoints normalize to current disease nodes. Preserve clinical significance/review status/submitter or curator per evidence row. |
| `mutation_associated_phenotype` | Use when phenotype endpoints normalize to HPO/phenotype nodes from ClinVar/dbVar/ClinGen or licensed DECIPHER-like sources. Preserve source condition/phenotype text and evidence origin. |
| Potential new relation: `mutation_has_population_frequency` | Do not add as an edge relation now. Population frequencies are evidence/feature context on mutation nodes or evidence sidecars, not biological binary edges. Revisit only if a feature schema requires first-class cohort/frequency observations. |
| Potential new relation: `mutation_disrupts_region` | Defer. For now represent region overlaps through existing enhancer/transcript/gene relations plus evidence fields. Add only after a schema review if recurrent region/pathogenic CNV assertions need a non-gene endpoint. |

## Assembly and liftOver policy

- Prefer source-native coordinates and assembly as the immutable evidence record.
- Canonical coordinate representation for new SV nodes should be GRCh38 where exact mapping is available and source terms allow derived coordinates.
- Do not silently liftOver large/complex SVs. LiftOver is allowed only when:
  - both endpoints map uniquely and preserve chromosome/orientation where relevant;
  - interval length change is within a configured tolerance or is explicitly flagged;
  - no centromere/gap/patch ambiguity is introduced;
  - source-native coordinates remain in evidence fields.
- For BND/translocation/complex records, require breakend-aware mapping; if not available, keep source-native assembly and mark `liftOver_status=not_attempted_or_unsupported`.
- If a relation candidate depends on lifted coordinates, evidence must include `coordinate_derivation=liftover`, tool/version/chain file, mapping status, and failure reason for rejected records.

## Validation plan before any ingestion/promotion

Endpoint anti-joins:

- `mutation_in_gene`: anti-join normalized gene endpoints against canonical gene IDs; require evidence that source gene symbols/IDs were resolved and ambiguous symbols were dropped or disambiguated.
- `mutation_affects_transcript`: anti-join transcript endpoints against canonical transcript IDs; reject transcript-free coordinate-only candidates.
- `mutation_overlaps_enhancer`: anti-join enhancer endpoints against canonical enhancer IDs; require support-gated evidence if canonical edge is proposed.
- `mutation_associated_disease`: anti-join disease endpoints against MONDO/EFO/current disease nodes; preserve unmapped source condition text in rejected/remap reports.
- `mutation_associated_phenotype`: anti-join phenotype endpoints against HPO/current phenotype nodes.

Duplicate/overlap checks:

- Deduplicate exact source assertions by `(source, source_release, source_variant_id, relation, subject_id, object_id, predicate_or_assertion, condition_id)`.
- Deduplicate graph edges separately from evidence rows: one edge can have multiple evidence rows from ClinVar submitters, ClinGen curations, dbVar studies, and population catalogs.
- Cluster SV nodes for near-duplicate intervals only for reporting/crosswalk; do not merge distinct source variants solely because reciprocal overlap is high. Use type-aware reciprocal overlap thresholds, e.g. 0.5/0.8 for CNVs depending on source, exact breakpoints for sequence-resolved events, and breakend matching for translocations.
- Flag multi-gene CNVs and very large events separately; avoid generating unbounded gene/enhancer edge explosions without max-span and review gates.
- Compare gnomAD/DGV population evidence against clinical assertions to identify common variants with pathogenic labels, but treat conflicts as evidence review signals, not automatic deletion.

No-go cases:

- DECIPHER or any patient-level restricted source without explicit license/approval.
- Any source requiring bulk data download on Mac while disk guard is active; route a separate `must_run_on=txgnn-worker` card instead.
- Any SV with unknown assembly used for coordinate relations.
- Any ambiguous/multi-mapped liftOver used as if exact.
- Coordinate-only enhancer overlap promoted as observed regulatory evidence.
- Population frequency interpreted as disease association/pathogenicity.
- Placeholder Parquets or empty schema coverage artifacts.

## Recommended follow-up card shape

When disk/worker capacity allows, create a VM-only small pilot card, not a Mac-local bulk job:

- `must_run_on=txgnn-worker`.
- Inputs: one tiny bounded source sample per class, e.g. ClinVar GRCh38 SV subset by INFO/SVTYPE, dbVar one or two public studies, ClinGen dosage export/API sample, and gnomAD/DGV metadata/sample rows only after terms are confirmed.
- Outputs: staged-only `artifacts/staged/<task-id>/` or `gs://jouvencekb/kg/staging/source-native-expansion/sv-pilot-<task-id>/`; no canonical writes.
- Required validation: endpoint anti-joins, source/license manifest, schema conformance, duplicate/overlap report, assembly/liftOver report, and reviewer gate.

## Explicit non-actions

- No ingestion was run.
- No canonical KG write or promotion was performed.
- No Parquet/DuckDB scan over canonical KG was performed.
- No LaminDB sync, embedding, PyG/GNN export/training, ReMap, or all-relation work was performed.
- No `/Users/jkobject/mnt/gcs/...` macOS GCS-FUSE path was read or scanned.
