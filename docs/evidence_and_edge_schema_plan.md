# Evidence and edge-schema reconciliation

Updated: 2026-06-16.

This note reconciles the canonical KG coverage table with Jérémie's schema cleanup notes. It is intentionally non-destructive: relations that already have canonical Parquet files remain readable/valid until a migration explicitly archives or rewrites them.

## Current canonical state

Canonical KG root: `/mnt/gcs/jouvencekb/kg/v2`.

Validated state:

- node files: `15 / 15`
- edge files: `44 / 80`
- nodes: `55,523,691`
- edges: `151,549,604`
- dangling endpoints: `0`
- last full KG validation evidence before the 2026-06-16 additive tranche:
  `.omoc/reports/hermes-full-validate-duckdb-enhancer-20260615T084756Z.txt`
- evidence layer: `10` canonical evidence files, `5,623,895` total support rows,
  audited read-only with zero unsupported/orphan records for
  `cell_line_from_organism`, `disease_associated_gene`,
  `disease_involves_pathway`, `gene_ortholog_gene`, `molecule_targets_protein`,
  `mutation_affects_molecule_response`, `mutation_associated_disease`,
  `mutation_associated_gene`, `mutation_causes_phenotype`, and
  `mutation_causes_protein_change`.
- 2026-06-16 targeted endpoint validation: `cell_type_expresses_protein`
  (`7,205,547` edges) and `mutation_causes_phenotype` (`25,545` edges) both
  have zero dangling endpoints by DuckDB anti-join.

Important corrections relative to old notes:

- Enhancer nodes and three enhancer edge files are canonical, not smoke-only:
  - `enhancer_regulates_gene`: `48,808,144`
  - `enhancer_active_in_tissue`: `22,903,506`
  - `enhancer_active_in_cell_type`: `19,700,144`
- Dataset/cell-line metadata slices are partially canonical:
  - `dataset_contains_gene`: `17,844`
  - `dataset_contains_cell_line`: `1,183`
  - `dataset_contains_tissue`: `27`
  - `cell_line_expresses_gene`: `20,928,056`
  - `cell_line_derived_from_tissue`: `1,092`
  - `cell_line_from_organism`: `1,183`
- Mutation safe slices are partially canonical:
  - `mutation_associated_gene`: `535,093`
  - `mutation_associated_disease`: `4,656,171`
  - `mutation_causes_protein_change`: `177,735`
  - `mutation_causes_phenotype`: `25,545`

## Relations to deprecate or treat as migration candidates

These are **not** deleted automatically. They should be handled by an explicit migration once downstream consumers are checked.

| Relation | Current status | Recommendation | Rationale |
| --- | --- | --- | --- |
| `cell_line_associated_disease` | schema present; no canonical file | Deprecate in favor of `cell_line_models_disease` or evidence metadata on cell-line datasets | Ambiguous association; `models_disease` is the clearer biological relation when curated. |
| `gene_encodes_protein` | canonical file exists (`233,995`) | Keep readable for now, but mark as shortcut/derived | Redundant with `gene_has_transcript` + `transcript_encodes_protein`; useful for legacy TxGNN compatibility. |
| `transcript_alternative_transcript` | schema present; no canonical file | TODEL/deprecate ambiguous transcript-transcript shortcut | Alternative isoforms should be represented by shared `gene_has_transcript` membership plus transcript feature metadata (canonical isoform, MANE/RefSeq/CCDS), not a dense transcript clique. |
| `mutation_associated_cell_type` | schema present; no canonical file | Deprecate unless a concrete eQTL/cell-type source is selected | Likely better as evidence/context metadata for variant effects. |
| `organism_models_disease` | schema present; no canonical file | Deprioritize/deprecate for the human-only KG | Useful for model-organism expansion, but not for current human TxGNN graph. |
| `phenotype_caused_by_mutation` | schema present; no canonical file | Deprecate as inverted wording; prefer `mutation_causes_phenotype` | The causal direction should run from mutation to phenotype. Keep only as compatibility metadata until migrated. |
| `phenotype_associated_molecule` | canonical file exists (`64,784`) | Keep readable as `LEGACY_INDEX`; prefer `molecule_associated_phenotype` for new exports | Existing canonical files are not renamed in place, but the semantic direction is molecule→phenotype (drug/effect), not phenotype→molecule. |
| `phenotype_associated_protein` | canonical file exists (`3,330`) | Keep readable as `LEGACY_INDEX`; prefer `protein_associated_phenotype` for new exports | Current canonical file has legacy gene/protein endpoint caveats; the semantic direction is protein/gene→phenotype, not phenotype→protein. |
| `phenotype_associated_gene` | schema present; no canonical file | Deprecate inverted relation; use `gene_associated_phenotype` | HPO gene associations should be represented gene→phenotype. This remains non-causal and must not be interpreted as phenotype causes gene. |
| `paper_mentions_gene` | canonical file exists (`7,177,163`) | Keep as legacy/literature index; migrate long-term into edge evidence | Co-mention is weak evidence, not a biological assertion. |
| `paper_mentions_disease` | canonical file exists (`6,492,130`) | Keep as legacy/literature index; migrate long-term into edge evidence | Co-mention is weak evidence, not a biological assertion. |

`manage_db.kg_schema` records these decisions as explicit relation lifecycle
metadata (`RelationStatus.DERIVED`, `LEGACY_INDEX`, or `DEPRECATED`) instead of
removing relations. This preserves compatibility for canonical files that already
exist while making cleanup intent machine-readable for tests and downstream docs.

Candidate new regulatory relations from the user list that are **not** in current `kg_schema.py`:

| Candidate relation | Source | Target | Recommendation |
| --- | --- | --- | --- |
| `protein_interacts_with_enhancer` | `protein` | `enhancer` | Add only if backed by a concrete TF/ChIP/ENCODE source; otherwise model as evidence for `enhancer_regulates_gene`. |
| `protein_interacts_with_transcript` | `protein` | `transcript` | Add only if backed by RBP/RNA-binding source; otherwise keep out of core schema. |

These are represented in code as `CANDIDATE_RELATIONS`, not as canonical
`RELATIONS`, so coverage/validation does not expect edge Parquets before a source
selection and ingestion policy exist.

## `mutation_in_gene` vs `mutation_associated_gene`

They both connect `mutation -> gene`, but they are not the same semantic edge.

| Relation | Direct? | Meaning | Source examples | Recommendation |
| --- | --- | --- | --- | --- |
| `mutation_in_gene` | yes | Physical/genomic containment: the variant lies inside the gene locus/transcribed region. | VEP/Ensembl consequence, genomic interval overlap. | Do **not** blindly promote the dense OpenTargets `variant/targetId` smoke output. Promote only from explicit locus/consequence evidence with clear interval semantics. |
| `mutation_associated_gene` | no | Statistical/functional locus-to-gene association: the variant/credible set is linked to a gene, possibly by distance, QTL, chromatin, or L2G model. | OpenTargets L2G/GWAS credible-set join. | Keep as the canonical promoted GWAS/L2G relation; canonical edge and evidence files already exist (`535,093`). |

So: they are shape-compatible but semantically distinct. If a source cannot prove physical containment, it should go to `mutation_associated_gene` or to evidence metadata for an association edge, not to `mutation_in_gene`.

## Evidence doctrine

Evidence should be modeled primarily as **metadata/support for an edge assertion**, not as a separate biological edge whose only purpose is to say that a paper mentions two entities. The graph edge is the biological, pharmacological, or clinical assertion; the evidence layer explains why that assertion exists and where it came from.

In this model, a `paper` is one evidence/support carrier, not the primary biological edge. Evidence can also be an OpenTargets source row, a curated database record, a dataset/cohort/screen, a GWAS or clinical study, a score, an effect-size observation, or an extracted text span. A relation can therefore have multiple support rows of different kinds for the same `(relation, x_id, y_id)` edge.

A canonical edge file, e.g. `edges/molecule_treats_disease.parquet`, should contain the collapsed assertion:

```text
x_id, x_type, y_id, y_type, relation, display_relation, source, credibility, ...collapsed fields
```

An evidence/support layer should retain the many-to-one support records:

```text
evidence/{relation}.parquet
```

Suggested columns:

| Column | Meaning |
| --- | --- |
| `edge_key` | Stable hash of `(relation, x_id, y_id)` or explicit edge UUID. |
| `relation`, `x_id`, `x_type`, `y_id`, `y_type` | The asserted edge being supported. |
| `evidence_type` | `source_row`, `paper`, `database_record`, `dataset`, `study`, `score`, `text_span`, `experiment`, `clinical_trial`, `genetic_association`, `model_prediction`, `manual_curation`, etc. |
| `source` | Source system, e.g. `OpenTargets`, `EuropePMC`, `ChEMBL`, `Reactome`, `ClinVar`, `Cellosaurus`. |
| `source_dataset` | Specific source table or release, e.g. OpenTargets `evidence`, `known_drug`, `mechanismOfAction`, `variantIndex`, `studies`, `credibleSet`, `locus2Gene`, `europepmc`. |
| `source_record_id` | Stable source row/document ID when available. |
| `paper_id` | `PMID:...` / DOI when evidence is a publication. |
| `dataset_id` | Dataset node ID if the evidence comes from a dataset/cohort/screen. |
| `study_id` | GWAS/clinical/experiment accession when available. |
| `evidence_score` | Source-provided score if available; can itself be the support artifact when the source only exposes scored assertions. |
| `effect_size`, `p_value`, `direction`, `confidence_interval` | Quantitative fields when applicable. |
| `predicate` | Source predicate before TxGNN normalization. |
| `text_span`, `section`, `extraction_method` | Literature/NLP provenance if extracted from text. |
| `license`, `release`, `created_at` | Reproducibility/legal metadata. |

This makes `paper` useful without overloading the graph:

- `paper` remains a node type for bibliographic provenance and potential literature graph tasks.
- `paper_mentions_*` can remain as a legacy/literature index for now.
- New biological/pharmacological/disease-association imports should prefer evidence tables with `paper_id` references over adding more `paper_mentions_*` as core KG edges.
- OpenTargets rows should usually become `evidence_type=source_row` records with `source_dataset` and `source_record_id` populated, plus optional paper/study/dataset/score/text-span fields when present.

## OpenTargets evidence plan

OpenTargets is the first evidence source to normalize because it already exposes evidence-like records across multiple domains.

### Phase E1 — Evidence schema and loader ✅ first tranche complete

1. `manage_db/kg_evidence.py` now provides:
   - `write_evidence(root, relation, frame, mode=...)`
   - `read_evidence(root, relation)`
   - `list_evidence(root)`
   - schema validation for required columns.
2. Evidence is stored under `evidence/<relation>.parquet` for the first tranche.
3. `manage_db.audit_edge_evidence` reports unsupported edges and orphan evidence.
4. `manage_db.backfill_edge_evidence` can create conservative evidence records
   from existing canonical edge Parquets when original source-row provenance is
   not yet retained.

### Phase E2 — Backfill evidence for existing canonical OpenTargets-derived edges

Prioritize relations that already exist and have source rows:

1. `mutation_associated_gene` from GWAS/L2G/credible-set inputs. ✅ Canonical conservative L2G evidence backfill complete: `535,093` support rows preserving `studyLocusId`, audited with zero unsupported/orphan records.
2. `mutation_associated_disease` from OpenTargets genetic-association / known-variant disease rows. ✅ Canonical streaming evidence backfill complete: `4,656,171` support rows across `eva`, `gwas_credible_sets`, `uniprot_variants`, and `eva_somatic`, audited with zero unsupported/orphan records.
3. `mutation_causes_protein_change` from variant protein-change inputs. ✅ Canonical conservative OpenTargets variant evidence backfill complete: `177,735` support rows, audited with zero unsupported/orphan records.
4. `disease_associated_gene` and `disease_involves_pathway` from Reactome evidence. ✅ Canonical evidence backfill complete: `2,928` and `2,296` support rows respectively, audited with zero unsupported/orphan records.
5. `mutation_affects_molecule_response` from OpenTargets pharmacogenomics. ✅ Canonical source-aware evidence backfill complete: `18,595` support rows (`5,543` source-record supports + `13,052` PMID paper supports), audited with zero unsupported/orphan records.
6. `molecule_targets_protein` from `mechanismOfAction` / ChEMBL-like sources. ✅ Conservative canonical evidence backfill complete: `41,239` support rows, including `14,559` OpenTargets MoA rows with `drug_mechanism_of_action` action metadata and `26,680` legacy TxGNN supports. This intentionally preserves legacy `y_type=gene` endpoints; do not remap ENSG to ENSP without a separate endpoint migration.
7. `molecule_treats_disease`, `molecule_contraindicates_disease` from `known_drug` / clinical-indication-like sources. **Next tranche.** Treat indication and contraindication as separate collapsed clinical assertions, supported by OpenTargets/ChEMBL known-drug source rows, clinical trial IDs, approval/status fields, disease/drug normalization provenance, and optional publication references. Do not model a paper or clinical trial as the primary edge; use it as support metadata for the treatment/contraindication edge. Audit indications and contraindications independently because polarity errors are high-impact.
8. `enhancer_regulates_gene` and enhancer context edges from enhancer-to-gene/activity sources.

#### Clinical / phenotype source-policy tranche investigated 2026-06-15

This tranche deliberately does **not** backfill canonical evidence from the
current clinical edge files. The safest finding is that the available canonical
clinical assertions are legacy TxGNN collapsed edges without retained source-row
provenance, while the archived OpenTargets clinical source directories expected
by the importer are present but empty. Creating evidence rows from those edges
alone would only restate the edge as ``source=TxGNN`` and would not meet the
source-aware evidence policy.

Observed state from the read-only KG/archive inspection:

| Relation / candidate | Canonical edge state | Source mapping required for evidence | Archive/source state | Safe action |
| --- | ---: | --- | --- | --- |
| `molecule_treats_disease` | `14,135` rows, all `source=TxGNN`, columns only `x_id`, `x_type`, `y_id`, `y_type`, `relation`, `display_relation`, `source`, `credibility` | OpenTargets `clinical_indication`: `drugId` CHEMBL → canonical molecule via OpenTargets `drug_molecule.crossReferences` DrugBank xrefs; `diseaseId` normalized `_`→`:`; `maxClinicalStage` as predicate; `clinicalReportIds[]` as study IDs. | Source recovered from `txgnn-phase4-audit`; staging builder produced `481` source-backed treatment supports for canonical edges. | Keep as staging-only unless partial canonical evidence is accepted; never claim full coverage from this source. |
| `molecule_contraindicates_disease` | `30,675` rows, all `source=TxGNN`, same minimal columns | Requires an explicit contraindication source. OpenTargets `clinical_indication` is positive indication/trial-stage evidence and is invalid for this relation even when pairs overlap. | No usable contraindication-specific source is present in the archived clinical indication importer. Read-only review found `89` overlapping pairs with clinical indications, but those have the wrong polarity. | Blocked pending DrugBank/SIDER/ChEMBL safety-label source with explicit contraindication predicate. |
| `disease_manifests_in_tissue` | no canonical edge file | Needs a disease/phenotype-to-anatomy source with explicit disease/phenotype, tissue/anatomy ID, predicate, and provenance, e.g. curated HPO/UBERON, disease atlas, or GTEx-like disease tissue annotation. | No source archive or canonical file found for this relation. Existing tissue files are expression/context edges, not disease manifestations. | Keep unexported; do not derive disease→tissue edges from expression or phenotype co-occurrence without a source-policy decision. |
| `phenotype_observed_in_tissue` | no canonical edge file | Needs phenotype-to-anatomy observations with HP/UBERON (or mapped tissue) endpoints and source/study/provenance. | No source archive or canonical file found for this relation. Existing phenotype files are HPO disease phenotype and legacy phenotype-associated molecule/protein edges. | Keep unexported; add only after a concrete phenotype-anatomy source is selected. |

Implementation implication: when OpenTargets clinical source rows are restored,
add a source-aware backfill helper rather than using generic edge backfill. It
should join only source rows whose `(molecule, disease, relation)` endpoints are
already canonical, preserve phase/status/source-row keys, write local
`evidence/molecule_treats_disease.parquet`, and run
`audit_edge_evidence --relations molecule_treats_disease` before any promotion.
Contraindications need an independent source and audit path; they should not be
inferred as the inverse or complement of treatment indications.

Current evidence files in canonical GCS/FUSE (read-only Parquet metadata audit,
2026-06-16):

| Relation | Edge rows | Evidence rows | Audit status |
| --- | ---: | ---: | --- |
| `cell_line_from_organism` | 1,183 | 1,183 | zero unsupported/orphan; human cell-line metadata support |
| `disease_associated_gene` | 2,928 | 2,928 | zero unsupported/orphan |
| `disease_involves_pathway` | 2,296 | 2,296 | zero unsupported/orphan |
| `gene_ortholog_gene` | 161,675 | 161,675 | zero unsupported/orphan; OpenTargets target.homologues database-record support |
| `molecule_targets_protein` | 41,239 | 41,239 | zero unsupported/orphan; keeps current legacy `y_type=gene` endpoints |
| `mutation_affects_molecule_response` | 4,866 | 18,595 | zero unsupported/orphan; multiple source/paper supports per collapsed edge |
| `mutation_associated_disease` | 4,656,171 | 4,656,171 | zero unsupported/orphan; OpenTargets disease-facing variant support |
| `mutation_associated_gene` | 535,093 | 535,093 | zero unsupported/orphan |
| `mutation_causes_phenotype` | 25,545 | 26,980 | zero unsupported/orphan; EVA/ClinVar database-record + PMID supports |
| `mutation_causes_protein_change` | 177,735 | 177,735 | zero unsupported/orphan |

Relations with canonical edge files but no source-aware evidence yet include
`molecule_treats_disease`, `molecule_contraindicates_disease`, enhancer
context/regulatory edges, expression and cell-line/DepMap edges,
organism/dataset provenance edges, and legacy paper-mention indexes. Treat
these as the active backlog rather than
claiming the whole canonical graph is fully evidenced.

## Expression/cell-line/tissue/phenotype missing-edge source triage

Read-only tranche selection on 2026-06-15 found two safe non-GCS backfills that
can be generated from existing OpenTargets-derived archived/source inputs once a
parent-side canonical temp root is prepared:

| Relation | Proposed source | Export policy |
| --- | --- | --- |
| `cell_type_expresses_protein` | Existing OpenTargets `expression` (`cell_type_expresses_gene`) projected through registered protein nodes' `ensembl_gene_id` / `gene_encodes_protein` mapping | Safe derived edge. Preserve expression metadata (`tpm`, `expression_level`) and add `gene_id`; source is `OpenTargets/HPA;projected_via_gene_encodes_protein`. |
| `cell_line_expresses_protein` | Existing OpenTargets `target_essentiality` / DepMap expression (`cell_line_expresses_gene`) projected through registered protein nodes' `ensembl_gene_id` / `gene_encodes_protein` mapping | Safe derived edge. Preserve DepMap metadata (`expression`, `gene_effect`, `is_essential`) and add `gene_id`; source is `OpenTargets/DepMap;projected_via_gene_encodes_protein`. |
| `cell_line_responds_to_molecule` | PRISM/GDSC/CTRP-like drug-screen response table | Do not synthesize from pharmacogenomics or target essentiality; wait for an explicit cell-line×molecule response source with effect/viability metric. |
| `disease_manifests_in_tissue` | Disease/tissue pathology source (e.g. curated UBERON/EFO mapping) | Do not infer from disease phenotype or cell-line tissue context. |
| `phenotype_observed_in_tissue` | HPO phenotype anatomical-context annotations or curated phenotype↔UBERON mapping | Do not infer from `disease_has_phenotype` plus `disease_manifests_in_tissue` until both sources and directionality are explicit. |
| `phenotype_associated_cell_type` | Cell Ontology / HPO or disease scRNA enrichment source | Existing direction is legacy phenotype→cell_type; for new exports prefer adding a forward `cell_type_associated_phenotype` relation first, then keep legacy readable if needed. |
| `gene_coexpressed_gene` | Coexpression network with explicit threshold/cohort (GTEx/HPA/CellxGene-derived) | Potentially huge; require thresholding and evidence policy before export. |

No canonical GCS files should be written by child lanes; promote only after the
parent has run endpoint validation and LaminDB parity checks on a bounded temp
root.

### Phase E3 — Recompute collapsed edge credibility from support

For each `(relation, x_id, y_id)`:

- aggregate evidence count by source and evidence type;
- preserve max/source-provided score;
- compute or update `credibility`:
  - `3`: curated/mechanistic/high-confidence multi-source;
  - `2`: multiple independent evidence records/sources;
  - `1`: single weak or NLP-only evidence.

### Phase E4 — Literature integration

1. Treat Europe PMC / papers as evidence records where they support an existing relation.
2. Keep co-mentions separate from assertions:
   - co-mention only => evidence_type `paper_mention`, low confidence;
   - curated claim or extracted relation => evidence_type `paper_relation`, predicate required.
3. Add `paper` metadata/features later: title, abstract, sections/full text if available, embeddings.

### Phase E5 — Audit/reporting

Add a CLI:

```bash
uv run python -m manage_db.audit_edge_evidence /mnt/gcs/jouvencekb/kg/v2
```

Report per relation:

- edge rows with zero evidence;
- evidence records with missing canonical edge;
- source/evidence-type distribution;
- evidence score/credibility coverage;
- top unsupported high-impact relations.

## Immediate next actions / active backlog

1. ✅ `mutation_associated_disease` evidence is canonical: `4,656,171` support
   rows, built in streaming mode under `MemoryMax=5G`, and audited with zero
   unsupported/orphan records.
2. Next build separate clinical evidence tranches for
   `molecule_treats_disease` and `molecule_contraindicates_disease` from
   OpenTargets/ChEMBL known-drug/clinical-indication rows. Keep treatment and
   contraindication polarity separate, preserve source row/trial/status/
   provenance fields, and audit each relation independently.
3. Backfill source-aware supports for enhancer regulatory/context relations,
   then expression and cell-line/DepMap relations. Use local scratch builds,
   endpoint validation, and targeted evidence audits before any canonical GCS
   promotion.
4. Keep `paper_mentions_gene` and `paper_mentions_disease` as readable
   literature indexes, but do not expand paper-mention edges as if they were
   biological assertions; attach papers, text spans, datasets, studies, scores,
   and source rows through `evidence/{relation}.parquet`.
5. Remove or rewrite deprecated/candidate relations only after a compatibility
   migration decision; until then rely on `RelationStatus` and
   `CANDIDATE_RELATIONS` metadata.
