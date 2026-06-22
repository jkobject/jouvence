# Source-native TF regulatory sources proposal

_Date: 2026-06-21_
_Status: proposal only; do not ingest from this note directly._

S1/P4 update: later Jérémie decisions supersede this proposal where it recommends active `tf_regulates_gene`. Do not populate `tf_regulates_gene` for now. For `tf_binds_enhancer`, prefer ReMap as the first observed binding source; ReMap/ChIP-like observed evidence and JASPAR/HOCOMOCO motif evidence may support the same TF/region/context, but evidence type must distinguish observed binding from motif-predicted support. See `docs/source_native_expansion_policy.md`.

## Goal

Select source-native, mechanistic sources for two future regulatory relations:

- `tf_regulates_gene`: a TF/gene product regulates target gene expression.
- `tf_binds_enhancer`: a TF/gene product binds an enhancer or regulatory interval.

This is deliberately not a split from the current canonical `gene_interacts_gene` relation. The current `gene_interacts_gene` endpoints are gene-level and its OpenTargets subdatabases mix STRING, IntAct, Reactome, and SIGNOR interaction evidence. Product IDs and roles retained in evidence metadata are not enough to promote rows into TF or enhancer relations. Future builders for these relations should start from source-native TF-regulatory or TF-binding sources.

## Modeling rules

1. Separate regulation from binding.
   - `tf_regulates_gene` requires a directional regulatory assertion about target gene expression.
   - `tf_binds_enhancer` requires physical/assay evidence that a TF binds a genomic regulatory interval.
2. Motif presence is not binding and not regulation.
   - Motifs can support candidate binding evidence, especially when intersected with accessible chromatin or ChIP peaks, but motif-only rows should not create active causal regulatory edges.
3. ChIP binding is binding, not necessarily target-gene regulation.
   - ChIP-seq/ChIP-exo/CUT&RUN/CUT&Tag peaks can populate `tf_binds_enhancer` when interval/endpoints are validated.
   - A peak-to-nearest-gene expansion is not sufficient for `tf_regulates_gene` unless a source provides a regulatory target assignment and the evidence remains context-specific.
4. Context-specific predictions stay context-specific.
   - ABC/rE2G enhancer-gene predictions can support enhancer→gene regulatory evidence in a biosample context, but they are not global TF→gene truth.
5. Preserve row-level evidence detail.
   - Keep source database, release, source record IDs, PMIDs, assay/method, biosample/cell/tissue context, sign/effect, score/confidence, coordinates, and endpoint namespaces in evidence.

## Recommended relation schemas

### `tf_regulates_gene`

Graph endpoints:

- `x`: TF as gene/gene-product identifier, preferably canonical `ENSG` gene node for KG compatibility.
- `y`: target gene, preferably `ENSG` gene node.

Required evidence fields:

- `source`, `source_dataset`, `source_release`.
- source TF ID/name and target ID/name before mapping.
- regulator role and target role.
- `predicate`: e.g. `activates`, `represses`, `regulates`, `unknown_effect`.
- direction: always TF/regulator → target gene.
- sign/effect where available: activation/upregulation, repression/downregulation, unknown.
- mechanism/evidence class: curated regulation, perturbation-supported regulation, literature-curated regulation, ChIP-supported regulation, motif-only, coexpression-only.
- confidence/score/level.
- PMID(s), source record ID, and curation notes.
- species and orthology policy if non-human rows are considered.

Promotion rule:

- Promote only rows whose source asserts directional TF→target regulation.
- Do not promote generic protein-protein signaling, undirected gene interaction, coexpression, or motif-only evidence into this relation.

### `tf_binds_enhancer`

Graph endpoints:

- `x`: TF as gene/gene-product identifier, preferably canonical `ENSG` gene node with original protein/antibody identifiers preserved in evidence.
- `y`: enhancer/regulatory interval node, using the KG enhancer interval ID policy.

Required evidence fields:

- `source`, `source_dataset`, `source_release`.
- source TF ID/name, antibody/target metadata when present.
- interval coordinates: chromosome, start, end, genome build.
- peak ID/source record ID.
- assay: ChIP-seq, ChIP-exo, CUT&RUN, CUT&Tag, ATAC/DNase-motif intersection, motif prediction.
- biosample/cell type/tissue/condition/treatment.
- score/confidence: peak score, q-value/p-value, IDR/reproducibility flags, motif score if applicable.
- PMID/study/accession: ENCODE experiment, GEO/SRA, ReMap/ChIP-Atlas record, etc.
- mapping from peak to enhancer node: exact overlap, reciprocal overlap threshold, promoter-exclusion policy, enhancer catalog version.

Promotion rule:

- Promote ChIP-like TF binding peaks that overlap accepted enhancer/regulatory interval nodes after genome-build harmonization and QC.
- Motif-only intervals should be evidence-only or candidate features, not active `tf_binds_enhancer` graph edges, unless Jérémie explicitly wants a lower-confidence context/candidate layer.

## Source-by-source classification

| Source family | Mechanism strength | Native endpoints/context | Recommended placement | Classification | Rationale |
| --- | --- | --- | --- | --- | --- |
| DoRothEA | Literature/curated TF regulons with confidence levels; includes supporting evidence from curated resources, TF binding/motif evidence, and expression-based inference depending on row/source. | TF gene symbol/ID, target gene symbol/ID, mode of regulation/sign when available, confidence level A-E, species; limited explicit biosample context. | `tf_regulates_gene` for high-confidence directional rows; preserve DoRothEA confidence and evidence/source flags. Reject or evidence-only for low-confidence or purely inferred rows if source detail shows no mechanistic support. | `recommended` with threshold gate | Strong candidate for TF→gene regulation, but the KG should not flatten all confidence levels into equal causal truth. Proposed default: ingest human A-C as active edges, keep D-E as evidence-only/candidate unless approved. |
| TRRUST | Manually curated transcriptional regulatory relationships from literature; activation/repression/unknown modes and PMID support. | TF gene, target gene, regulatory effect, PMID(s), species. Mostly global, not cell-context specific. | `tf_regulates_gene`; evidence rows must keep effect and PMIDs. | `recommended` | Clean source-native TF→target regulation. Unknown-effect rows can still be directional `regulates` evidence, but should carry `predicate=regulates` / `effect=unknown`, not fake activation/repression. |
| OmniPath transcriptional regulation resources | Integrated directed/signed regulatory interactions, including transcriptional/regulon resources such as DoRothEA/CollecTRI and literature-curated channels depending on selected dataset. | Usually TF/regulator and target gene/protein identifiers, source resource, sign/direction, references, curation/evidence metadata. Context usually global unless resource-specific. | `tf_regulates_gene` only for explicitly transcriptional-regulation datasets/resources; use as an integration layer or source harmonizer, not as a reason to duplicate DoRothEA/TRRUST rows blindly. | `recommended` with dedup/source policy | Good for coverage and harmonized provenance, but must filter to transcriptional regulation resources and preserve the original resource. Generic OmniPath signaling/intercellular interactions should not enter `tf_regulates_gene`. |
| SIGNOR regulatory edges | Literature-curated causal signaling/regulatory relations with direction, sign/effect, mechanism, and PMIDs; not all rows are transcriptional TF→gene regulation. | Protein/gene entities, directed causal relation, effect/sign, mechanism, PMID. Usually no enhancer interval and often not TF target-gene expression. | `tf_regulates_gene` only if row explicitly represents a TF/regulator controlling target gene transcription/expression and endpoints map to TF gene → target gene. Otherwise keep in broader signaling/gene interaction evidence or reject for this relation. | `maybe_contextual` | Mechanistic and causal, but the boundary is scientific: many SIGNOR rows are protein signaling events, not transcription factor regulation. Needs a TF-role and target-gene-expression filter before promotion. |
| ENCODE ChIP-seq / ENCODE TF ChIP tracks | Direct TF-DNA binding assay. Mechanism is binding, not necessarily regulation. | TF/antibody target, genomic peak coordinates, experiment accession, biosample/cell/tissue/condition, genome build, replicate/QC, peak score/significance. | `tf_binds_enhancer` after peak→enhancer overlap and QC; not `tf_regulates_gene` unless combined with context-specific enhancer→gene/regulatory evidence. | `recommended` | Best direct source family for TF binding to regulatory intervals. Must preserve biosample context and avoid nearest-gene causal shortcuts. |
| ChIP-Atlas | Aggregated public ChIP-seq/DNase/ATAC-style peak resources with TF/antigen, cell/tissue/sample context, coordinates, scores, and source experiment accessions. | TF/antigen, peak coordinates, genome build, cell type/tissue, experiment metadata, score/QC depending on file. | `tf_binds_enhancer` for TF ChIP peaks overlapping enhancer nodes; evidence rows preserve experiment and context. | `recommended` | Broad coverage for binding. Treat as binding evidence only; harmonize genome builds and avoid mixing non-TF assays into TF binding edges. |
| ReMap | Curated/remapped regulatory ChIP-seq atlas for transcriptional regulators with peaks and metadata. | Transcriptional regulator/TF, genomic peak coordinates, dataset/biotype/cell context, genome build, score/QC metadata. | `tf_binds_enhancer` for TF/regulator peaks overlapping enhancer nodes. | `recommended` | Strong source-native binding atlas, often more curated/harmonized than raw GEO aggregation. Still not direct TF→gene regulation by itself. |
| JASPAR motifs | Open TF binding profiles / position frequency matrices. Mechanism is sequence motif match/predicted binding potential, not observed binding or regulation. | TF motif matrix ID, TF name/family, species/taxon, motif/PWM; scans yield interval, strand, motif score/p-value, genome build. No biosample context unless intersected externally. | Evidence-only/candidate feature for `tf_binds_enhancer`; do not create active `tf_binds_enhancer` or `tf_regulates_gene` edges from motif-only scans. | `reject_for_causal_mechanism` as standalone; `maybe_contextual` as supporting feature | Motif evidence is useful but not causal/observed. Can annotate enhancers with candidate TF motifs, especially when combined with chromatin accessibility and TF expression, but should not become graph truth alone. |
| HOCOMOCO motifs | Curated human/mouse TF binding models/PWMs. Same mechanism class as JASPAR. | Motif model ID, TF name, species, PWM/thresholds; scans produce predicted TFBS intervals/scores. | Evidence-only/candidate feature; not active relation alone. | `reject_for_causal_mechanism` as standalone; `maybe_contextual` as supporting feature | High-quality motifs, but still prediction. Use for candidate enhancer annotations or as supporting evidence for ChIP/accessibility-backed binding. |
| ABC enhancer-gene predictions | Context-specific enhancer→gene regulatory prediction from activity/contact features; trained/benchmarked using perturbation-like data but not TF-specific binding. | Enhancer interval, target gene, biosample/cell context, ABC score, activity/contact features, distance, possibly study/version. | Keep under `enhancer_regulates_gene` evidence/context index; may support downstream inference connecting a TF-bound enhancer to a target gene in the same context. Not direct `tf_regulates_gene`; not direct `tf_binds_enhancer`. | `maybe_contextual` | Useful bridge: TF binds enhancer + enhancer regulates gene in same context can support a derived/context-specific TF→gene hypothesis. But ABC alone does not name the TF. |
| ENCODE-rE2G | Context-specific enhancer→gene model/prediction with biosample context and feature scores. | Enhancer interval, target gene, biosample ID/name, score, distance-to-TSS, DNase/Hi-C/resource scores, study/QC metadata. | `enhancer_regulates_gene` evidence/context index; evidence-only support for derived TF→gene hypotheses when paired with TF binding in the same context. | `maybe_contextual` | Existing KG policy already treats rE2G as composite context-specific enhancer→gene evidence, not global truth. It should not populate TF relations alone. |
| Coexpression-only networks | Correlation/statistical association in expression profiles. | Gene-gene pairs, correlation/score, tissue/cell/dataset context depending on source. Usually no TF binding, perturbation, or curated causal direction. | Keep in `gene_coexpressed_gene` or feature tables; reject for TF causal regulation unless independently supported. | `reject_for_causal_mechanism` | Correlation is not mechanism. Direction/sign as regulatory effect would be fake. |

## Proposed default source policy

### Active `tf_regulates_gene` candidates

1. TRRUST human rows.
   - Accept activation/repression/unknown-effect rows as directional TF→target regulation.
   - Store `effect=activation|repression|unknown` and PMIDs.
2. DoRothEA human high-confidence rows.
   - Proposed default: A-C active graph edges; D-E candidate/evidence-only until approved.
   - Store confidence and original source support flags.
3. OmniPath transcriptional-regulation subset.
   - Use only explicitly transcriptional/regulon resources.
   - Preserve original resource (`DoRothEA`, `CollecTRI`, `TRRUST`, etc.) to avoid opaque OmniPath-as-source provenance.
4. SIGNOR filtered TF transcriptional rows.
   - Accept only after a row-level gate confirms TF/regulator role and target-gene expression regulation.
   - Do not import generic signaling relations into `tf_regulates_gene`.

### Active `tf_binds_enhancer` candidates

1. ENCODE TF ChIP-seq peaks.
2. ReMap transcriptional regulator ChIP peaks.
3. ChIP-Atlas TF ChIP peaks.

Required gates:

- Human or approved species only.
- Genome build harmonized to the KG enhancer coordinate build.
- TF/antigen maps to a TF gene/gene product.
- Peak overlaps an accepted enhancer/regulatory interval node using a documented overlap rule.
- Evidence retains cell/tissue/biosample, experiment accession, assay, score/QC, and source peak ID.
- Promoter-only intervals should not be silently mixed with enhancer nodes unless the enhancer node catalog includes promoter-like regulatory intervals and the relation wording is broadened.

### Evidence-only / context-index sources

1. JASPAR and HOCOMOCO motif scans.
   - Store as enhancer features or candidate evidence, not active causal edges.
2. ABC and rE2G.
   - Keep in `enhancer_regulates_gene` evidence/context index.
   - Use only to contextualize a derived chain: TF binds enhancer in biosample B; enhancer regulates gene G in compatible biosample B; optional target gene expression/perturbation supports direction/effect.
3. Coexpression-only rows.
   - Use `gene_coexpressed_gene` or feature tables, never causal TF regulation alone.

## Derived context-specific TF→gene hypotheses

A future derived relation or feature could connect TF→gene when multiple source-native facts align:

1. TF binds enhancer E in biosample/context C from ENCODE/ReMap/ChIP-Atlas.
2. Enhancer E regulates gene G in context C from ABC/rE2G.
3. Optional: TF and G are expressed in C, and perturbation/curated source supports effect direction.

Recommendation: do not write these as plain global `tf_regulates_gene` edges initially. Put them in a context-index/evidence table or a clearly named derived relation only after Jérémie approves the semantics, because the assertion is conditional on biosample/context and model features.

## Evidence placement matrix

| Evidence class | `tf_regulates_gene` | `tf_binds_enhancer` | Context-index/evidence-only | Reject |
| --- | --- | --- | --- | --- |
| Literature-curated TF→target regulation with PMID and sign | yes | no | no | no |
| Perturbation-supported TF→target expression change | yes, if TF perturbation and target expression effect are explicit | no | maybe if context-specific only | no |
| ChIP TF peak overlapping enhancer | no | yes | with context metadata | no |
| ChIP peak assigned to nearest gene | no by default | yes for binding interval | yes as candidate target assignment | yes for causal TF→gene if nearest-gene only |
| Motif scan in enhancer | no | no as active edge | yes as candidate feature | yes as standalone causal evidence |
| ABC/rE2G enhancer→gene | no | no | yes under `enhancer_regulates_gene` | no |
| Coexpression TF-target correlation | no | no | yes as expression feature/coexpression relation | yes as causal TF regulation |
| Generic SIGNOR protein signaling edge | no unless explicitly transcriptional TF→gene | no | maybe broader signaling evidence | yes for these two relations |

## Open approval questions for Jérémie

1. Do we accept DoRothEA confidence A-C as active `tf_regulates_gene` edges, with D-E held as candidate/evidence-only? My recommendation is yes.
2. For TRRUST unknown-effect rows, should they be active `tf_regulates_gene` edges with `effect=unknown`, or evidence-only until sign is known? My recommendation is active directional regulation with unknown effect preserved.
3. Should OmniPath be used as a harmonized access layer for DoRothEA/TRRUST/CollecTRI-like resources, or should each original resource be ingested independently to avoid duplicate provenance? My recommendation is use OmniPath only if original resource provenance is retained and deduplicated.
4. Should filtered SIGNOR transcriptional rows be included in P2, or deferred until a separate SIGNOR row audit defines the TF-role gate? My recommendation is defer or include only after a small audit, because generic SIGNOR signaling can easily contaminate TF regulation.
5. For `tf_binds_enhancer`, should active edges require ChIP-like observed binding only, or can high-confidence motif+accessibility rows create lower-confidence active edges? My recommendation is ChIP-like observed binding only; motif+accessibility stays evidence-only/candidate.
6. Should derived TF→enhancer→gene chains be represented as context-specific evidence/features only, or should the KG eventually get a separate context-qualified derived relation? My recommendation is evidence/features first, no global derived relation.

## Proposed next steps after approval

No ingestion cards are created by this proposal task. If approved later, implementation should be split into separate cards:

1. Audit and stage `tf_regulates_gene` from TRRUST/DoRothEA/OmniPath transcriptional subsets.
2. Audit SIGNOR rows for explicit TF transcriptional regulation gates.
3. Audit and stage `tf_binds_enhancer` from one binding source first, preferably ENCODE TF ChIP or ReMap, with genome-build and enhancer-overlap validation.
4. Design motif/enhancer feature tables for JASPAR/HOCOMOCO without promoting motif-only rows to active edges.
5. Design a context-index for TF-bound enhancer + enhancer-regulates-gene chains, using ABC/rE2G context compatibility checks.
