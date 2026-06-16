# Variant / transcript / enhancer missing-edge tranche plan

This note locks the source policy for remaining variant, transcript, enhancer,
and phenotype relations. Do not create empty placeholder Parquets for unresolved
relations. Build locally, validate locally, then let the parent perform any
explicit canonical promotion.

2026-06-16 update: the first candidate below, `mutation_causes_phenotype`, has
now been promoted canonically from HP-only pathogenic/likely pathogenic EVA rows
(`25,545` edges, `26,980` evidence support rows, zero dangling endpoints and
zero unsupported/orphan support). The remaining unresolved relations are
`mutation_in_gene`, `mutation_affects_transcript`, `mutation_overlaps_enhancer`,
`enhancer_regulates_transcript`, and `enhancer_associated_disease`.

## Read-only source inspection

Current canonical root, inspected read-only: `/mnt/gcs/jouvencekb/kg/v2`.
Relevant existing canonical inputs are `nodes/mutation.parquet`,
`nodes/transcript.parquet`, `nodes/enhancer.parquet`, `nodes/phenotype.parquet`,
`nodes/disease.parquet`, `edges/enhancer_regulates_gene.parquet`, and the
existing variant/gene/protein disease-association edges.

Bounded metadata/sample inspection found these available source caches:

| Source cache | Metadata rows | Useful columns / role |
| --- | ---: | --- |
| `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-known-variants-scratch/opentargets/evidence_eva` | 4,035,263 | `variantId`, `diseaseId`, `clinicalSignificances`, `variantFunctionalConsequenceId`, `targetId`, `studyId`, `score`, literature/date fields. Candidate source for HP-only `mutation_causes_phenotype`; disease rows remain `mutation_associated_disease`, not phenotype causality. |
| `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-known-variants-scratch/opentargets/evidence_uniprot_variants` | 36,814 | Variant/disease/gene assertions and PMIDs, but endpoints are mainly diseases/genes; not the first phenotype edge source unless an HP endpoint is present. |
| `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0907Z/txgnn-gwas-join-scratch/opentargets/credible_set` | 3,491,182 | GWAS/QTL credible-set variants. Useful only after joining to studies/diseases and, for enhancer disease, interval-overlap evidence. |
| `/mnt/gcs/jouvencekb/kg/scratch/remaining-slices-20260614T220351Z/opentargets/enhancer_to_gene` | 48,810,390 | E2G enhancer intervals and gene endpoints. Already promoted as enhancer nodes / gene regulatory/context edges. No current OpenTargets E2G transcript endpoint is present in this table. |

## Promoted first candidate

Promoted first candidate: `mutation_causes_phenotype` from OpenTargets EVA/ClinVar-style known-variant evidence with `HP:` endpoints, restricted to pathogenic/likely pathogenic clinical significance and germline or otherwise causal assertions. This was the safest of the six because it uses explicit
variant-to-HPO rows, has bounded source columns, does not require an interval
join, and avoids the known `mutation_in_gene` versus `mutation_associated_gene`
semantic trap.

## Relation-specific source-to-edge semantics

| Relation | Source-to-edge rule | Must not do | Required evidence/provenance fields |
| --- | --- | --- | --- |
| `mutation_in_gene` | Use OpenTargets `variant/transcriptConsequences` or equivalent VEP/Ensembl consequence rows only when the row proves physical overlap/containment of the variant in a gene/transcribed locus. Collapse to mutation → ENSG only after endpoint anti-join validation reports zero missing endpoints. | Do not use OpenTargets L2G/GWAS `targetId` association rows, GWAS credible-set gene scores, or the old dense smoke output as containment evidence. Do not treat it as a synonym of `mutation_associated_gene`. | `source_dataset=variant/transcriptConsequences`, source row or variant/transcript composite ID, SO consequence/predicate, transcript ID where present, release. |
| `mutation_affects_transcript` | Use OpenTargets `variant/transcriptConsequences` transcript rows with valid ENST endpoints and a consequence predicate; edge is mutation → transcript. Preserve SO term / consequence severity as evidence, not as the relation name. | Do not promote all variants blindly without cardinality review and endpoint validation. Do not infer transcripts from gene edges. | `source_dataset=variant/transcriptConsequences`, `source_record_id=variantId|transcriptId|consequence`, predicate/SO ID, evidence score/severity if available. |
| `mutation_overlaps_enhancer` | Use a DuckDB interval join against canonical `nodes/enhancer.parquet`: variant chromosome/position overlaps enhancer chromosome/start/end. Edge is mutation → enhancer and means physical interval overlap only. | Do not infer overlap through E2G gene targets. Do not attach disease or gene association semantics to this physical edge. Avoid a Python in-memory range join. | source variant row ID, enhancer interval ID, coordinates/build, overlap method/version, release. |
| `mutation_causes_phenotype` | Use OpenTargets EVA/ClinVar-style known-variant evidence with `HP:` endpoints, normalized from `HP_...` to `HP:...`, and filter to pathogenic/likely pathogenic (or equivalent curated causal) assertions. Edge is mutation → phenotype. | Do not map disease endpoints to phenotypes. Do not use benign/likely benign/uncertain-significance rows for causal phenotype edges. Do not use deprecated `phenotype_caused_by_mutation`. | source `id`, `variantId`, HP endpoint, clinical significance predicate, allele origin, confidence, `studyId`, score, PMID/date where present. |
| `enhancer_regulates_transcript` | Promote only from a transcript-specific enhancer/regulatory source that directly names ENST/TSS/transcript endpoints. No such endpoint was found in current E2G samples. | Do not infer `enhancer_regulates_transcript` from `enhancer_regulates_gene` by expanding a regulated gene to all transcripts. Do not use all gene transcripts or canonical transcript shortcuts. | enhancer ID, ENST endpoint, TSS/transcript-specific method, source record ID, score, biosample/tissue context if present. |
| `enhancer_associated_disease` | Use GWAS/credible-set variant overlap: credible/risk variant → enhancer interval overlap plus a disease/study mapping; collapse to enhancer → disease with support rows preserving study and variant. | Do not use enhancer → gene → disease transitive inference. Do not use E2G gene target disease annotations as enhancer disease association. | source credible-set/study IDs, variant ID, enhancer interval ID, disease ID, posterior probability/p-value/effect size, study metadata, overlap method. |

## Local build gates before parent promotion

1. Build into a local scratch KG root, never `/mnt/gcs/jouvencekb/kg/v2`.
2. Materialize both `edges/{relation}.parquet` and `evidence/{relation}.parquet`
   for any promoted relation; evidence is required for these unresolved edges.
3. Use canonical node snapshots as read-only endpoint universes and require that
   endpoint anti-join validation reports zero missing endpoints for x and y.
4. Audit evidence with `manage_db.audit_edge_evidence` for the specific relation
   and require zero unsupported/orphan support records.
5. Review cardinality before promotion. Interval joins for enhancer overlap and
   enhancer disease should use DuckDB or another bounded external-memory engine.
6. Update `docs/kg_coverage_audit.md`, `docs/evidence_and_edge_schema_plan.md`,
   and `CLAUDE.md` only after a successful local build and parent-approved
   canonical promotion.

## Recommended implementation order

1. ✅ Promoted `mutation_causes_phenotype` from HP-only pathogenic/likely
   pathogenic EVA rows.
2. Separately prototype `mutation_affects_transcript` and `mutation_in_gene`
   from `variant/transcriptConsequences`, with a row-count cap/sample audit first.
3. Prototype `mutation_overlaps_enhancer` with a DuckDB interval join on a single
   chromosome before full run.
4. Leave `enhancer_regulates_transcript` unpromoted until a transcript-specific
   enhancer source is selected.
5. Attempt `enhancer_associated_disease` only after credible-set → disease study
   joins are documented and an interval-overlap prototype validates endpoints.
