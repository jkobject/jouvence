# Evidence and edge-schema reconciliation

Updated: 2026-06-15.

This note reconciles the canonical KG coverage table with Jérémie's schema cleanup notes. It is intentionally non-destructive: relations that already have canonical Parquet files remain readable/valid until a migration explicitly archives or rewrites them.

## Current canonical state

Canonical KG root: `/mnt/gcs/jouvencekb/kg/v2`.

Validated state:

- node files: `15 / 15`
- edge files: `40 / 77`
- nodes: `55,365,186`
- edges: `144,155,654`
- dangling endpoints: `0`
- evidence: `.omoc/reports/hermes-full-validate-duckdb-enhancer-20260615T084756Z.txt`

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
- Mutation safe slices are partially canonical:
  - `mutation_associated_gene`: `535,093`
  - `mutation_associated_disease`: `4,656,171`
  - `mutation_causes_protein_change`: `177,735`

## Relations to deprecate or treat as migration candidates

These are **not** deleted automatically. They should be handled by an explicit migration once downstream consumers are checked.

| Relation | Current status | Recommendation | Rationale |
| --- | --- | --- | --- |
| `cell_line_associated_disease` | schema present; no canonical file | Deprecate in favor of `cell_line_models_disease` or evidence metadata on cell-line datasets | Ambiguous association; `models_disease` is the clearer biological relation when curated. |
| `gene_encodes_protein` | canonical file exists (`233,995`) | Keep readable for now, but mark as shortcut/derived | Redundant with `gene_has_transcript` + `transcript_encodes_protein`; useful for legacy TxGNN compatibility. |
| `mutation_associated_cell_type` | schema present; no canonical file | Deprecate unless a concrete eQTL/cell-type source is selected | Likely better as evidence/context metadata for variant effects. |
| `organism_models_disease` | schema present; no canonical file | Deprioritize/deprecate for the human-only KG | Useful for model-organism expansion, but not for current human TxGNN graph. |
| `paper_mentions_gene` | canonical file exists (`7,177,163`) | Keep as legacy/literature index; migrate long-term into edge evidence | Co-mention is weak evidence, not a biological assertion. |
| `paper_mentions_disease` | canonical file exists (`6,492,130`) | Keep as legacy/literature index; migrate long-term into edge evidence | Co-mention is weak evidence, not a biological assertion. |

Candidate new regulatory relations from the user list that are **not** in current `kg_schema.py`:

| Candidate relation | Source | Target | Recommendation |
| --- | --- | --- | --- |
| `protein_interacts_with_enhancer` | `protein` | `enhancer` | Add only if backed by a concrete TF/ChIP/ENCODE source; otherwise model as evidence for `enhancer_regulates_gene`. |
| `protein_interacts_with_transcript` | `protein` | `transcript` | Add only if backed by RBP/RNA-binding source; otherwise keep out of core schema. |

## `mutation_in_gene` vs `mutation_associated_gene`

They both connect `mutation -> gene`, but they are not the same semantic edge.

| Relation | Direct? | Meaning | Source examples | Recommendation |
| --- | --- | --- | --- | --- |
| `mutation_in_gene` | yes | Physical/genomic containment: the variant lies inside the gene locus/transcribed region. | VEP/Ensembl consequence, genomic interval overlap. | Do **not** blindly promote the dense OpenTargets `variant/targetId` smoke output. Promote only from explicit locus/consequence evidence with clear interval semantics. |
| `mutation_associated_gene` | no | Statistical/functional locus-to-gene association: the variant/credible set is linked to a gene, possibly by distance, QTL, chromatin, or L2G model. | OpenTargets L2G/GWAS credible-set join. | Keep as the canonical promoted GWAS/L2G relation. |

So: they are shape-compatible but semantically distinct. If a source cannot prove physical containment, it should go to `mutation_associated_gene` or to evidence metadata for an association edge, not to `mutation_in_gene`.

## Evidence doctrine

Evidence should be modeled primarily as **metadata/support for an edge assertion**, not as a separate biological edge whose only purpose is to say that a paper mentions two entities.

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
| `evidence_type` | `paper`, `database_record`, `experiment`, `clinical_trial`, `genetic_association`, `model_prediction`, `manual_curation`, etc. |
| `source` | Source system, e.g. `OpenTargets`, `EuropePMC`, `ChEMBL`, `Reactome`, `ClinVar`, `Cellosaurus`. |
| `source_dataset` | Specific OpenTargets table or release, e.g. `evidence`, `known_drug`, `mechanismOfAction`, `interaction`, `europepmc`. |
| `source_record_id` | Stable source row/document ID when available. |
| `paper_id` | `PMID:...` / DOI when evidence is a publication. |
| `dataset_id` | Dataset node ID if the evidence comes from a dataset/cohort/screen. |
| `study_id` | GWAS/clinical/experiment accession when available. |
| `evidence_score` | Source-provided score if available. |
| `effect_size`, `p_value`, `direction`, `confidence_interval` | Quantitative fields when applicable. |
| `predicate` | Source predicate before TxGNN normalization. |
| `text_span`, `section`, `extraction_method` | Literature/NLP provenance if extracted from text. |
| `license`, `release`, `created_at` | Reproducibility/legal metadata. |

This makes `paper` useful without overloading the graph:

- `paper` remains a node type for bibliographic provenance and potential literature graph tasks.
- `paper_mentions_*` can remain as a legacy/literature index for now.
- New biological/pharmacological/disease-association imports should prefer evidence tables with `paper_id` references over adding more `paper_mentions_*` as core KG edges.

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
2. `mutation_associated_disease` from known-variant/GWAS disease evidence.
3. `mutation_causes_protein_change` from variant protein-change inputs. ✅ Canonical conservative OpenTargets variant evidence backfill complete: `177,735` support rows, audited with zero unsupported/orphan records.
4. `disease_associated_gene` and `disease_involves_pathway` from Reactome evidence. ✅ Canonical evidence backfill complete: `2,928` and `2,296` support rows respectively, audited with zero unsupported/orphan records.
5. `mutation_affects_molecule_response` from OpenTargets pharmacogenomics. ✅ Canonical source-aware evidence backfill complete: `18,595` support rows (`5,543` source-record supports + `13,052` PMID paper supports), audited with zero unsupported/orphan records.
6. `molecule_targets_protein` from `mechanismOfAction` / ChEMBL-like sources. ✅ Conservative canonical evidence backfill complete: `41,239` support rows, including `14,559` OpenTargets MoA rows with `drug_mechanism_of_action` action metadata and `26,680` legacy TxGNN supports. This intentionally preserves legacy `y_type=gene` endpoints; do not remap ENSG to ENSP without a separate endpoint migration.
7. `molecule_treats_disease`, `molecule_contraindicates_disease` from `known_drug` / clinical-indication-like sources.
8. `enhancer_regulates_gene` and enhancer context edges from enhancer-to-gene/activity sources.

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

## Immediate next actions

1. Update `CLAUDE.md` edge table comments with the deprecation/evidence distinctions.
2. Decide whether candidate deprecated relations should be removed from `kg_schema.py` now or only after a compatibility migration.
3. Implement `kg_evidence.py` and backfill OpenTargets evidence for one relation first, preferably `mutation_associated_gene` or `disease_associated_gene`.
