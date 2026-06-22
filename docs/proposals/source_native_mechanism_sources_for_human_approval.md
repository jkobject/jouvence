# Source-native mechanism sources for human approval

Date: 2026-06-22
Status: revised after P4 comments; proposal only; no ingestion/build cards created.

This memo replaces the earlier P4 approval table with Jérémie's corrections incorporated. It is intentionally a proposal/approval document, not an ingestion plan. Do not create ingestion cards from this file until a later card explicitly asks for them.

## Revised policy summary

The goal is still source-native relation semantics: do not split broad legacy relations by projecting gene-level assertions onto proteins, TFs, transcripts, or miRNAs. Edges should represent what the source actually measured or curated; row-level provenance and uncertainty belong in evidence.

P4 corrections narrow the policy in four important ways:

1. `tf_regulates_gene` stays empty for now. No TF-regulation ingestion cards should be created until a future stricter policy is approved.
2. First TF-binding work should prefer ReMap over ENCODE, targeting `tf_binds_enhancer` from observed ChIP-like binding plus enhancer-overlap logic.
3. DoRothEA is not an approved homogeneous source. It is a mixed access layer/subdataset index; if used at all, preserve subdataset identity such as TRRUST/literature-curation datasets, ReMap, JASPAR/HOCOMOCO motifs, and any other original provider.
4. OmniPath may be a simpler access layer than DoRothEA, but it has the same requirement: keep original provider/resource, license, evidence class, confidence, and row-level provenance. Do not ingest opaque OmniPath/DoRothEA rows as if they were one source.

The policy is not “causal only.” Explicitly typed non-causal exceptions are allowed when useful: predictive enhancer-gene evidence, motif evidence, coexpression/correlation, disease-association-only modules, and context-qualified perturbational RNA evidence. The key rule is honest typing: these should not masquerade as causal/mechanistic edges.

## Revised shortlist

### Approved first batch

These are approved as the first mechanism/source-native candidates to audit or implement in later tasks. Approval here is semantic approval only; each later implementation still needs exact export choice, endpoint anti-join validation, evidence schema, and license/access checks.

| Source | Proposed relation(s) | Why approved | Required evidence/provenance | Caveats |
| --- | --- | --- | --- | --- |
| IntAct exact MITAB/PSI-MI export(s) | `protein_interacts_protein`; rarely `protein_regulates_protein` only when the row is explicitly directional/regulatory; complex rows routed to `protein_complex`/membership policy | Strong experimental molecular interaction evidence when exact exports and interaction types are preserved | Export path/version, interaction type PSI-MI term, detection method, participant IDs/namespaces, interactor types, species, positive/negative status, confidence, expansion method, publication/PMID, features/mutations/binding regions when present | Do not call this just “IntAct direct.” Choose exact files such as MITAB human/species exports and preserve row fields. PSI-MI `association` is broad and must be typed honestly. |
| BioGRID physical subset | `protein_interacts_protein` only when endpoints are protein-native | Useful physical-interaction coverage if separated from other BioGRID classes | Experimental system/type, throughput, publication, score/qualifications/tags, source database, endpoint namespace/protein accession support | BioGRID is not one source class. Genetic interactions are excluded from protein mechanism edges. PTM and complex data require separate schemas below. |
| BioGRID PTM/modification subset | `ptm_site` / structured PTM event nodes and relations, not generic PPI | Site-level modification data is mechanistic but the assertion is a PTM event, not a protein-protein interaction | Modified protein accession, residue/position/modification type when available, enzyme/regulator if present, assay/system, publication, BioGRID identifiers | If canonical protein nodes lack xrefs, fix xref coverage; do not project gene IDs to arbitrary protein isoforms. |
| BioGRID complex subset | `protein_complex` nodes plus `protein_part_of_complex`/membership relations when stable complex IDs/membership exist | Complex membership is source-native and should be represented as complex nodes | Complex ID/name/source, member proteins, stoichiometry/role if available, evidence/publication | Do not flatten complexes into pairwise PPI evidence unless the source actually asserts pairwise interaction. |
| SIGNOR direct/causalTab protein rows | `protein_regulates_protein`; `protein_part_of_complex` or complex-node policy for complex endpoints; `protein_interacts_protein` only for direct binding without sign/effect | Strong directed/signed causal protein regulation and mechanistic effect evidence | Source entity IDs/databases, direction, sign/effect, mechanism, direct flag, residue/sequence, PMID, evidence sentence, score, cell/tissue context | SIGNOR families/complexes must remain family/complex evidence or nodes; do not collapse them into individual proteins. |
| ReMap transcriptional-regulator ChIP/remapped peaks | `tf_binds_enhancer` | Preferred first TF-binding source; observed binding is a better first active relation than inferred TF→gene regulation | Regulator identity, genomic peak coordinates/build, dataset/experiment metadata, biosample/cell/tissue context, peak score/QC, overlap rule to enhancer node | Binding is not regulation. Do not populate `tf_regulates_gene`; do not infer target genes except as separate typed evidence/features. Full-scale overlap must be chunked/indexed to avoid OOM. |

### Explicit non-causal exceptions

These sources/modules may be useful and should not be automatically rejected, but they must be typed as predictive, correlative, association, motif-support, or context-qualified evidence. They should not create active causal/mechanistic edges unless independent source-native mechanism evidence exists.

| Source/module | Recommended treatment | Evidence type / qualifier | Rationale and constraints |
| --- | --- | --- | --- |
| ABC / ENCODE-rE2G enhancer-gene predictions | Context-specific `enhancer_regulates_gene` evidence or enhancer-gene context index; may support hypotheses when combined with compatible TF-binding evidence | `predictive`, `context_specific`, model/release-qualified | Preserve biosample, model score, distance/contact/activity/DNase/Hi-C features, genome build, enhancer interval, target gene, and release. Not global TF regulation. |
| JASPAR / HOCOMOCO motifs | Motif-support evidence/features for enhancer/TF hypotheses; motif-only evidence should not create observed `tf_binds_enhancer` edges | `motif_support`, `predicted_binding_potential`, `non_observed` | Preserve motif model ID/version, TF/family mapping, score/p-value, strand, genome build, scanned interval/enhancer overlap. Useful support, not observed binding or regulation. |
| Coexpression/correlation modules | Evidence/features or separate correlation relations if later approved | `correlative`, `non_causal`, tissue/cell/dataset-qualified | Preserve dataset, tissue/cell/context, correlation/statistic, direction/sign where applicable, sample size, method, multiple-testing fields. Never infer direct mechanism from correlation alone. |
| Disease-association-only modules | Association evidence/relations only if uniquely useful for disease coverage | `association`, `non_causal`, source-qualified | Do not reject solely because no mechanism exists; preserve disease ontology, entity namespace, score/statistic, study/publication/source record. Keep separate from causal mechanism replacements. |
| LncRNA perturbation evidence (LncTarD, LncRNA2Target-like) | Qualified/contextual lncRNA→gene evidence; relation naming should reflect perturbational or regulatory support if later approved | `perturbational`, `contextual`, often `indirect_possible` | Knockdown/overexpression DEGs can be useful causal perturbation evidence but often indirect. Preserve perturbation type, assay, species, cell/tissue/disease, effect direction, target list, PMID/dataset. Prefer low-throughput/mechanistic rows when available. |
| ceRNA prediction modules | Candidate RNA-network evidence only; no direct causal `lncrna_regulates_gene` without stronger support | `prediction`, `shared_mirna_support`, `correlative`, `candidate_ceRNA` | ceRNA predictions usually infer that two RNAs may regulate each other indirectly by competing for shared miRNAs, often combining predicted/observed miRNA binding with expression correlation. Treat as hypothesis/evidence; require perturbation or experimental support before making direct regulatory edges. |

### Deferred

These are not rejected, but should wait until the approved first batch or namespace prerequisites are stable.

| Source | Proposed future treatment | Deferral reason |
| --- | --- | --- |
| ENCODE TF ChIP-seq peaks | Possible second observed-binding source for `tf_binds_enhancer` | ReMap is preferred first. Add ENCODE later after ReMap overlap logic, genome-build harmonization, and enhancer interval rules are validated. |
| ChIP-Atlas TF ChIP peaks | Later broad binding coverage source | Aggregated coverage increases QC/provenance burden; defer until ReMap/ENCODE handling is robust. |
| TRRUST human | Potential original-provider evidence inside a future TF-regulation policy, not active now | Do not populate `tf_regulates_gene` for now. TRRUST may be useful later only if a stricter TF regulation policy is approved. |
| DoRothEA human | Access layer/subdataset index only, not a homogeneous source | Mixed provenance. If used later, split/preserve original subdatasets and evidence types; do not approve DoRothEA A-C as a single active relation source. |
| OmniPath curated mechanism/action subsets | Possible harmonized access layer for protein/mechanism sources after provenance/license filtering | May be simpler than DoRothEA for access, but only if original resource identity, license, direction/sign, mechanism, and references are retained. Prefer primary resources when ambiguity matters. |
| miRTarBase / DIANA-TarBase | Future `mirna_targets_transcript` or `mirna_targets_gene`, depending source endpoint granularity | Needs miRNA node/xref policy and source endpoint audit first. Transcript/UTR/site-level evidence should target transcripts; gene-level measurements should stay gene-level. |
| POSTAR3/POSTAR2 | Future `transcript_interacts_protein` / RBP-RNA binding relations | Wait for transcript/RNA endpoint harmonization, exact export/license review, and coordinate/site evidence schema. |
| ENCORI/starBase CLIP/degradome-backed modules | Possible RNA/RBP/miRNA evidence source; ceRNA/correlation modules remain evidence-only | Needs module-by-module audit. Use CLIP/degradome-backed evidence only; do not ingest pan-cancer correlation/ceRNA as active causal edges. |
| LncTarD 2.0 / LncRNA2Target | Future qualified/contextual lncRNA perturbation/regulation evidence | Accepted in principle as qualified/contextual, but source availability, stable lncRNA mapping, evidence schema, and license need review. |
| MINT | Later overlap/enrichment audit after core protein batch | Likely overlaps IntAct/IMEx; defer until IntAct/SIGNOR/BioGRID core protein batch is validated. |
| InnateDB curated interactions | Later immune/inflammation enrichment audit | Useful niche source but not first wave; defer after core protein batch and source/license sampling. |

### Rejected as active causal/mechanistic edges

Rejected here means rejected as active causal/mechanistic edges, not necessarily useless as evidence/features.

| Source/module | Rejection scope | Reason |
| --- | --- | --- |
| Broad STRING network | Reject as source-native causal/mechanism replacement for `gene_interacts_gene` | Functional association is broad, not directed/signed causal mechanism; can remain association/features if explicitly typed. |
| Full IID compendium | Reject full compendium as causal mechanism source | Mixes experimental, predicted, orthology, context annotations, and source classes; only a future source-decomposed experimental subset could be reconsidered. |
| Motif-only JASPAR/HOCOMOCO scans | Reject as active observed binding/regulation edges | Motifs are predicted binding potential; keep as motif-support evidence/features. |
| ABC/rE2G as global TF regulation | Reject as active/global `tf_regulates_gene` or TF mechanism | Enhancer-gene predictions are context-specific and not TF-specific by themselves. |
| Generic coexpression/correlation as direct regulation | Reject as active causal edges | Correlation alone is not mechanism; keep only as correlative evidence/features. |
| ceRNA prediction as direct lncRNA/RNA regulation | Reject as direct causal edge without perturbation/experimental support | ceRNA is usually an inferred indirect competitive network hypothesis. Keep candidate evidence only unless stronger support exists. |
| Disease-association-only modules as mechanism replacement | Reject as mechanism/protein/TF/RNA causal replacement | Association can be valuable but must stay typed as disease association/non-causal evidence. |
| BioGRID genetic interactions as protein mechanism edges | Reject for protein mechanism relations | Genetic interaction is perturbational/functional, not direct protein mechanism. Model separately only if a future genetic-perturbation schema is approved. |

## RNA and miRNA namespace policy

RNA namespace handling should be explicit before miRNA/lncRNA ingestion:

- Existing transcript nodes are ENST/isoform-level. Do not recreate transcript nodes wholesale and do not choose a “main transcript” for a gene.
- A gene can have many transcript isoforms, and isoforms can encode distinct proteins or non-coding RNA products.
- For miRNA, add miRBase / `hsa-miR-*` IDs as aliases/xrefs to existing ENST transcript nodes only when there is a true 1:1 identity mapping.
- Create miR-primary nodes for mature miRNAs or precursor/hairpin entities when they are biologically distinct from the existing ENST transcript entity.
- Use `mirna_targets_transcript` when the source measures transcript/UTR/site-level targeting. Use `mirna_targets_gene` when the source is gene-level. Do not force gene-level miRNA target rows onto arbitrary transcript endpoints.
- Preserve source-native miRNA name/accession, target namespace, assay/support class, binding location/site if available, disease/context, species, SNP/binding effects, and PMID/source record.

## DoRothEA / OmniPath handling

DoRothEA and OmniPath should be treated as access/provenance layers, not biological sources in themselves.

If a future card uses either one:

1. Enumerate the original provider/subdataset for every row.
2. Preserve provider-specific confidence, evidence class, direction/sign, references, license flags, and source record IDs.
3. Split observed binding, literature-curated TF regulation, motif predictions, and other inferred evidence into distinct evidence types.
4. Do not populate `tf_regulates_gene` unless a later stricter TF-regulation policy explicitly approves the exact source/provider subset.
5. Prefer primary-resource ingestion when the access layer obscures endpoint namespace, evidence type, license, or row provenance.

## What happens to broad `gene_interacts_gene`

No change from the core doctrine:

1. Keep current broad `gene_interacts_gene` readable for legacy compatibility during transition.
2. Do not split its rows into protein/TF/transcript relations by projection. Evidence metadata containing product IDs is not enough.
3. Compare coverage between new source-native relations and legacy `gene_interacts_gene` source slices only after approved source-native replacements exist.
4. Move misnamed/proxy use-cases to `LEGACY_INDEX` with explicit replacement guidance, not silent deletion.
5. Preserve or re-home source-specific evidence: STRING-like functional associations should become features/evidence for functional association, IntAct/SIGNOR-like rows should be superseded by source-native protein relations, and Reactome/pathway co-membership should stay in pathway/complex semantics rather than generic gene interaction.
6. Only deprecate/remove broad active usage after docs, schema matrix, evidence support audits, endpoint anti-joins, and downstream model compatibility are updated.

## Remaining questions

No blocking human question remains for this proposal update. Later implementation cards should ask only source-specific questions that require a product/scientific decision, such as canonical promotion approval, exact disease-association module scope, or whether to activate a future stricter `tf_regulates_gene` policy.
