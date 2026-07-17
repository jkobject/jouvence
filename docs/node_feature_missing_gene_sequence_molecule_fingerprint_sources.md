# Missing node feature source audit: `gene_sequence` and `molecule_fingerprint`

Task: `t_36d80bee`  
Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`  
Scope: source/schema decision audit only. This document authorizes no biological edge writes, no evidence writes, no canonical feature promotion, and no ReMap dependency.

## Context

The official feature layer at `gs://jouvencekb/kg/v2/features/` currently contains 10 reviewer-approved feature tables: `protein_sequence`, `transcript_sequence`, and textual-summary tables for selected node types. The official promotion report (`docs/node_feature_tables_official_promotion_report.md`) states that the promotion was feature-layer-only and wrote no `edges/` or `evidence/` objects.

The prior sequence source audit (`docs/node_sequence_feature_sources.md`) explicitly deferred gene-level genomic sequence because full gene sequence is large and ambiguous without coordinate, strand, reference-build, and context-length policy. Jérémie noticed that at least `gene_sequence` and `molecule_fingerprint` are still missing from the feature-layer contract; this audit decides what those names should mean before any build card is opened.

Local cache inspected for this audit:

- `.omoc/gcs-cache/kg-v2/nodes/gene.parquet`: 267,830 rows. Columns include `id`, `ncbi_gene_id`, `hgnc_id`, `uniprot_id`, `gene_name`, `name`, `description`, `biotype`; no chromosome/start/end/strand coordinates are present in the cached node table.
- `.omoc/gcs-cache/kg-v2/nodes/molecule.parquet`: 31,007 rows. Columns include `id`, `smiles`, `inchikey`, `name`, `description`, `drug_type`, approval/clinical fields. `smiles` and `inchikey` are non-null for 22,230 rows. There is no separate `canonical_smiles` column in this cached node table, although notebooks mention canonical-smiles fields in earlier LaminDB setup context.

## Common principles for the missing tables

- Feature tables live under `features/` and are model features, not KG graph assertions.
- A feature row must join cleanly to `nodes/<node_type>.parquet.id`; endpoint anti-joins must be zero before staging/promotion.
- Rows must carry source, source_dataset, source_record_id, source_release/release, provenance, license, citation, created_at, and a deterministic `feature_key`.
- No transcript-derived shortcut may be called `gene_sequence`. If the sequence is transcript/cDNA-derived, name it transcript/cDNA-specific.
- No placeholder Parquets should be created for deferred decisions.
- This work has no ReMap dependency; ReMap is an enhancer/regulatory-source concern, not a prerequisite for either gene genomic sequence or molecule fingerprints.

## Decision matrix

| node_type | candidate feature table | meaning | recommended source | release/build | mapping | recommended decision |
|---|---|---|---|---|---|---|
| `gene` | `gene_genomic_sequence` | Reference genomic sequence spanning the gene locus only, extracted from GRCh38 using reviewed Ensembl/GENCODE coordinates and strand. Includes introns; not a transcript/cDNA proxy. | Ensembl or GENCODE gene annotation GTF/GFF3 + matching GRCh38 primary assembly FASTA. | Pin exact Ensembl/GENCODE release and reference FASTA checksum. Prefer release aligned with existing Ensembl release 114 sequence wave if available, otherwise explicitly document the mismatch. | ENSG ID from source coordinates to KG gene node ID. Current cached `gene.parquet` uses NCBI-like IDs in `id` and has no coordinate columns, so a builder needs an explicit ENSG/NCBI/HGNC mapping source before sequence extraction. | Accept as the correct immediate build candidate, but name it `gene_genomic_sequence` rather than bare `gene_sequence` unless the schema reserves `gene_sequence` as an alias with `sequence_kind=genomic_locus`. |
| `gene` | `gene_coordinates` or `gene_genomic_interval` | Coordinates-only feature: chromosome, start/end, strand, reference build, source record, and optional length; no raw sequence payload. | Same Ensembl/GENCODE GTF/GFF3 coordinate source. | Same as above. | Same as above. | Recommended as a smaller precursor/companion table if full genomic strings are too large for model storage. This may be buildable before sequence extraction once mapping is settled. |
| `gene` | `gene_promoter_sequence` | Strand-aware promoter window sequence upstream of TSS, optionally plus a bounded gene-body prefix/window. | Ensembl/GENCODE transcript/gene models + GRCh38 FASTA. | Pin window policy and release. | Requires TSS/canonical transcript policy. | Defer. Promoter windows are model-useful but policy-heavy; do not fold them into `gene_sequence`. |
| `gene` | `gene_transcript_derived_sequence` | Canonical transcript cDNA or representative transcript sequence projected to gene. | Existing `transcript_sequence` plus a canonical transcript policy, or Ensembl canonical transcript FASTA. | Existing transcript release or pinned Ensembl release. | gene -> canonical transcript. | Defer or reject as `gene_sequence`; only build under an explicit transcript-derived name if a downstream model needs it. |
| `molecule` | `molecule_fingerprint` | Deterministic cheminformatics fingerprint computed from each molecule node's reviewed canonicalized SMILES. | Existing molecule node `smiles` from ChEMBL/OpenTargets drug metadata, optionally recanonicalized by RDKit and recorded. | Pin KG molecule source release plus RDKit version and fingerprint parameters. | `nodes/molecule.parquet.id`; current cache has 22,230 rows with non-empty `smiles`. | Accept as an immediate build candidate after parameter/invalid-SMILES policy is fixed. |

## Recommended feature contract: `gene_genomic_sequence`

Prefer the explicit table name `gene_genomic_sequence` over `gene_sequence`. If a generic `gene_sequence` name is required by downstream code, it should still carry `sequence_kind=genomic_locus` and should not include promoter or transcript-derived sequences.

Required columns:

| column | meaning |
|---|---|
| `feature_key` | Stable key: `gene_genomic_sequence|node_id|source|source_dataset|source_record_id|reference_build|sequence_kind`. |
| `feature_table` | `gene_genomic_sequence`. |
| `node_id` | KG gene node id from `nodes/gene.parquet.id`. |
| `node_type` | `gene`. |
| `sequence_kind` | `genomic_locus`. |
| `sequence` | Uppercase DNA sequence extracted from reference FASTA; no whitespace. |
| `length` | Sequence length in bases after extraction. |
| `alphabet` | `dna_iupac`. |
| `chromosome` | Source chromosome/contig name normalized to reference FASTA naming. |
| `start_1based` | Inclusive 1-based coordinate from source annotation. |
| `end_1based` | Inclusive 1-based coordinate from source annotation. |
| `strand` | `+` or `-`; sequence should be emitted in gene strand orientation if reverse-complement policy is accepted. |
| `reference_build` | `GRCh38` plus assembly/accession detail when available. |
| `source` | `Ensembl` or `GENCODE`; choose one per build. |
| `source_dataset` | Exact GTF/GFF3 dataset and reference FASTA dataset. |
| `source_record_id` | Stable source gene ID, e.g. ENSG without version plus version in metadata if available. |
| `source_release` | Exact source release/version/date. |
| `provenance` | Local/remote paths, FASTA checksum, coordinate extraction command/version. |
| `license` | EMBL-EBI/GENCODE/reference genome attribution terms as applicable. |
| `citation` | Source citation/attribution. |
| `created_at` | Build timestamp. |
| `checksum_sha256` | SHA-256 of emitted uppercase sequence. |

Validation/policy requirements:

- Endpoint anti-join against gene node IDs must be zero for emitted rows.
- Source coordinate table must be audited before extraction because current cached gene nodes do not contain genomic coordinates.
- Coordinate system conversion must be explicit: source GTF/GFF uses 1-based inclusive coordinates; FASTA extraction tooling often uses 0-based half-open intervals.
- Strand policy must be fixed before build. Recommendation: emit sequence in source gene strand orientation and record original `strand`; for `-` strand genes, reverse-complement the reference interval.
- Default maximum length should be set before staging. The old sequence pilot used a 100,000 max sequence policy; full gene loci can exceed this by a lot. Recommended first build: coordinates-only for all mapped genes plus raw sequence only for loci <= 500,000 bp, or defer long sequences with explicit rejected/overlength counts. Do not silently truncate.
- Alternative contigs, patches, PAR/haplotype loci, readthrough genes, and versioned ENSG IDs must be reported separately.
- Release mismatch against existing protein/transcript sequence features is allowed only if documented in the source matrix and builder report.

## Recommended feature contract: `molecule_fingerprint`

The correct source is the molecule node chemical structure field, not external text descriptions. The current local `molecule.parquet` exposes `smiles` for 22,230/31,007 molecules and `inchikey` for the same count. Treat this as the input SMILES field unless a future builder proves a separate canonical SMILES source is present.

Recommended representation: one row per molecule per fingerprint parameter set, using sparse on-bit indices for readability/interoperability plus an optional packed bit-vector checksum. Sparse indices avoid byte-order ambiguity and are stable in JSON/Parquet. A later performance-oriented build can add packed bytes if needed, but the source contract should still record RDKit parameters.

Required columns:

| column | meaning |
|---|---|
| `feature_key` | Stable key: `molecule_fingerprint|node_id|source|source_dataset|source_record_id|fingerprint_kind|radius|n_bits|use_chirality`. |
| `feature_table` | `molecule_fingerprint`. |
| `node_id` | KG molecule node id from `nodes/molecule.parquet.id`. |
| `node_type` | `molecule`. |
| `fingerprint_kind` | `morgan_binary` / ECFP-like Morgan bit fingerprint. |
| `fingerprint_format` | Recommended first format: `sparse_on_bits_uint16_list`; optional later packed format: `bit_vector_little_endian_base64` with explicit byte order. |
| `on_bits` | Sorted list of on-bit indices, each `0 <= bit < n_bits`; Parquet list<uint16/int32>. |
| `n_bits` | Recommended: `2048`. |
| `radius` | Recommended: `2` (ECFP4-like). |
| `use_chirality` | Recommended: `true`, because drug stereochemistry matters. |
| `use_bond_types` | `true` unless builder proves a reason otherwise. |
| `input_smiles` | Input string from molecule node `smiles` or a recorded canonical source field. |
| `canonical_smiles_rdkit` | RDKit canonical SMILES after parsing/sanitization. |
| `input_smiles_field` | `nodes/molecule.parquet.smiles` for the current cache unless a future source provides `canonical_smiles`. |
| `inchikey` | Existing molecule node InChIKey when present; useful for audit only, not the feature key. |
| `source` | `ChEMBL/OpenTargets molecule node metadata` or more specific source once confirmed. |
| `source_dataset` | Exact KG molecule node/source release or upstream ChEMBL/OpenTargets drug molecule dataset. |
| `source_record_id` | Molecule node id and/or upstream ChEMBL/DrugBank ID used for the structure. |
| `source_release` | KG/source release used to read molecule nodes. |
| `rdkit_version` | Exact RDKit version used to parse/canonicalize/fingerprint. |
| `invalid_smiles_policy` | `skip_with_report`; no placeholder fingerprint rows. |
| `salt_mixture_policy` | See policy below. |
| `provenance` | Node path, source release, builder command, and structure-field provenance. |
| `license` | ChEMBL/OpenTargets terms captured from source policy. |
| `citation` | ChEMBL/OpenTargets citation/attribution. |
| `created_at` | Build timestamp. |
| `fingerprint_sha256` | Hash of deterministic serialized sparse indices and parameters. |

Recommended RDKit parameters/policies:

- Use RDKit Morgan fingerprint as bit vector: radius 2, nBits 2048, `useChirality=True`, `useBondTypes=True`. Record whether legacy `GetMorganFingerprintAsBitVect` or newer `rdFingerprintGenerator.GetMorganGenerator` was used.
- Parse and sanitize SMILES with RDKit. Invalid/unparseable SMILES are skipped and counted in a builder report; they must not emit all-zero placeholders.
- Canonicalize parsed molecules with RDKit and store `canonical_smiles_rdkit` for reproducibility. Do not overwrite node source fields in this feature build.
- Salts/mixtures: recommended first build does not fragment-strip or choose largest component silently. Fingerprint the parsed molecule represented by the input SMILES as-is, record `component_count`, and flag multi-component rows. A separate salt-stripping feature variant can be added later only if explicitly named and parameterized.
- Molecule rows without SMILES are skipped and counted as `missing_structure`.
- Protein/biologic drugs with peptide/protein-like descriptions but no valid small-molecule SMILES should not receive fabricated fingerprints.

## Risks and open questions

### `gene_genomic_sequence`

- Current gene node IDs appear NCBI-like (`NCBI:*`) in the local cache; source gene coordinates are likely ENSG-based. A reliable NCBI/HGNC/Ensembl mapping is a prerequisite.
- Full gene loci are storage-heavy and include introns; this may be less model-useful than promoter/TSS windows or transcript-derived features. Name the table according to the biology chosen.
- Reference assembly and coordinate release mismatch can create hard-to-debug sequence differences. Builder reports must include FASTA checksum and annotation release.
- A coordinates-only table may be the best first deliverable if the model stack is not ready for very long genomic strings.

### `molecule_fingerprint`

- The local field is named `smiles`, not `canonical_smiles`; the builder should not assume canonicality without RDKit recanonicalization.
- RDKit version and generator API changes can affect reproducibility; record version and parameters in every row/report.
- Salts, mixtures, disconnected components, stereochemistry, and invalid SMILES must be visible in report counts.
- ChEMBL/OpenTargets licensing/attribution should mirror the existing molecule textual-summary source policy.

## Build-card recommendations

Immediate candidate if accepted by reviewer:

1. Build `molecule_fingerprint` from `nodes/molecule.parquet.smiles` using deterministic RDKit Morgan radius 2 / 2048-bit / chirality-aware sparse on-bit indices. Stage only; report counts for rows emitted, missing SMILES, invalid SMILES, multi-component structures, and endpoint anti-join.

Conditional precursor candidate:

2. Build `gene_coordinates` / `gene_genomic_interval` source-mapping audit from Ensembl or GENCODE annotation to current KG gene nodes. This should produce a mapping/coverage report and optionally a coordinates-only feature table. Do this before raw `gene_genomic_sequence` extraction.

Defer until precursor is accepted:

3. Build `gene_genomic_sequence` from accepted coordinates + GRCh38 FASTA with explicit length and strand policy. Do not call promoter windows or transcript-derived cDNA `gene_sequence`.

## Explicit non-goals

- No biological `edges/` writes.
- No biological `evidence/` writes.
- No canonical `kg/v2/features/` promotion.
- No ReMap dependency.
- No use of transcript sequence as `gene_sequence` unless the feature name explicitly states transcript-derived semantics.
- No fabricated all-zero molecule fingerprints for missing/invalid structures.
