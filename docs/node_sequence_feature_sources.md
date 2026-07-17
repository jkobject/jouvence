# Node sequence feature sources (staged pilot)

Producer task for this audit/gate: `t_b5dd2399`  
Predecessor/staging lineage: staged artifact paths retain the original `t_f9ef6389` prefix from the earlier pilot run; this document is the auditable source-decision handoff for `t_b5dd2399` review/closure.  
Scope: conservative staged sequence features only; no canonical KG writes and no canonical feature promotion authorized by this document/review.

## Common feature contract

Sequence features live under `features/` and are model features, not graph assertions.

Required columns used by `manage_db.kg_sequence_features`:

| column | meaning |
|---|---|
| `feature_key` | stable key: `feature_table|node_id|source|source_record_id|sequence_kind` |
| `feature_table` | table name, e.g. `protein_sequence` |
| `node_id` | canonical KG node id from matching `nodes/<node_type>.parquet` |
| `node_type` | KG node type |
| `sequence_kind` | `amino_acid`, `cdna`, etc. |
| `sequence` | uppercase sequence payload, no whitespace |
| `length` | sequence length in residues/bases |
| `alphabet` | validated alphabet label, currently `protein_iupac` or `dna_iupac` |
| `source` | source system |
| `source_dataset` | exact source dataset/file type |
| `source_record_id` | stable source record id after version normalization where applicable |
| `source_release` | release/version/date |
| `provenance` | source path/URL/header extraction detail |
| `license` | source license/terms label |
| `citation` | required attribution/citation |
| `created_at` | build timestamp |
| `checksum_sha256` | SHA-256 checksum of uppercase sequence |

Validation policy:

- table-specific node type and sequence kind checks;
- endpoint anti-join against corresponding node IDs;
- non-empty sequences;
- strict alphabet validation (`*` stop-containing protein records are rejected for this pilot);
- default max sequence length: 100,000;
- duplicate policy: drop duplicate `(feature_table, node_id, source, source_dataset, source_record_id, sequence_kind)`, keep last;
- source/license policy report emitted to `reports/sequence_source_policy.csv`.

## Source decision matrix

| node_type | feature_table | sequence type | source | release used/recommended | license/terms | ID mapping | expected columns | risks | recommendation |
|---|---|---|---|---|---|---|---|---|---|
| `protein` | `protein_sequence` | amino-acid sequence | Ensembl human protein FASTA (`pep.all`) | pilot used Ensembl release 114, GRCh38 FASTA last-modified 2025-02-02 | EMBL-EBI open data / attribution | FASTA record token `ENSP...version` -> strip version -> `nodes/protein.parquet.id` | common contract above | Ensembl has peptide records with stop codons/fragments; unmapped records reflect KG/source release mismatch; UniProt accession mapping can be added later | acceptable staged candidate source pending separate canonical promotion task/gate; keep Ensembl ENSP mapping as the first conservative staged table |
| `transcript` | `transcript_sequence` | transcript cDNA sequence | Ensembl human cDNA FASTA (`cdna.all`) | pilot used Ensembl release 114, GRCh38 FASTA last-modified 2025-02-02 | EMBL-EBI open data / attribution | FASTA record token `ENST...version` -> strip version -> `nodes/transcript.parquet.id` | common contract above | very long transcripts can stress models/storage; release mismatch creates unmapped records | acceptable staged candidate source pending separate canonical promotion task/gate, with max-length policy documented; excluded >100k rows in pilot |
| `protein` | optional future `protein_uniprot_sequence` or replacement source | amino-acid sequence | UniProtKB canonical/isoform FASTA or REST | not used in this pilot | CC BY 4.0 | UniProt accession -> `nodes/protein.parquet.uniprot_id`; ambiguity if one UniProt maps to multiple ENSP IDs | common contract plus mapping evidence | requires careful canonical-vs-isoform and one-to-many policy | defer until a separate source policy gate decides whether Ensembl or UniProt should be used for canonical features |
| `gene` | deferred | genomic locus sequence | Ensembl/GENCODE gene coordinates + GRCh38 reference FASTA | not built | EMBL-EBI/GENCODE/reference genome attribution | ENSG coordinates -> reference FASTA interval | common contract plus coordinates | sequences are large/ambiguous; strand/promoter/intron policy needed | defer; prefer coordinates/context policy before full sequence table |
| `enhancer` | deferred | genomic interval sequence | enhancer coordinates + GRCh38 reference FASTA | not built | depends on enhancer source + reference genome attribution | enhancer interval -> reference FASTA interval | common contract plus `chrom/start/end/strand/reference_build` | requires reviewed enhancer coordinate provenance and interval normalization | defer until enhancer source promotion/policy is accepted |
| `mutation` | deferred | local allele/ref/alt context | reviewed variant source + reference FASTA | not built | source-dependent | variant coordinates/ref/alt -> reference window | common contract plus variant context columns | mutation sources/coordinate build not fully promoted; avoid fabricating allele context | defer |
| `miRNA` | deferred | mature/precursor RNA/DNA sequence | miRBase mature/precursor FASTA | not built | exact redistribution terms and node mapping need review | miRBase IDs/accessions -> staged/canonical miRNA nodes | common contract | miRNA nodes and mature-vs-precursor policy need confirmation | defer until node IDs and terms are reviewed |
| `lncRNA` | deferred | transcript cDNA | GENCODE/Ensembl transcript FASTA | not built separately | EMBL-EBI/GENCODE attribution | ENST IDs -> lncRNA node IDs if available | common contract | requires staged lncRNA node mapping and biotype policy | defer unless lncRNA nodes are promoted and mapped to ENST |

## Pilot staged outputs

Local staging prefix:

- `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/features/protein_sequence.parquet`
- `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/features/transcript_sequence.parquet`
- `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/reports/sequence_feature_report.json`
- `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/reports/sequence_source_policy.csv`
- source FASTA cache/checksums under `.omoc/staging/node-sequence-features-20260622-t_f9ef6389/source_cache/`

Remote staging target:

- `gs://jouvencekb/kg/staging/node-sequence-features-20260622-t_f9ef6389/`

Canonical promotion status:

- No canonical promotion is authorized by this document/review.
- Reviewer should inspect counts, unmapped source records, invalid/overlength exclusions, and decide only whether Ensembl release 114 is an acceptable staged candidate source pending a separate canonical promotion task/gate.
- If a later gate accepts promotion, that separate task should promote to `features/protein_sequence.parquet` and `features/transcript_sequence.parquet`, not as KG nodes/edges.
