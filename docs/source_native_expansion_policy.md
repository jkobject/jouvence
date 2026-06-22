# Source-native expansion policy: complexes, PTMs, TF binding, miRNA, transcripts

Date: 2026-06-21
Status: policy only; do not ingest data from this document.

This document records Jérémie-approved modeling decisions from the P4 human gate and the S1 policy task. It narrows the earlier proposal docs before any new source ingestion/audit cards build staged Parquets.

## Scope and non-goals

- This is a documentation/policy update only.
- Do not change canonical KG files from this task.
- Do not create ingestion output from proposal text alone; every future builder still needs raw source inspection, endpoint anti-joins, evidence support checks, and review.
- Current canonical `gene_interacts_gene` remains gene-level and must not be projected into protein, TF, transcript, miRNA, complex, or PTM relations.

## Global source-native rules

1. Model what the source measures or asserts, not what can be reached by ID projection.
2. Keep relation names broad and stable; keep source-specific nuance in evidence fields.
3. Preserve original endpoint IDs/namespaces, source record IDs, source dataset/subdataset, release, method/assay, score/confidence, PMID/study IDs, context, direction/sign/effect, and raw-source provenance in evidence.
4. Non-causal exceptions are allowed when useful, but must be explicitly typed as predictive, correlative, association, candidate, or context-specific in evidence/metadata. Do not silently promote them to causal/mechanistic truth.

## Protein complexes

Decision: `protein_complex` should be a node type.

Policy:

- Source-native complex records should create `protein_complex` nodes when the source names a complex identity, stable source ID, or explicit complex record.
- Membership should be represented with relations such as `protein_part_of_complex` / `complex_has_component` once final naming is approved; evidence must preserve stoichiometry, expansion method, source complex ID, organism, method, PMIDs, and release when available.
- Do not infer complex nodes or memberships from generic pairwise PPI rows unless the source explicitly says the row comes from a complex expansion or complex-membership record.
- Family/complex-like endpoints from SIGNOR/OmniPath/BioGRID should not be forced into single protein nodes. Keep them as complex/family nodes once supported, or evidence-only until the node family exists.

## PTMs and PTM sites/events

Decision: PTMs should not be flattened into generic protein interactions.

Policy:

- Site-level PTM evidence should use structured node/event modeling, with a likely `ptm_site` node or `protein_ptm_event`/structured event table once the schema is finalized.
- A site-level PTM assertion should preserve modified protein/isoform, residue, position, modification type, enzyme/regulator if source-native, substrate role, direction/effect, method, PMID, source record, and context.
- Enzyme→substrate PTM rows may support `protein_regulates_protein` only when the source explicitly identifies direction/roles/mechanism; the PTM site/event remains structured evidence or a node/event, not just an edge label.
- Vague PTM mentions without site, enzyme/substrate roles, or endpoint clarity stay as evidence/edge-level metadata and should not create PTM site nodes.

## TF binding and TF regulation

### `tf_binds_enhancer`

Decision: `tf_binds_enhancer` can combine observed ReMap/ChIP-like binding plus motif evidence. Evidence type distinguishes observed from motif-predicted support.

Policy:

- ReMap is the preferred first source for observed TF/regulator binding to enhancer/regulatory intervals.
- Observed ChIP-like support includes ReMap/ChIP-seq/ChIP-exo/CUT&RUN/CUT&Tag-style evidence after genome-build harmonization and overlap to accepted enhancer/regulatory interval nodes.
- Motif evidence from JASPAR/HOCOMOCO can strengthen evidence for the same TF/region/context and should be stored as motif/candidate support with motif ID, score, threshold, strand, genome build, and scan method.
- Motif-only rows are predicted binding potential, not observed binding. If represented, mark `evidence_type=motif_predicted` or equivalent and do not call them observed binding.
- Evidence should preserve TF/source antigen, antibody/target metadata if present, source peak ID, interval coordinates, genome build, enhancer-overlap rule, biosample/cell/tissue/condition, score/QC fields, source dataset/subdataset, release, and study/PMID/accession.

### `tf_regulates_gene`

Decision: do not populate `tf_regulates_gene` for now.

Policy:

- Do not create `tf_regulates_gene` ingestion/build cards until Jérémie approves a stricter future source policy.
- Do not populate `tf_regulates_gene` from DoRothEA as a homogeneous source. DoRothEA is a mixed access layer/subdataset index; if used later, preserve subdataset identity and row provenance.
- OmniPath may be used later as a simpler access layer only if original resource/subdataset identity, row-level provenance, and license/source filtering are preserved.
- ABC/rE2G enhancer→gene predictions, motifs, coexpression, and nearest-gene peak assignments do not create global TF→gene regulation edges.

## Transcripts and isoforms

Decision: existing transcript nodes remain; do not create or choose a “main transcript.”

Policy:

- Existing `transcript` nodes include ENST transcript IDs and should be reused.
- A gene can have many transcript isoforms. Do not collapse to a main transcript unless a source explicitly names one canonical transcript for its own measurement, and even then preserve that source-specific claim as evidence.
- Isoforms may map to distinct proteins through `transcript_encodes_protein`; preserve isoform-level mappings where available.
- Use gene-level relations when the source measurement is gene-level. Use transcript-level relations only when the source names transcript/UTR/isoform endpoints or a validated source-native transcript mapping.

## miRNA identity and target policy

Decision: miRBase/hsa-miR IDs should be aliases/xrefs to existing ENST transcript nodes when true 1:1; create miR-primary nodes only when the mature/precursor miRNA entity is distinct from an existing transcript entity.

Policy:

- When an existing ENST transcript node has a true 1:1 mapping to a miRBase/hsa-miR identity, add miRBase accessions/names (`MI...`, `MIMAT...`, `hsa-miR-*`) as aliases/xrefs or a mapping table for that transcript node.
- Do not re-create transcript nodes blindly. Existing ENST transcript nodes remain the transcript layer.
- Create miR-primary nodes only when the source entity is not the same biological entity as an existing ENST transcript: for example a distinct mature miRNA or precursor miRNA entity. Candidate labels are `mirna_precursor` and `mature_mirna`, pending schema finalization.
- Preserve maturity/processing relationships where source/annotation supports them, for example precursor → mature miRNA and transcript/host-gene relationships.
- For miRNA target sources, gene-level source measurements stay gene-level and should use `mirna_targets_gene` / `mirna_regulates_gene` naming once approved. Do not force gene-level target evidence into transcript endpoints.
- Use `mirna_targets_transcript` when the source endpoint is transcript/UTR/site-level and the transcript endpoint is source-native or validated.
- Protein readouts in miRNA target assays remain evidence unless the source natively identifies a target protein endpoint and a protein-level relation is explicitly approved.

## Non-causal exception classes

Some useful KG content is not causal/mechanistic. Keep it only when typed honestly:

- ABC/rE2G: context-specific enhancer→gene prediction/evidence; preserve biosample, model score, distance, activity/contact/DNase/Hi-C features, release, and QC. Not global TF regulation.
- Motifs: predicted binding potential/candidate support; preserve motif model, score, threshold, strand, scan method, genome build, and enhancer overlap.
- Coexpression/correlation: correlative expression evidence/features; preserve context, dataset, correlation/effect size, score, and method. Not regulatory direction by itself.
- Disease-association-only modules: association evidence can be useful when unique, but must be typed as association/non-causal with disease/context/provenance fields. Do not use disease association as a proxy for molecular mechanism.
- ceRNA predictions: competing-endogenous-RNA hypotheses where RNAs may regulate each other by competing for shared miRNAs. Treat as context-specific/predicted RNA-RNA regulatory evidence unless explicit experimental mechanism is present; do not collapse ceRNA correlation into transcript→gene or miRNA target edges.

## Future builder gates

Every future source-native builder should:

1. Name exact source export(s), release(s), and license/terms.
2. Inspect raw schema and sample rows before mapping.
3. Keep source-native endpoint namespaces; avoid gene/RNA/protein projection unless explicitly approved for that source and relation.
4. Write edge and evidence together in scratch/staging.
5. Validate endpoint anti-joins against active node files.
6. Run edge/evidence support audits.
7. Keep non-causal evidence typed as predictive/correlative/association/candidate/context-specific.
8. Update docs and coverage reports with real staged/canonical counts only after validation.
