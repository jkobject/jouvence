# Relation gaps wave: gene/tissue/disease/phenotype set

> **Supersession note (2026-07-22):** consolidated reviewer `t_2d1f767d` accepted the exact narrow canonical `disease_manifests_in_tissue` revision. Producer-time `review-required` rows below are historical; the narrow HPA/TCGA scope remains unchanged.

Kanban task: `t_badd3e1e`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Status: staged-only/source-audit for the original producer task; no canonical writes were made by `t_badd3e1e`.

Promotion update (2026-06-24): semantic review `t_7e5953c2` approved only the bounded HPA Pathology Atlas / TCGA cancer-prognostics `disease_manifests_in_tissue` candidate for canonical promotion. Implementation task `t_5fe137a0` promoted exactly that relation to `gs://jouvencekb/kg/v2/edges/disease_manifests_in_tissue.parquet` and `gs://jouvencekb/kg/v2/evidence/disease_manifests_in_tissue.parquet` (19 edges / 29 evidence rows) with review still required. No broader relation-gap batch and no rejected HPA candidate rows were promoted.

## Scope

Requested relations:

- `gene_coexpressed_gene`
- `disease_manifests_in_tissue`
- `disease_comorbid_disease`
- `phenotype_observed_in_tissue`
- `cell_type_involved_in_disease`

This wave rechecked the current canonical KG at `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`, reused the existing conservative builders where source-native evidence was available, and wrote fresh task-scoped artifacts under `artifacts/staged/t_badd3e1e/` only.

## Canonical and staged counts

Machine inventory: `artifacts/reports/t_badd3e1e_relation_inventory.json`.

| Relation | Current canonical edges/evidence | Fresh staged edges/evidence | Recommendation | Rationale |
| --- | ---: | ---: | --- | --- |
| `gene_coexpressed_gene` | absent / absent | not built | `defer` | Coexpression is correlation/context. No reviewed edge policy selected a source, correlation threshold, context handling, symmetry/direction rule, or leakage guard. Keep as feature/context until policy is approved. |
| `disease_manifests_in_tissue` | 19 / 29 after `t_5fe137a0` canonical promotion (`review-required`) | 19 / 29 | `canonical promoted / review-required` | Source-native bounded candidate exists from HPA Pathology Atlas / TCGA cancer prognostics columns with explicit disease+tissue endpoint mappings and support audit pass. Promotion is narrow cancer-context-specific, not a broad all-disease pathology graph; independent review of `docs/disease_manifests_in_tissue_canonical_promotion_t_5fe137a0.md` is still required. |
| `disease_comorbid_disease` | absent / absent | 0 / 0 audited empty files | `needs_source` | No clean accessible/licensable EHR or co-occurrence source with privacy/provenance policy was available. Do not synthesize comorbidity from shared disease annotations, symptoms, treatments, or ontology proximity. |
| `phenotype_observed_in_tissue` | absent / absent | 0 / 0 audited empty files | `needs_source` | HPO/HPOA directly supports disease→phenotype; audited HPO/HPOA/UBERON did not provide a direct tissue→phenotype observation assertion. Do not infer tissue context from anatomy-like phenotype names or disease→phenotype plus UBERON mappings. |
| `cell_type_involved_in_disease` | absent / absent | no edge file; source-gap JSON | `needs_source` | Cell Ontology provides cell-type hierarchy and explicit tissue-location axioms, but not disease involvement. Need a disease-cell enrichment/annotation source with CL plus EFO/MONDO endpoints, statistics, and source record IDs. |

Related context rebuilt during this wave, because it is the available source-native Cell Ontology bridge around `cell_type_involved_in_disease`:

| Relation | Current canonical edges/evidence | Fresh staged edges/evidence | Recommendation | Rationale |
| --- | ---: | ---: | --- | --- |
| `cell_type_found_in_tissue` | absent / absent | 958 / 958 | `promote_candidate` | Explicit CL relationship axioms to canonical UBERON tissue endpoints (`part_of`, `located_in`) passed endpoint/evidence support checks. This supports tissue context but is not a substitute for disease involvement. |
| `cell_type_subtype_of_cell_type` | absent / absent | 4,526 / 4,526 | `promote_candidate` | Explicit CL `is_a` hierarchy over canonical CL endpoints passed endpoint/evidence support checks. Included only as builder context, not part of the requested five relation gaps. |

## Per-relation source and evidence policy

### `gene_coexpressed_gene`

- Current state: active schema relation, classified as `feature-context-not-edge`; no canonical edge/evidence file.
- Candidate sources: GTEx tissue coexpression, HPA/consensus expression correlation, COXPRESdb/coexpression networks, or single-cell cell-type-specific coexpression networks.
- Endpoint policy: gene→gene, but graph assertion should be symmetric/undirected in practice; evidence must carry context (`tissue`, `cell_type`, dataset/cohort), correlation method, score, multiple-testing/statistical threshold, sample size, and release.
- Evidence schema: source dataset, source record/network ID, context ID/name, correlation metric, correlation value, p/q value if available, sample size, thresholding rule, source release/license, extraction method.
- Expected scale: potentially very dense; even top-k per gene can be millions of edges, while all-pairs expression correlations are not graph-appropriate.
- Leakage/use caveats: coexpression can leak tissue/disease/phenotype labels through expression-derived features and should generally remain feature/context unless a reviewed sparse network policy is adopted.
- Recommendation: `defer`.

### `disease_manifests_in_tissue`

- Current state: canonical promoted / review-required by `t_5fe137a0`; 19 canonical edges and 29 canonical evidence rows under `v2/edges` and `v2/evidence`.
- Source used for fresh staged prototype: Human Protein Atlas `proteinatlas.tsv.zip`, Cancer prognostics columns, with explicit reviewed mappings from cancer-type labels to disease and tissue endpoints.
- Fresh artifact: `artifacts/staged/t_badd3e1e/disease-tissue-phenotype-context/`.
- Counts: 19 staged edges, 29 evidence rows, 2 rejected HPA labels, 25 source-audit rows.
- Endpoint policy: disease→tissue only when the source label has both a single disease endpoint and a single direct tissue/organ endpoint present in canonical nodes.
- Evidence schema: `evidence/{relation}.parquet` rows preserve HPA column name as `source_record_id`, source dataset/release, TCGA/validation cohort predicate, non-empty/prognostic gene-row counts, mapping confidence, and raw mapping payload in `text_span` JSON.
- Expected scale: bounded cancer/tissue context scale for HPA cancer types, not a broad all-disease pathology graph.
- Leakage/use caveats: HPA cancer prognostics columns encode cancer-type/cohort context rather than an independent pathology atlas of every disease manifestation; downstream disease/tissue prediction tasks should treat this as cancer-specific context unless reviewer promotes the semantics.
- Recommendation: promoted only after independent semantic approval in `t_7e5953c2`; keep review-required until `docs/disease_manifests_in_tissue_canonical_promotion_t_5fe137a0.md` is independently accepted.

### `disease_comorbid_disease`

- Current state: active schema relation classified as `feature-context-not-edge`; no canonical edge/evidence file.
- Candidate sources: EHR/cohort comorbidity networks, claims/EHR co-occurrence resources, literature-curated disease-disease comorbidity resources, or other public datasets with explicit co-occurrence statistics and privacy/provenance policy.
- Source audit result: no accepted accessible/licensable source was present in local KG cache or selected by policy; fresh staged root contains audited empty edge/evidence files.
- Endpoint policy: disease→disease graph assertion should be symmetric/undirected or consistently canonicalized; evidence must carry cohort/source, statistic, directionality if any, adjustment variables, sample size, and privacy/provenance constraints.
- Evidence schema: source dataset/cohort, disease pair, co-occurrence/relative-risk/odds-ratio metric, p/q value, sample size, demographic/context fields if non-identifying, release/license, source record ID.
- Expected scale: medium to dense depending on threshold; likely thousands to millions of pairs if naively generated.
- Leakage/use caveats: comorbidity can encode target labels for disease prediction and may introduce population/healthcare-system biases; no rows should be synthesized from shared genes/phenotypes/treatments.
- Recommendation: `needs_source`.

### `phenotype_observed_in_tissue`

- Current state: schema-only/missing in canonical KG; no canonical edge/evidence file. Schema direction is tissue→phenotype.
- Sources audited: HPO `hp.obo`, HPOA `phenotype.hpoa`, UBERON `basic.obo`.
- Source audit result: no direct tissue→phenotype observation assertion found; fresh staged root contains audited empty edge/evidence files.
- Endpoint policy: tissue→phenotype only when a source directly observes/reports phenotype in a tissue or anatomical site. Disease→phenotype plus anatomy-like HP names is not enough.
- Evidence schema: source dataset, tissue endpoint, phenotype endpoint, observation predicate, assay/clinical context, reference/study/paper ID, frequency/severity if available, source record ID, release/license.
- Expected scale: unknown until a direct tissue phenotype source is selected; HPOA disease annotation scale should not be reused for this relation.
- Leakage/use caveats: deriving tissue from phenotype names would create fake anatomical edges and leak disease phenotype annotation into tissue context.
- Recommendation: `needs_source`.

### `cell_type_involved_in_disease`

- Current state: source-audit-only/deferred; no canonical edge/evidence file.
- Sources audited/rebuilt: Cell Ontology `cl.obo` for surrounding cell type hierarchy/tissue context; no disease-cell enrichment source accepted.
- Fresh artifact: `artifacts/staged/t_badd3e1e/cell-type-context-relations/reports/cell_type_involved_in_disease_source_gap.json`.
- Endpoint policy: cell_type→disease only from explicit disease-cell enrichment/annotation sources with canonical CL cell type endpoints and EFO/MONDO disease endpoints. Do not infer from Cell Ontology labels, tissue membership, disease expression context, or cell-type expression edges.
- Evidence schema: disease context/cohort/source, CL endpoint, disease endpoint, enrichment/statistic/effect size, p/q value, sample size, source record ID, study/paper/dataset ID, tissue/cell context if supplied, release/license.
- Expected scale: source-dependent; likely thousands to hundreds of thousands if built from disease single-cell atlases.
- Leakage/use caveats: single-cell disease enrichment can encode labels directly; train/test splits must avoid disease/task leakage and preserve cohort provenance.
- Recommendation: `needs_source`.

## Fresh artifacts

- Disease/tissue/phenotype staged root: `artifacts/staged/t_badd3e1e/disease-tissue-phenotype-context/`
- Cell-type context staged root: `artifacts/staged/t_badd3e1e/cell-type-context-relations/`
- Build reports:
  - `artifacts/reports/t_badd3e1e_disease_tissue_build.json`
  - `artifacts/reports/t_badd3e1e_cell_type_context_build.json`
- Evidence support audits:
  - `artifacts/reports/t_badd3e1e_disease_tissue_evidence_audit.json`
  - `artifacts/reports/t_badd3e1e_cell_type_evidence_audit.json`
- Inventory: `artifacts/reports/t_badd3e1e_relation_inventory.json`

## Commands run

```bash
uv run python -m manage_db.build_staged_disease_tissue_context \
  --node-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes \
  --cache-dir /Users/jkobject/mnt/gcs/jouvencekb-kg/v2/raw \
  --output-dir artifacts/staged/t_badd3e1e/disease-tissue-phenotype-context \
  --fetch-audit-sources

uv run python -m manage_db.build_cell_type_context_relations \
  --download \
  --output-dir artifacts/staged/t_badd3e1e/cell-type-context-relations

uv run python -m manage_db.audit_edge_evidence \
  artifacts/staged/t_badd3e1e/disease-tissue-phenotype-context \
  --relations disease_manifests_in_tissue phenotype_observed_in_tissue disease_comorbid_disease \
  --json

uv run python -m manage_db.audit_edge_evidence \
  artifacts/staged/t_badd3e1e/cell-type-context-relations \
  --relations cell_type_found_in_tissue cell_type_subtype_of_cell_type \
  --json
```

Observed support-audit results:

- disease/tissue root: `ok: true`; `disease_manifests_in_tissue` 19 edges / 29 evidence, 0 unsupported edges, 0 evidence without edge; empty audited files for `phenotype_observed_in_tissue` and `disease_comorbid_disease` also support-pass.
- cell-type context root: `ok: true`; `cell_type_found_in_tissue` 958 edges / 958 evidence, 0 unsupported edges, 0 evidence without edge; `cell_type_subtype_of_cell_type` 4,526 / 4,526 also support-passes.

## Residual risks

- `disease_manifests_in_tissue` remains semantically narrow and cancer-context-specific; reviewer must decide whether HPA cancer prognostics columns are direct manifestation evidence or only context metadata.
- `gene_coexpressed_gene` and `disease_comorbid_disease` can become dense/leaky graph shortcuts if built without sparse source and split policy.
- `phenotype_observed_in_tissue` and `cell_type_involved_in_disease` should not be backfilled from adjacent canonical relations; both need direct assertion sources.
