# Proposal: source-native protein interaction sources for replacing broad `gene_interacts_gene`

Date: 2026-06-21

Status: proposal only; no ingestion/build performed.

S1/P4 update: later Jérémie decisions supersede the complex/PTM handling in this proposal. `protein_complex` should be a node type for source-native complex identities; membership relations should be built only from explicit complex membership/source-native complex records. Site-level PTMs should use `ptm_site` / structured PTM event modeling when source fields provide residue/site and roles; vague PTM support remains evidence metadata. Do not flatten complexes or PTMs into generic `protein_interacts_protein`. See `docs/source_native_expansion_policy.md`.

## Executive decision

Do not use the current canonical `gene_interacts_gene` relation as the source for protein interaction splits. Its active graph endpoints are gene-level (`ENSG`↔`ENSG` for OpenTargets, `NCBI`↔`NCBI` for legacy TxGNN), even though product IDs are present in evidence metadata. A replacement for physical/mechanistic interaction use-cases should start from source-native protein/isoform or complex endpoints and then materialize new evidence-backed protein relations.

Recommended sources to ask Jérémie to approve first:

1. **IntAct direct MITAB27/PSI-MI export** — primary curated experimental molecular interaction source; already partly represented through OpenTargets but flattened to gene endpoints.
2. **BioGRID physical + PTM + complex subsets** — broad, downloadable, permissive license; must explicitly exclude genetic interactions from causal molecular-mechanism relations.
3. **SIGNOR direct TSV/causalTab** — best source here for directed, signed, mechanism/effect protein regulation and complex/family biology.
4. **OmniPath mechanism/action subsets** — useful integration layer for directed signaling/regulatory edges, but only when rows expose source, directedness/sign, and underlying license/source provenance.

Second-pass / conditional:

5. **MINT** — curated experimental PPI, but likely overlaps heavily with IntAct/IMEx and is accessed through PSICQUIC/MITAB. Use as extra evidence if source IDs are preserved.
6. **InnateDB curated interactions** — good immune-focused experimental mechanism coverage; use when immune/inflammation coverage matters and license/source provenance is acceptable.

Rejected for causal mechanism replacement:

7. **STRING broad functional network** — keep only as `functional_association` evidence/features. The `protein.physical.links.*` files may be a low-priority `maybe`, but still scored/integrated and not clean causal mechanism evidence.
8. **IID full compendium** — useful contextual PPI features, not a clean causal mechanism source unless restricted to experimental rows and decomposed by original source.

## Relation policy

Keep relation names broad:

- `protein_interacts_protein`: undirected or source-ordered physical molecular interactions between protein/isoform endpoints when the source assertion is physical binding/association/complex-level contact and no signed regulatory effect is encoded.
- `protein_regulates_protein`: directed regulation where the source explicitly provides controller/target roles plus effect/sign/mechanism (`up-regulates`, `down-regulates`, phosphorylation, inhibition, activation, etc.).
- `protein_part_of_complex`: protein or isoform membership in a named source-native complex. Do not infer complex membership from a generic pairwise PPI unless the source explicitly states a complex/expansion method.
- Evidence-only/features: predicted, functional-association, text-mining, coexpression, orthology-projected, tissue-contextualized, or integrated confidence rows that do not themselves assert a direct molecular mechanism.

Do not create relation names per database or predicate. Preserve source-specific detail in `evidence/{relation}.parquet`: `source`, `source_dataset`, source record ID, endpoint namespaces, original endpoint IDs, predicate/interaction type, direction, roles, effect/sign, mechanism/action, confidence, method, PMID/publication, cell/tissue context, release, license, and raw JSON metadata.

## Source assessments

### IntAct

Classification: **recommended**

Mechanism fit:

- True curated molecular interaction database using PSI-MI/MITAB. The public MITAB27 export states one binary interaction per row and, since 2009, one row per interaction evidence.
- Suitable for `protein_interacts_protein` when both interactors are proteins/isoforms and the interaction type indicates physical association/binding or related PSI-MI molecular interaction.
- Some rows may involve genes, RNAs, chemicals, complexes, or negative interactions; filter by interactor type and organism rather than assuming every row is protein-protein.

Endpoint namespaces:

- MITAB header uses `ID(s) interactor A/B`, with observed rows containing `uniprotkb:*` primary IDs and alternate IDs including `ensembl:ENSP...` and IntAct accessions.
- Keep original IDs and map to the canonical protein node namespace only after explicit endpoint policy. Do not collapse to ENSG unless the target relation is gene-level.

Directionality/sign/effect:

- Mostly binary interaction evidence; generally not signed causal regulation.
- MITAB fields preserve biological roles, experimental roles, interaction type, negative flag, features, stoichiometry, and participant identification method. If a row encodes directed regulatory mechanism, it may feed `protein_regulates_protein`; otherwise default to `protein_interacts_protein`.

Confidence/method/publications:

- MITAB columns include interaction detection method(s), publication first author(s), publication identifiers, interaction type(s), source database(s), interaction identifiers, confidence values, expansion method, host organism, parameters, feature(s), stoichiometry, creation/update dates, and negative flag.

Access/license constraints:

- Public FTP/HTTPS downloads under EMBL-EBI terms. EMBL-EBI states it places no additional restrictions on data use/redistribution beyond original data owners unless a resource-specific license says otherwise; attribution is expected.
- Preserve IntAct accession/source identifiers and citation metadata.

Proposed relation handling:

- `protein_interacts_protein` for experimentally supported protein/isoform binary interactions.
- `protein_part_of_complex` only when complex membership/stoichiometry/expansion method justifies it.
- `protein_regulates_protein` only for explicitly causal/directed rows; otherwise evidence stays under interaction.

### MINT

Classification: **maybe**

Mechanism fit:

- MINT describes itself as a public/open database focused on experimentally verified protein-protein interactions mined from literature by expert curators.
- Good biological fit for direct PPI evidence, but likely substantial overlap with IntAct/IMEx and the same PSI-MI ecosystem.

Endpoint namespaces:

- PSICQUIC/MITAB access. Expect MITAB-style interactor A/B identifiers, usually UniProt-oriented for proteins, with alternate IDs and aliases.
- Must keep MINT source IDs separate from IntAct/IMEx IDs to avoid losing provenance.

Directionality/sign/effect:

- Primarily curated PPI and enzymatic modification evidence; mostly `protein_interacts_protein` unless modification/regulatory effects are explicit.

Confidence/method/publications:

- MITAB/PSI-MI fields should preserve detection method, publication identifiers, interaction type, source database, interaction identifiers, and confidence where present.

Access/license constraints:

- Public PSICQUIC endpoint is advertised from the MINT site. Exact redistribution/license terms should be checked before promotion, because the home page is explicit about public/open access but not enough for downstream product/commercial redistribution policy.

Proposed relation handling:

- Use as additional `protein_interacts_protein` evidence only after overlap audit against IntAct.
- Do not make a separate MINT relation.

### BioGRID

Classification: **recommended with strict subset filters**

Mechanism fit:

- BioGRID provides experimentally observed interactions, including physical interactions, genetic interactions, chemical interactions, post-translational modifications, and complexes.
- It is valuable precisely because it separates `Experimental System Type`; only `physical` and source-native PTM/complex subsets should feed causal molecular-mechanism relations.
- Explicitly exclude `genetic` interaction rows from `protein_interacts_protein`; those are genotype/phenotype interaction evidence and belong in a separate gene/genetic relation only if that schema is desired.

Endpoint namespaces:

- TAB3 header includes Entrez Gene IDs, BioGRID IDs, official symbols, organism IDs, and protein accessions (`SWISS-PROT`, `TREMBL`, `REFSEQ`) for each interactor.
- MITAB export header includes interactor IDs, alternate IDs, aliases, detection method, publication identifiers, taxids, interaction types, source database, interaction identifiers, confidence.
- Best endpoint policy: prefer UniProt/Swiss-Prot accessions for protein relations when present; keep Entrez/BioGRID IDs in evidence. Rows without protein accession support should remain gene-level or evidence-only.

Directionality/sign/effect:

- Many physical interactions are undirected. PTM rows carry modification type/site and can imply directed enzyme→substrate regulation only if the experimental system/ontology terms identify enzyme and target roles.
- Complex downloads can support `protein_part_of_complex`; do not infer complex membership from generic physical pairs.

Confidence/method/publications:

- TAB3 fields preserve experimental system, experimental system type, author, publication source, throughput, score, modification, qualifications, tags, source database, accessions, ontology term IDs/names/categories/qualifiers.

Access/license constraints:

- Download page states BioGRID data are freely available for academic and commercial users under the MIT License; publications are requested to cite BioGRID and original contributing authors.
- Large bulk downloads are available as latest release ZIPs and organism-specific files.

Proposed relation handling:

- `protein_interacts_protein` for physical interaction rows with protein endpoints/accessions.
- `protein_regulates_protein` for high-confidence PTM/regulation rows only when source fields identify direction/mechanism/target site.
- `protein_part_of_complex` from explicit complex datasets.
- Evidence-only or separate future genetic relation for genetic interaction rows.

### IID

Classification: **maybe / reject full compendium for causal mechanism**

Mechanism fit:

- IID is an integrated database of detected and predicted PPIs across species, annotated with tissues, diseases, localizations, developmental stages, drugs, complexes, directionality, duration, mutation effects, and evidence classes.
- It explicitly includes experimentally detected PPIs from multiple curated databases plus orthology and machine-learning predictions.
- The full compendium is not a clean causal mechanism source because it mixes experimental, predicted, and orthology-projected evidence and imports sources already considered separately.

Endpoint namespaces:

- Query UI accepts gene symbols, UniProt IDs, and Entrez Gene IDs. Endpoint export fields must be inspected before implementation.
- Treat endpoint policy as unresolved until a download/API sample is audited; do not assume protein-native endpoints merely because the UI accepts UniProt.

Directionality/sign/effect:

- IID exposes directionality filters and mutation effects, but these are integrated annotations. Preserve them as evidence/context fields; use for `protein_regulates_protein` only if the underlying source row asserts direction/mechanism.

Confidence/method/publications:

- Evidence classes include experimental, orthology, and machine-learning prediction; experimental evidence thresholds and detection types are selectable.
- Context annotations include tissue/stage/disease/localization and complex/drug/protein-class filters.

Access/license constraints:

- Web download is available, but exact bulk redistribution terms were not obvious from the checked page. Because IID aggregates imported sources, downstream license/source decomposition is mandatory.

Proposed relation handling:

- Reject full IID as a causal mechanism replacement.
- Maybe use `experimental` rows only as evidence after decomposing original source and excluding predicted/orthology-only rows.
- Use predicted/contextualized rows as features, not graph causal edges.

### InnateDB

Classification: **maybe**

Mechanism fit:

- InnateDB describes itself as a database of genes, proteins, experimentally verified interactions, and signaling pathways involved in innate immune responses in human, mouse, and bovine.
- Strong niche value for immune/inflammation biology; not a global replacement for all PPIs.
- It includes InnateDB-curated interactions and imported experimentally validated interactions, so provenance must distinguish native curation from imported source records.

Endpoint namespaces:

- Search/download surfaces are gene/protein centered. Endpoint IDs must be audited from the download/API output before choosing canonical protein IDs.
- Candidate endpoint policy: use UniProt/protein IDs when source-native; keep gene identifiers as evidence xrefs, not protein endpoints by projection.

Directionality/sign/effect:

- Interaction search supports interaction type and cell type; pathway/signaling context may imply direction. Use `protein_regulates_protein` only when a row has explicit direction/effect/mechanism, not merely pathway co-membership.

Confidence/method/publications:

- Focuses on experimentally verified molecular interactions; expected fields include interaction type, source/originating database for imported records, cell type/context, and publication support. Exact export schema must be sampled during implementation.

Access/license constraints:

- Site states InnateDB curated interactions are licensed under the Design Science License; all other data follow originating database terms.
- This is acceptable only if evidence records preserve native/imported source and license provenance.

Proposed relation handling:

- `protein_interacts_protein` for experimentally verified protein interactions with protein endpoints.
- `protein_regulates_protein` for explicit signaling/regulatory mechanism rows.
- Evidence-only for pathway co-membership or imported rows whose originating license/source cannot be resolved.

### SIGNOR

Classification: **recommended**

Mechanism fit:

- Best candidate among the listed sources for directed, signed, mechanism-aware regulation.
- SIGNOR all-data TSV directly exposes entity A/B, entity types, IDs/databases, effect, mechanism, residue/sequence, PMIDs, direct flag, evidence sentence, score, and SIGNOR relation ID.
- CausalTab export exposes MITAB-like fields plus biological effects, causal regulatory mechanism, and causal statement.

Endpoint namespaces:

- Human TSV sample uses `IDA/IDB` with `DATABASEA/DATABASEB`, including `UNIPROT` for proteins and `SIGNOR` IDs for protein families/complexes.
- Entity types include protein, protein family, complex, phenotype/stimulus/chemical-like entities. Filter endpoint types explicitly.

Directionality/sign/effect:

- Direction is source-native: ENTITYA regulates ENTITYB. Effects include `up-regulates`, `down-regulates`, `down-regulates activity`, `unknown`, etc. Mechanism includes binding, phosphorylation, and other controlled vocabulary terms. `DIRECT=YES/NO` distinguishes directness.
- This should not be canonical-sorted.

Confidence/method/publications:

- TSV fields include PMID, directness, notes, annotator, supporting sentence, score, residue/sequence for modifications, cell/tissue data, modulator/target complex, and SIGNOR_ID.

Access/license constraints:

- SIGNOR site states SIGNOR 3.0 is licensed under Creative Commons Attribution 4.0 International. Downloads are available as stable releases, TSV, causalTab, SBML beta, complexes, protein families, phenotypes, stimuli, phosphorylation, and transcriptional relations.

Proposed relation handling:

- `protein_regulates_protein` for protein→protein rows with explicit effect/mechanism and UniProt/protein endpoints.
- `protein_part_of_complex` for explicit SIGNOR complex membership downloads.
- `protein_interacts_protein` only for direct binding rows without regulatory sign/effect.
- Family/complex endpoints should not be forced into protein nodes; either model family/complex nodes or keep as evidence until those node families are active.

### OmniPath

Classification: **recommended for curated mechanism subsets; maybe as full aggregator**

Mechanism fit:

- OmniPath is an integration service with directed/signaling/regulatory interactions and explicit booleans such as `is_directed`, `is_stimulation`, `is_inhibition`, plus consensus direction/stimulation/inhibition in API output.
- It is useful for mechanism-aware signaling, ligand-receptor, kinase/substrate, and pathway-extra datasets, but it is an aggregator: source decomposition is non-negotiable.

Endpoint namespaces:

- API sample returns UniProt-like protein accessions (`source`, `target`) for human protein interactions.
- Keep OmniPath source/target as original protein IDs, and preserve provider/resource-level xrefs in evidence.

Directionality/sign/effect:

- Strong fit for `protein_regulates_protein` when `is_directed` and stimulation/inhibition/mechanism fields are populated and supported by acceptable source resources.
- Use `protein_interacts_protein` for undirected physical interactions only when a source resource supports physical interaction.

Confidence/method/publications:

- API output can include source databases/resources, references, curation flags, direction/sign, mechanism/dataset membership, and interaction categories depending on query options. Require resource list and references in evidence before promotion.

Access/license constraints:

- OmniPath resource metadata lists heterogeneous licenses per underlying source: many CC BY 4.0/commercial-compatible resources, but also CC BY-NC, CC BY-SA, GPL/LGPL, HPRD, and unspecified/non-commercial terms. OmniPath itself/resource metadata is not enough to license all rows uniformly.
- Use only rows whose originating resources are license-compatible for the intended KG use, or store as internal features with license flags.

Proposed relation handling:

- `protein_regulates_protein` for directed signed rows from license-compatible mechanism resources.
- `protein_interacts_protein` for direct physical rows from acceptable source resources.
- Evidence-only/features for rows from non-commercial/unclear resources or broad consensus rows without source-level provenance.

### STRING

Classification: **reject_for_causal_mechanism** for broad STRING; **maybe** for physical subnetwork as low-priority evidence/features

Mechanism fit:

- STRING is explicitly a functional protein association network, not a pure physical/mechanistic causal source.
- Download files include full protein links, detailed subscores by channel, and physical subnetwork files. Even physical files are scored/integrated and include experimental/database/text-mining channels, not necessarily source-native mechanistic evidence.

Endpoint namespaces:

- Human download rows use STRING protein identifiers like `9606.ENSP...`; alias files map to other accessions. Endpoint policy can map to protein nodes only after validating ENSP/protein node compatibility.

Directionality/sign/effect:

- STRING links are scored associations and are not directed/signed causal regulation.
- Detailed physical header observed: `protein1 protein2 experimental database textmining combined_score`.

Confidence/method/publications:

- Provides combined score and channel subscores (experimental, database, text mining, etc.). It does not generally provide row-level experimental method/PMID as a curated PSI-MI evidence row in the physical links download.

Access/license constraints:

- STRING access/download pages state files are freely available under Creative Commons BY 4.0.

Proposed relation handling:

- Do not use broad STRING as replacement for causal/mechanistic `gene_interacts_gene` use-cases.
- Optionally keep STRING as evidence/features under a `functional_association` concept, or as low-priority support for `protein_interacts_protein` only when using `protein.physical.links.*` with clear flags: `source_dataset=string_physical`, `evidence_type=predicted_or_integrated_physical_association`, channel scores preserved, and no causal claims.

## Proposed approval set for Jérémie

Ask Jérémie to approve this source set before any ingestion/build cards:

1. Approve **IntAct direct** as the primary experimental PPI source for `protein_interacts_protein`.
2. Approve **BioGRID physical/PTM/complex subsets only**, with genetic interactions excluded from protein mechanism relations.
3. Approve **SIGNOR direct** as the primary directed/signed `protein_regulates_protein` source and a complex/family evidence source.
4. Approve **OmniPath only with license-compatible resource filtering and source decomposition**.
5. Decide whether **MINT** is worth a separate overlap audit after IntAct, or should be treated as covered through IntAct/IMEx unless native MINT IDs add evidence.
6. Decide whether **InnateDB** is in-scope now for immune/inflammation enrichment, or deferred.
7. Reject **broad STRING** for causal mechanism replacement; optionally approve STRING physical as feature/evidence-only support, not a causal relation source.
8. Reject **full IID** for causal mechanism replacement; optionally approve an experimental-only, source-decomposed IID audit later.

## Implementation gates if approved later

This proposal intentionally creates no ingestion/build cards. If approved later, each source builder should pass these gates:

1. Download/sample raw source in scratch only; record release/version/license.
2. Inspect raw schema and endpoint namespaces before mapping.
3. Filter source-native protein/isoform/complex endpoints; no gene→protein projection.
4. Preserve original source IDs and endpoint namespaces in evidence.
5. Keep directed/signed rows source-ordered; do not canonical-sort regulator/target pairs.
6. Materialize edge and evidence together in scratch/staging.
7. Validate node anti-joins for protein/complex endpoints.
8. Run edge/evidence support audit.
9. Update `docs/source_measure_edge_matrix.md`, `docs/kg_schema_overview.md`, and coverage reports with real counts.
