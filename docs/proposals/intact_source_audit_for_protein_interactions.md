# IntAct source audit for protein interaction ingestion

Date: 2026-06-21

Status: source audit only; no ingestion/build performed.

## Executive decision

Use IntAct raw MITAB27 exports as evidence-first inputs for any future `protein_interacts_protein` builder. Do **not** use the vague label "IntAct direct" and do **not** build from the existing broad `gene_interacts_gene` rows. The exact recommended starting files are:

1. Primary human-scoped positive evidence input:
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/species/human.txt`
   - compressed mirror: `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/species/human.zip`
2. Primary human-scoped negative evidence input:
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/species/human_negative.txt`
3. Full positive evidence input if the builder wants non-human/pathogen interactions before filtering:
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/intact.txt`
   - compressed mirror: `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/intact.zip`
4. Full negative evidence input if the builder wants non-human/pathogen interactions before filtering:
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/intact_negative.txt`
5. Feature side tables to preserve binding regions, mutations, and PTM-like participant features:
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/bindings_regions.tsv`
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/mutations.tsv`
   - `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/ptms.tsv`

Treat `intact-micluster.txt` / `intact-micluster.zip` and `intact-micluster_negative.txt` as optional clustered graph/assertion aids, not as the primary evidence source. The IntAct README says `intact.txt` has one line per interaction evidence since 2009; MIcluster summarizes unique binary pairs and aggregates detection methods/publications/interaction types. That aggregation is useful for deduplication or comparison, but it loses the one-row-per-evidence semantics we need for Jouvence evidence tables.

## Inspected current IntAct download structure

Inspection target: `https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/`

Current release timestamps in the listing were `2026-01-14`.

Root files/directories inspected:

| Path | Size in listing | Role |
|---|---:|---|
| `README` | 2.2K | MITAB27 notes; states one row per interaction evidence in `intact.txt` since 2009. |
| `intact.txt` | 10G | Full raw positive MITAB27 evidence export. |
| `intact.zip` | 1.3G | Compressed full raw positive export. |
| `intact_negative.txt` | 4.9M | Full raw negative MITAB27 evidence export. |
| `intact-micluster.txt` | 6.0G | Clustered/summarized binary-pair export; not evidence-first. |
| `intact-micluster.zip` | 852M | Compressed MIcluster export. |
| `intact-micluster_negative.txt` | 4.2M | Clustered/summarized negative export. |
| `datasets/` | directory | Thematic slices such as `Cancer.txt`, `Virus.txt`; not the primary canonical input. |
| `features/` | directory | Participant feature side tables. |
| `species/` | directory | Species-scoped MITAB27 exports, including human. |
| `pmid/` | directory | PMID/year sharded MITAB exports. |
| `pmidMITAB27.zip` | 1.3G | PMID-sharded MITAB archive. |

Relevant `datasets/` entries observed:

- `AFCS.txt` / `AFCS.zip`
- `Affinomics.txt` / `Affinomics.zip`
- `Alzheimers.txt` / `Alzheimers.zip`
- `Apoptosis.txt` / `Apoptosis.zip`
- `Autism.txt` / `Autism.zip`
- `BioCreative.txt` / `BioCreative.zip`
- `Brain_Disease.txt` / `Brain_Disease.zip`
- `Cancer.txt` / `Cancer.zip`
- `Cardiac.txt` / `Cardiac.zip`
- `Chromatin.txt` / `Chromatin.zip`
- `Coronavirus.txt` / `Coronavirus.zip`
- `Crohn's_disease.txt` / `Crohn's_disease.zip`
- `Diabetes.txt` / `Diabetes.zip`
- `Huntington's.txt` / `Huntington's.zip`
- `IBD.txt` / `IBD.zip`
- `Neurodegeneration.txt` / `Neurodegeneration.zip`
- `Neurodevelopmental_disease.txt` / `Neurodevelopmental_disease.zip`
- `PDBe.txt` / `PDBe.zip`
- `Parkinsons.txt` / `Parkinsons.zip`
- `Rare_diseases.txt` / `Rare_diseases.zip`
- `Synapse.txt` / `Synapse.zip`
- `Ulcerative_colitis.txt` / `Ulcerative_colitis.zip`
- `Virus.txt` / `Virus.zip`
- `sfari_genes.txt` / `sfari_genes.zip`

Use dataset slices only for targeted analyses or incremental QA. They are not clean relation definitions and should not replace raw MITAB evidence rows.

Relevant `species/` entries observed:

| File | Size in listing | Note |
|---|---:|---|
| `human.txt` | 8.6G | Human species-scoped positive MITAB27 export. Sample rows are 42-column MITAB27. |
| `human.zip` | 1.1G | Compressed human positive export. |
| `human_negative.txt` | 4.8M | Human species-scoped negative MITAB27 export. |

The species directory also has `Human.zip` (capital H, 423M) and many virus names containing `Human`; do not accidentally select those by broad substring matching. Use exact filenames `human.txt`, `human.zip`, and `human_negative.txt` for human species-scoped IntAct.

Important caveat: `species/human.txt` and `species/human_negative.txt` can include rows where one participant is human and the other is another organism, e.g. human-chick or human-mouse negative evidence. A human-only `protein_interacts_protein` builder must still require both participant taxids to be `taxid:9606` if the intended graph endpoints are human proteins only.

## MITAB27 columns to preserve

The inspected raw positive and negative files (`intact.txt`, `intact_negative.txt`, `species/human.txt`, `species/human_negative.txt`) share a 42-column MITAB27 header:

1. `ID(s) interactor A`
2. `ID(s) interactor B`
3. `Alt. ID(s) interactor A`
4. `Alt. ID(s) interactor B`
5. `Alias(es) interactor A`
6. `Alias(es) interactor B`
7. `Interaction detection method(s)`
8. `Publication 1st author(s)`
9. `Publication Identifier(s)`
10. `Taxid interactor A`
11. `Taxid interactor B`
12. `Interaction type(s)`
13. `Source database(s)`
14. `Interaction identifier(s)`
15. `Confidence value(s)`
16. `Expansion method(s)`
17. `Biological role(s) interactor A`
18. `Biological role(s) interactor B`
19. `Experimental role(s) interactor A`
20. `Experimental role(s) interactor B`
21. `Type(s) interactor A`
22. `Type(s) interactor B`
23. `Xref(s) interactor A`
24. `Xref(s) interactor B`
25. `Interaction Xref(s)`
26. `Annotation(s) interactor A`
27. `Annotation(s) interactor B`
28. `Interaction annotation(s)`
29. `Host organism(s)`
30. `Interaction parameter(s)`
31. `Creation date`
32. `Update date`
33. `Checksum(s) interactor A`
34. `Checksum(s) interactor B`
35. `Interaction Checksum(s)`
36. `Negative`
37. `Feature(s) interactor A`
38. `Feature(s) interactor B`
39. `Stoichiometry(s) interactor A`
40. `Stoichiometry(s) interactor B`
41. `Identification method participant A`
42. `Identification method participant B`

Example source-native values seen in samples:

- Participant IDs: `uniprotkb:O43426`, `uniprotkb:P49418`, `intact:EBI-*`, `ensembl:ENSP...` in alternate IDs.
- Detection methods: `psi-mi:"MI:0084"(phage display)`, `psi-mi:"MI:0019"(coimmunoprecipitation)`, `psi-mi:"MI:0007"(anti tag coimmunoprecipitation)`.
- Interaction types: `psi-mi:"MI:0407"(direct interaction)`, `psi-mi:"MI:0915"(physical association)`, `psi-mi:"MI:0914"(association)`.
- Source DBs: `psi-mi:"MI:0471"(MINT)`, `psi-mi:"MI:0469"(IntAct)`, `psi-mi:"MI:0486"(UniProt)`, `psi-mi:"MI:1335"(HPIDb)`.
- Confidence values: `intact-miscore:0.67`, `replication-based confidence:3|intact-miscore:0.40`.
- Experimental roles: `psi-mi:"MI:0496"(bait)`, `psi-mi:"MI:0498"(prey)`, `psi-mi:"MI:0497"(neutral component)`.
- Interactor types: `psi-mi:"MI:0326"(protein)`, `psi-mi:"MI:0327"(peptide)`, and non-protein types in some rows.
- Host organisms: `taxid:-1(in vitro)`, organism taxids, or `-`.
- Negative flag: `false` in positive exports; negative rows should carry `true`/negative status from the export/column.
- Feature fields: inline `binding-associated region:626-695(...)` in MITAB plus richer side-table rows by `Interaction AC`.

The inspected MIcluster exports have only 36 columns and omit the final participant feature/stoichiometry/participant identification method columns. They also aggregate many evidence values in one row. That is exactly why MIcluster should not be the primary evidence input.

## Feature side-table columns

The inspected feature files share a 16-column TSV header:

1. `Feature AC`
2. `Feature short label`
3. `Feature range(s)`
4. `Original sequence`
5. `Resulting sequence`
6. `Feature type`
7. `Feature annotation(s)`
8. `Affected molecule identifier`
9. `Affected molecule symbol`
10. `Affected molecule full name`
11. `Affected molecule organism`
12. `Interaction participants`
13. `PubMed ID`
14. `Figure legend(s)`
15. `Interaction AC`
16. `Xref ID(s)`

Files and observed semantics:

- `features/bindings_regions.tsv`: binding regions such as `psi-mi:"MI:0442"(sufficient binding region)` with ranges and affected molecule identifiers.
- `features/mutations.tsv`: mutation rows, including `psi-mi:"MI:2226"(mutation with no effect)`, original/resulting sequence, PubMed/IMEx IDs, figure legends, and interaction accessions.
- `features/ptms.tsv`: PTM/modification-like features, including PSI-MOD terms such as `psi-mod:"MOD:00160"(N4-glycosyl-L-asparagine)`, but also some feature types that are not necessarily protein PTMs; filter by affected molecule type/organism and do not infer directed PTM regulation just from this table.

Join these side tables to MITAB rows by `Interaction AC` / `Interaction identifier(s)` where possible. Keep them in evidence metadata or a normalized evidence-feature side table; do not collapse them into the graph edge key.

## What supports `protein_interacts_protein`

Rows support `protein_interacts_protein` when all of the following hold:

1. Positive assertion:
   - Source file is `intact.txt` or `species/human.txt`, or the MITAB `Negative` column is `false`.
   - Do not create positive graph edges from `intact_negative.txt` or `species/human_negative.txt`.
2. Protein/isoform endpoints:
   - `Type(s) interactor A` and `Type(s) interactor B` are protein-like, primarily `psi-mi:"MI:0326"(protein)`.
   - Preserve isoform IDs such as `uniprotkb:O54918-3` as source endpoint IDs; map to canonical protein/isoform nodes only by explicit node policy.
   - Do not rescue gene-only, RNA, chemical, peptide, or complex endpoints by gene→protein projection.
3. Intended organism scope:
   - For a human-only Jouvence relation, require both `Taxid interactor A` and `Taxid interactor B` to include `taxid:9606`.
   - Host-pathogen, human-mouse, or other cross-species rows may be valuable, but they need either non-human protein nodes or a separate host-pathogen evidence policy.
4. Interaction semantics:
   - Accept physical/molecular interaction terms such as direct interaction, physical association, association, colocalization/enzymatic reaction only after term-level review.
   - Store the exact PSI-MI interaction type as evidence. Do not encode every MI term into relation names.
5. Directionality:
   - Treat most IntAct MITAB binary PPI rows as undirected graph assertions. Experimental roles (`bait`, `prey`) and biological roles are assay/context roles, not causal direction.
   - Only route to a future directed relation (`protein_regulates_protein` or PTM-specific relation) if the row and/or feature evidence explicitly states a regulatory effect/mechanism and the endpoint roles are source-native.

Recommended edge key for `protein_interacts_protein` if approved later:

- canonicalize only after endpoint mapping, e.g. sort `(protein_id_a, protein_id_b)` for undirected interactions;
- retain source order in evidence fields: `source_interactor_a`, `source_interactor_b`, original IDs, roles, methods, and raw taxids;
- do not drop multiple evidence rows supporting the same canonical edge.

## What should not become `protein_interacts_protein`

Keep these rows evidence-only or route to a different future relation/schema:

- Negative evidence rows from `intact_negative.txt`, `species/human_negative.txt`, or rows with `Negative=true`: store as negative/supporting evidence, not positive graph edges.
- Any row with non-protein participants: RNA, chemicals, genes, complexes, peptides, synthetic constructs, or intact-only molecules without a protein node mapping.
- Rows with only one human participant if the active relation is human-human only.
- Feature/PTM rows by themselves: they annotate an interaction and may later support PTM/regulatory schemas, but do not imply `protein_interacts_protein` unless the paired MITAB row passes endpoint and assertion filters.
- Thematic `datasets/` slices as relation definitions. They are subsets/views, not source-native biological predicates.
- MIcluster rows as primary evidence. They can support clustered-edge QA or maybe a derived graph assertion table, but not the raw evidence table.

## Proposed evidence schema for `evidence/protein_interacts_protein.parquet`

Minimum source-native evidence fields:

| Field | Source / derivation |
|---|---|
| `edge_relation` | constant `protein_interacts_protein` for accepted positive evidence. |
| `edge_x_id`, `edge_y_id` | canonical protein/isoform endpoint IDs after approved mapping. |
| `source_dataset` | exact export path, e.g. `intact_species_human_mitab27_2026_01_14`. |
| `source_file` | exact filename/URL such as `species/human.txt`. |
| `source_row_number` | row number in source file after header. |
| `source_interactor_a_id`, `source_interactor_b_id` | MITAB `ID(s) interactor A/B`. |
| `source_interactor_a_alt_ids`, `source_interactor_b_alt_ids` | raw alternate IDs. |
| `source_interactor_a_aliases`, `source_interactor_b_aliases` | raw aliases. |
| `source_interactor_a_namespace`, `source_interactor_b_namespace` | parsed namespace(s), e.g. `uniprotkb`, `intact`, `ensembl`. |
| `source_interactor_a_type`, `source_interactor_b_type` | MITAB interactor type PSI-MI terms. |
| `taxid_interactor_a`, `taxid_interactor_b` | raw taxid fields. |
| `interaction_type` | MITAB `Interaction type(s)` PSI-MI values. |
| `predicate` | normalized broad predicate such as `direct_interaction`, `physical_association`, `association`, while preserving raw MI term. |
| `detection_method` | MITAB `Interaction detection method(s)`. |
| `participant_identification_method_a`, `participant_identification_method_b` | final MITAB columns 41/42. |
| `biological_role_a`, `biological_role_b` | MITAB biological role columns. |
| `experimental_role_a`, `experimental_role_b` | MITAB experimental role columns. |
| `host_organism` | MITAB `Host organism(s)`. |
| `publication_first_author` | MITAB publication first author field. |
| `publication_ids` | raw publication identifiers, preserving `pubmed:*`, `imex:*`, MINT IDs, etc. |
| `pmids` | parsed PubMed IDs, array/string-list. |
| `source_database` | MITAB `Source database(s)`. |
| `interaction_identifiers` | IntAct/MINT/IMEx interaction IDs. |
| `confidence_values` | raw confidence values, e.g. `intact-miscore:*`. |
| `intact_miscore` | parsed numeric score where present. |
| `expansion_method` | MITAB `Expansion method(s)`. |
| `negative` | boolean from MITAB/export. Positive edge rows should be false; negative evidence can go in separate table or flagged evidence. |
| `features_a`, `features_b` | MITAB inline features. |
| `stoichiometry_a`, `stoichiometry_b` | MITAB stoichiometry columns. |
| `feature_side_table_refs` | joined `Feature AC` / feature record IDs from side tables. |
| `binding_regions` | normalized records from `features/bindings_regions.tsv` when joined. |
| `mutations` | normalized records from `features/mutations.tsv` when joined. |
| `ptms` | normalized records from `features/ptms.tsv` when joined. |
| `interaction_xrefs` | MITAB interaction xrefs. |
| `interaction_annotations` | MITAB interaction annotations. |
| `parameters` | MITAB interaction parameters. |
| `creation_date`, `update_date` | MITAB dates. |
| `checksums_a`, `checksums_b`, `interaction_checksums` | MITAB checksum columns. |
| `raw_mitab_json` | optional raw record payload for audit/reparse. |

For negative rows, prefer a separate `evidence/protein_interacts_protein_negative.parquet` or the same evidence table with `negative=true` and an explicit guarantee that graph edge materialization filters `negative=false`. I prefer a separate negative evidence side table to make accidental positive promotion harder.

## MIcluster policy

Use raw IntAct first:

- `intact.txt` / `species/human.txt` are one-row-per-evidence MITAB27 exports.
- They preserve final MITAB27 feature, stoichiometry, and participant identification method fields.
- They preserve evidence multiplicity: multiple publications/methods can support one graph edge as multiple evidence rows.

Use MIcluster only as auxiliary:

- `intact-micluster.txt` has 36 columns, not 42.
- It aggregates detection methods, publications, interaction types, roles, and identifiers per binary pair.
- It can be used to compare final edge deduplication, to precompute a clustered assertion candidate list, or to verify that raw evidence aggregation produces compatible pairs.
- It should not replace evidence rows and should not be the source of row-level feature/mutation/binding-site evidence.

## Recommended staged builder task inputs and filters

If Jérémie approves an IntAct ingestion builder later, use this staged plan:

### Stage 0: download/sample only

Inputs:

- Required: `species/human.txt` or `species/human.zip`.
- Required negative side input: `species/human_negative.txt`.
- Required feature side inputs: `features/bindings_regions.tsv`, `features/mutations.tsv`, `features/ptms.tsv`.
- Optional QA input: `intact-micluster.txt` or `intact-micluster.zip`.
- Optional full-source input: `intact.txt` / `intact.zip` if non-human/pathogen support is in scope.

Record exact URL, listing timestamp, source file size, checksum if computed, and MITAB header. Do not write canonical KG files in this stage.

### Stage 1: schema/field parser

Parse all 42 MITAB27 columns by header name, not by hard-coded positional assumptions alone. Parse multi-valued pipe-delimited PSI-MI/xref fields while preserving the raw strings.

Required parser outputs:

- endpoint IDs and namespaces;
- endpoint type MI terms;
- taxids;
- interaction type MI terms;
- detection method MI terms;
- source DBs;
- publication IDs / PMIDs / IMEx IDs;
- interaction IDs;
- confidence values and parsed `intact-miscore`;
- biological/experimental roles;
- host organism;
- expansion method;
- negative flag;
- inline features and side-table feature records.

### Stage 2: candidate filters for `protein_interacts_protein`

For the initial human-human protein relation, filter to:

- `negative == false`;
- both interactor types include `psi-mi:"MI:0326"(protein)`;
- both interactor taxid fields include `taxid:9606`;
- both endpoints have accepted protein/isoform identifiers, preferably `uniprotkb:*` primary IDs or approved protein-node xrefs;
- interaction type is in an explicitly reviewed allowlist, initially including physical/direct terms such as `MI:0407` direct interaction, `MI:0915` physical association, and possibly `MI:0914` association with predicate preserved.

Reject or quarantine:

- peptides (`MI:0327`) until peptide/protein endpoint policy exists;
- RNAs, genes, chemicals, synthetic constructs, complexes unless their own relation schema exists;
- cross-species interactions for the human-human tranche;
- rows without accepted endpoint mapping;
- all negative rows for positive edge materialization.

### Stage 3: edge/evidence materialization in scratch only

Materialize:

- deduplicated `edges/protein_interacts_protein.parquet` from canonical mapped protein IDs;
- evidence rows retaining raw A/B order and all source-native fields;
- optional negative evidence side table;
- optional feature side table keyed by source interaction IDs and feature accessions.

Do not promote to canonical KG until endpoint anti-joins, evidence support audit, and doc/test updates pass.

### Stage 4: QA against MIcluster and source counts

Use MIcluster only for QA:

- compare raw-evidence-deduplicated pairs against `intact-micluster.txt` after applying the same endpoint/taxid filters;
- explain discrepancies from clustering, identifier normalization, negative filtering, and endpoint exclusions;
- do not force raw evidence to match MIcluster if that would drop row-level evidence.

## Open decisions before ingestion

1. Endpoint namespace policy: use UniProt accessions as canonical protein nodes if present, or map to the existing Jouvence protein node namespace; isoforms (`P12345-2`) need an explicit keep-vs-collapse policy.
2. Human-only scope: initial relation should probably be human-human only. Host-pathogen IntAct rows are valuable but should be a separate tranche/relation if non-human protein nodes are active.
3. Interaction type allowlist: `direct interaction` and `physical association` are easy; broad `association`, colocalization, enzymatic reactions, and genetic/phenotypic-looking MI terms need a reviewed allowlist/denylist.
4. Negative evidence storage: separate negative evidence table is safer than mixing with positive edge evidence, but the downstream audit tooling must know how to handle it.
5. Feature normalization: decide whether binding regions/mutations/PTMs stay JSON-packed in evidence rows first, or become a normalized side table keyed by `interaction_identifiers` + `Feature AC`.

## Bottom line

For Jouvence/TxGNN source-native protein interactions, the right IntAct source is **raw MITAB27 evidence**, primarily `species/human.txt` plus `species/human_negative.txt` and the three `features/*.tsv` files. MIcluster is a useful clustered comparison artifact, not the evidence source. Future builder cards should be explicit about exact filenames, organism filters, interactor type filters, negative handling, and full preservation of PSI-MI/evidence fields.
