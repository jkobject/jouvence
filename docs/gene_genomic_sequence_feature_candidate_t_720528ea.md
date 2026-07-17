# Gene genomic sequence feature candidate for NT embeddings

Task: `t_720528ea`  
Status: staged candidate / review-required; no canonical `kg/v2/features/` write.  
Local workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`

## Source/build decision

Use Ensembl release 114 gene coordinates from `Homo_sapiens.GRCh38.114.gtf.gz` and the matching Ensembl GRCh38 primary assembly reference FASTA `Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz`.

Downloaded source cache:

- `artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.114.gtf.gz`
  - SHA256: `75ec5b7a1bbb8ce566622dd9abf974ad37d390130325dae6d197d1a590854c50`
  - FTP last-modified observed by HTTP HEAD: 2025-01-27
- `artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz`
  - SHA256: `d8c3af0094a7bba6125763bad779ec18a81483c739c6ed122094bdf86c187b92`
  - FTP last-modified observed by HTTP HEAD: 2025-01-30

Source release label recorded in rows/reports:

`Ensembl release 114 / GRCh38 primary assembly FASTA last-modified 2025-01-30 / GTF last-modified 2025-01-27`

## Semantics

Two separate feature tables are produced:

1. `gene_genomic_interval`
   - Coordinates-only companion table.
   - One row per mapped Ensembl gene locus from the GTF.
   - Coordinates are GTF 1-based inclusive.
   - Carries chromosome, start, end, strand, reference build, Ensembl gene version, gene name/biotype, source/provenance/license/citation, and a coordinate hash.

2. `gene_genomic_sequence`
   - Full reference genomic gene locus sequence, including introns.
   - This is not a transcript/cDNA proxy and is not promoter/TSS sequence.
   - For `-` strand genes, the emitted sequence is reverse-complemented into gene-strand orientation while preserving the original `strand` field.
   - `sequence_kind=genomic_locus`; alphabet is DNA IUPAC (`ACGTRYSWKMBDHVN`).
   - No truncation: loci longer than `max_sequence_length=500000` are skipped from the sequence table and remain represented in `gene_genomic_interval`.

Promoter/TSS windows and canonical-transcript-derived gene sequences remain separate modalities and should not be folded into this table.

## Staged artifacts

Local:

- `artifacts/staged/t_720528ea/full/features/gene_genomic_interval.parquet`
- `artifacts/staged/t_720528ea/full/features/gene_genomic_sequence.parquet`
- `artifacts/staged/t_720528ea/full/reports/gene_genomic_sequence_feature_report.json`
- `artifacts/staged/t_720528ea/full/reports/full_build_stdout.json`

GCS staging mirror for review:

- `gs://jouvencekb/kg/staging/gene-genomic-sequence-20260625-t_720528ea/features/gene_genomic_interval.parquet`
- `gs://jouvencekb/kg/staging/gene-genomic-sequence-20260625-t_720528ea/features/gene_genomic_sequence.parquet`
- `gs://jouvencekb/kg/staging/gene-genomic-sequence-20260625-t_720528ea/reports/gene_genomic_sequence_feature_report.json`
- `gs://jouvencekb/kg/staging/gene-genomic-sequence-20260625-t_720528ea/reports/full_build_stdout.json`

Remote object size check: 4 objects, 606,915,753 bytes / 578.80 MiB.

## Build results

Full candidate report:

- Endpoint gene nodes in canonical KG: 267,830
- GTF gene rows seen: 78,894
- GTF rows mapped to canonical gene endpoints: 78,644
- GTF rows unmapped to endpoints: 5
- Alt/patch/MT-like contig rows skipped by policy: 245
- Interval rows written: 78,644
- Interval unique nodes: 78,644
- Interval endpoint anti-join rows: 0
- Sequence rows written: 78,164
- Sequence unique nodes: 78,164
- Sequence endpoint anti-join rows: 0
- Sequence rows skipped over 500 kb: 480
- Sequence rows skipped for invalid alphabet: 0
- Sequence rows skipped for missing FASTA contig: 0
- Total emitted sequence bases: 2,092,341,363

Length distributions:

- Interval length min/p50/p90/p95/p99/max: 8 / 4,603 / 79,805.2 / 141,792.35 / 393,857.58 / 2,473,539
- Sequence length min/p50/p90/p95/p99/max: 8 / 4,480 / 75,587.7 / 130,228.4 / 304,848.74 / 499,324

Top interval biotypes include:

- lncRNA: 34,877
- protein_coding: 20,083
- processed_pseudogene: 9,486
- misc_RNA: 2,207
- snRNA: 1,901
- miRNA: 1,879
- unprocessed_pseudogene: 1,953

## Validation commands run

```bash
uv run python -m py_compile manage_db/build_gene_genomic_sequence_features.py manage_db/kg_sequence_features.py manage_db/build_sequence_features.py
uv run --group dev pytest tests/test_gene_genomic_sequence_features.py tests/test_kg_sequence_features.py -q
uv run python -m manage_db.build_gene_genomic_sequence_features --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 --output-root artifacts/staged/t_720528ea/bounded --gtf artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.114.gtf.gz --fasta artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz --source-release 'Ensembl release 114 / GRCh38 primary assembly FASTA last-modified 2025-01-30 / GTF last-modified 2025-01-27' --reference-build GRCh38.primary_assembly --max-sequence-length 500000 --limit-rows 50
uv run python -m manage_db.build_gene_genomic_sequence_features --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 --output-root artifacts/staged/t_720528ea/full --gtf artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.114.gtf.gz --fasta artifacts/cache/t_720528ea/source/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz --source-release 'Ensembl release 114 / GRCh38 primary assembly FASTA last-modified 2025-01-30 / GTF last-modified 2025-01-27' --reference-build GRCh38.primary_assembly --max-sequence-length 500000
```

Independent validation after the full build checked:

- Parquet metadata rows/schema for both output tables.
- Duplicate `feature_key` count: 0 for intervals and sequence rows.
- Endpoint anti-join against canonical `nodes/gene.parquet`: 0 for both tables.
- `length == len(sequence)`: 0 mismatches.
- SHA256 recomputation on first 1,000 sequences: 0 mismatches.
- DNA alphabet regex violations: 0.
- Confirmed canonical absences: no `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/features/gene_genomic_sequence.parquet` and no `.../gene_sequence.parquet` were written.

Focused test output: `6 passed in 0.86s`.

## NT embedding recommendation

Do not embed raw full gene loci as a single default NT input without a model/window policy. Even after skipping >500 kb loci, the staged table contains ~2.09B bases and p99 sequence length is ~305 kb; many Nucleotide Transformer checkpoints require much shorter contexts and would need explicit windowing/stride/pooling metadata.

Recommended next reviewed modalities:

1. Promote or accept `gene_genomic_interval` as the coordinate/source precursor if reviewers approve source/build policy.
2. For NT embeddings, add a separate `gene_genomic_sequence_embedding` pilot that windows `gene_genomic_sequence` with explicit `window_size`, `stride`, and `pooling=mean_window_means` or model-specific pooling; record skipped/overlength accounting.
3. Add a separate `gene_promoter_sequence`/TSS-window feature only after a canonical TSS/canonical-transcript/window policy is accepted. This is likely the more practical first NT gene modality for regulatory modeling.
4. Keep existing gene text embeddings separate; do not replace gene text with transcript-derived or raw-locus embeddings.

## Residual risks / reviewer focus

- Current canonical `nodes/gene.parquet` contains mixed source IDs; this candidate maps only Ensembl `ENSG` genes from Ensembl release 114 GTF. NCBI-only and other non-Ensembl gene rows remain uncovered.
- Five Ensembl release 114 GTF primary-contig gene IDs did not map to current canonical gene endpoints; reviewers should inspect whether this is acceptable release drift.
- 245 GTF rows on alt/patch/MT-like contigs are excluded by current policy. This keeps the first candidate primary-assembly-focused but should be explicitly accepted or revised.
- The 500 kb max sequence cap avoids silent truncation but skips 480 mapped loci from `gene_genomic_sequence`; those loci remain in `gene_genomic_interval`.
- GCS upload used `gcloud storage` parallel composite upload for the large sequence object; `gcloud` can verify crc32c, but downstream clients should prefer crc32c-aware download/verification.
