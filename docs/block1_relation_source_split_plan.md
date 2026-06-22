# Block 1 — relation source split plan

_Date: 2026-06-20_

Goal: split broad source-native compendia only when the source assertion and endpoint namespace justify a more specific relation. Do not project gene-level rows to protein/transcript endpoints. Keep broad edges where the biological assertion is broad, and preserve source/subdatabase detail in `evidence/{relation}.parquet`.

S1 update (2026-06-21): source-native expansion policy for complexes, PTMs, TF binding, miRNA IDs, and transcript isoforms lives in `docs/source_native_expansion_policy.md` and overrides earlier proposal-only wording before any new ingestion.

## Current local limitation

This repo session does not have `/mnt/gcs/jouvencekb/kg/v2` or `/mnt/gcs/jouvencekb/kg/scratch` mounted, so this pass updates schema/docs/tests and defines the promotion plan. The actual DuckDB scans and Parquet promotion must run in an environment with the KG mount.

## New schema relations added in this pass

| Relation | Source | Target | When to populate | Evidence fields that must be retained |
| --- | --- | --- | --- | --- |
| `tf_regulates_gene` | `gene` | `gene` | Source explicitly states TF/regulator controls target gene expression. | source database, regulator/target roles, sign/effect, direction, assay/method, score, PMID/source record, release |
| `tf_binds_enhancer` | `gene` | `enhancer` | Source explicitly states TF/gene-product binding to enhancer/regulatory interval. | assay/cell context, interval coordinates, peak/QC fields, source database, score, PMID/source record, release |
| `transcript_interacts_protein` | `transcript` | `protein` | Source names RNA/transcript and protein/isoform endpoints. | assay/method, molecule roles, source database, score, PMID/source record, release |
| `transcript_interacts_gene` | `transcript` | `gene` | Source names transcript/RNA and gene endpoints for regulatory/interaction assertions. | mechanism, direction, sign/effect, source database, score, PMID/source record, release |

S1 policy corrections:

- Do not populate `tf_regulates_gene` for now, even though the relation remains schema-valid.
- Prefer ReMap as the first observed TF-binding source for `tf_binds_enhancer`; motif support from JASPAR/HOCOMOCO can strengthen evidence but motif-only support remains predicted/candidate.
- Model source-native complexes as `protein_complex` nodes plus membership relations once schema names are finalized.
- Model site-level PTMs as `ptm_site` / structured PTM events where possible; vague PTM support remains evidence metadata.
- Reuse existing ENST `transcript` nodes; do not create a main transcript.
- Add miRBase/hsa-miR aliases/xrefs to existing ENST transcript nodes only for true 1:1 mappings; create miR-primary mature/precursor nodes only for distinct entities.
- Use gene-level miRNA target relations for gene-level source measurements; use `mirna_targets_transcript` only for transcript/UTR/site-level source endpoints.
- Keep ABC/rE2G, motifs, coexpression/correlation, and disease-association-only modules only as explicitly typed predictive/correlative/association/context-specific evidence when useful.

## 1. `gene_interacts_gene`

Existing known source from prior build: OpenTargets 26.03 `interaction` evidence with IntAct, Reactome, SIGNOR, STRING support.

Action when KG is mounted:

1. Summarize source/subdatabase composition:
   ```sql
   select source_dataset, predicate, evidence_type, direction, count(*)
   from read_parquet('/mnt/gcs/jouvencekb/kg/v2/evidence/gene_interacts_gene.parquet')
   group by 1,2,3,4 order by 5 desc;
   ```
2. Keep broad gene/gene-product interaction rows in `gene_interacts_gene` when endpoints are Ensembl/NCBI gene-like or when source does not provide protein/transcript/enhancer endpoints.
3. Split only source-native rows:
   - `protein_interacts_protein`: both endpoints are protein/isoform-native (`ENSP`, UniProt mapped unambiguously to an ENSP, or equivalent protein product ID), and the source assertion is a protein interaction.
   - `tf_regulates_gene`: source explicitly encodes TF/regulator → target-gene regulation, not just undirected co-mention or generic interaction.
   - `tf_binds_enhancer`: source explicitly encodes TF binding to enhancer/regulatory interval.
   - `transcript_interacts_protein`: source names RNA/transcript and protein endpoints.
   - `transcript_interacts_gene`: source names transcript/RNA and gene endpoints.
4. Do not canonical-sort A/B if source has direction/sign/effect. Preserve roles in evidence.

### B1 audit outcome — 2026-06-21

`docs/block1_gene_interacts_gene_audit.md` rechecked the current canonical `gene_interacts_gene` edge/evidence files and the OpenTargets 26.03 raw `interaction` source. Outcome: no active split Parquets should be built from the current canonical relation.

Reasons:

- Current canonical OpenTargets endpoints are `ENSG`↔`ENSG`; legacy TxGNN endpoints are `NCBI`↔`NCBI`.
- Product identifiers (`ENSP`, UniProt-like IDs, occasional `URS...`) are retained as `text_span`/`source_record_id` metadata, not typed graph endpoints.
- SIGNOR regulator roles are broader than TF expression regulation, so they do not justify `tf_regulates_gene` without a TF-specific assertion/classification gate.
- No enhancer/regulatory interval endpoints exist in this source.
- Transcript/RNA-like raw rows require a separate raw-source audit because they are absent from canonical evidence.

Implementation policy for Block 1: do not create `protein_interacts_protein`, `tf_regulates_gene`, `tf_binds_enhancer`, `transcript_interacts_protein`, or `transcript_interacts_gene` from current canonical `gene_interacts_gene`. Future builders must start from source-native endpoint rows and write to scratch/staging first, with endpoint anti-joins and evidence support validation before promotion.

C1 follow-up status: there is no approved `protein_interacts_protein` artifact for this Block 1 pass. Review follow-up `t_9871827b` found stale earlier `protein_interacts_protein` edge/evidence files in `.omoc/block1-build/`; they were first rejected for auditability and then deleted per Jérémie's instruction, leaving only `.omoc/rejected/block1-stale-protein_interacts_protein-20260621/README.md` as a tombstone record. The active Block 1 build directory must not be blindly promoted as if a PPI split had passed review.

## 2. `pathway_contains_gene`

Known current broad relation: Reactome / GO gene-level membership.

Action when KG is mounted:

1. Summarize source/subdatabase composition:
   ```sql
   select source_dataset, predicate, evidence_type, count(*)
   from read_parquet('/mnt/gcs/jouvencekb/kg/v2/evidence/pathway_contains_gene.parquet')
   group by 1,2,3 order by 4 desc;
   ```
2. Keep gene-level pathway membership in `pathway_contains_gene`.
3. Populate `pathway_contains_protein` only when the source provides protein/isoform-native membership or complex/pathway membership at protein product level.
4. Evidence must preserve pathway database/version, membership type, evidence code, source record IDs, release, and any PMIDs.

## 3. `molecule_targets_gene`

Known current broad relation: drug/compound target rows whose native endpoint is gene/OpenTargets target ID.

Action when KG is mounted:

1. Summarize source/subdatabase composition:
   ```sql
   select source_dataset, predicate, evidence_type, direction, count(*)
   from read_parquet('/mnt/gcs/jouvencekb/kg/v2/evidence/molecule_targets_gene.parquet')
   group by 1,2,3,4 order by 5 desc;
   ```
2. Keep gene/OpenTargets-target endpoint assertions in `molecule_targets_gene`.
3. Populate `molecule_targets_protein` only when the source directly identifies a protein/isoform endpoint or an unambiguous protein product target.
4. Evidence must preserve MoA/action type, target class, mechanism, source database, confidence/score, source record ID, and release.

## Promotion gates

For each produced split relation:

1. Build in scratch/staging first.
2. Validate node anti-joins for x/y endpoints.
3. Write `evidence/{relation}.parquet` with source/subdatabase detail.
4. Run `manage_db.audit_edge_evidence`.
5. Update `docs/kg_schema_overview.md`, `TODO.md`, and coverage report with real row counts.
6. Run targeted tests.

## First local GCS-cache inspection — 2026-06-20

Mount was not available on this macOS host (`gcsfuse` is not installed; Homebrew cannot install it here because its `libfuse` dependency is Linux-only). Used `gcloud storage cp` into `.omoc/gcs-cache/kg-v2/` instead.

Observed files:

- `edges/gene_interacts_gene.parquet`: `7,424,037` rows; sources: OpenTargets `6,781,887`, TxGNN `642,150`.
- `evidence/gene_interacts_gene.parquet`: `14,336,594` rows; `source_dataset=interaction`; predicates/subdatabases: STRING `12,988,596`, IntAct `1,257,806`, Reactome `52,480`, SIGNOR `37,712`; directions: `undirected` `14,246,402`, `source_ordered` `90,192`. Evidence preserves `targetA/targetB`, `intA/intB` and source details in JSON `text_span`.
- `edges/pathway_contains_gene.parquet`: `630,932` rows; sources: TxGNN `340,383`, OpenTargets/GO `290,549`; columns include `go_evidence` and `go_aspect`.
- `evidence/pathway_contains_gene.parquet`: staged locally with `630,932` rows and complete support for `630,932/630,932` edges. Source datasets: TxGNN `txgnn_legacy_go` `297,737`, OpenTargets `go` `290,549`, TxGNN `txgnn_legacy_reactome` `42,646`. Endpoint anti-joins against pathway/gene nodes are clean; no protein-like/non-gene endpoints were observed, so no `pathway_contains_protein` split is promoted.
- `edges/molecule_targets_gene.parquet`: `41,239` rows; sources: TxGNN `26,680`, OpenTargets `14,559`; OpenTargets rows include `action_type`.
- `evidence/molecule_targets_gene.parquet`: `41,239` rows; OpenTargets source dataset is `drug_mechanism_of_action`; TxGNN rows have blank source_dataset and old predicate/direction value `molecule_targets_protein`, so this evidence needs cleanup/backfill of source/subdatabase detail before any protein-target split.

Immediate implications:

1. `gene_interacts_gene` already has enough subdatabase detail to start designing splits, but OpenTargets interaction remains mostly gene-target level; do not populate `protein_interacts_protein` from `intA/intB` unless endpoint mapping and assertion policy are explicitly validated.
2. `pathway_contains_gene` needs evidence materialization first.
3. `molecule_targets_gene` needs TxGNN evidence provenance cleanup first; OpenTargets MoA rows are gene-target assertions unless a protein-native endpoint is recovered.

