# ReMap + motif support audit for `tf_binds_enhancer`

_Date: 2026-06-21_
_Status: source audit only; do not ingest from this note directly._

## Goal

Define a source-native first builder plan for `tf_binds_enhancer` using ReMap observed TF/regulator ChIP peaks, with JASPAR/HOCOMOCO motif scans as supporting or predicted evidence only.

This proposal deliberately does not define or populate `tf_regulates_gene`. A TF-bound enhancer is a binding observation at a regulatory interval. It is not, by itself, a directional TF-to-target-gene regulation claim.

## Recommended source choice

Use ReMap 2022 human hg38 as the first observed-binding source for `tf_binds_enhancer`.

Preferred staged inputs:

1. Observed peak rows, provenance-preserving:
   - `https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_all_macs2_hg38_v1_0.bed.gz`
   - ReMap 2022, Homo sapiens, GRCh38/hg38, MACS2 peaks.
   - Sample row observed during audit:
     `chr1 9829 10459 GSE137250.SMARCA4.HeLa 34.47676 . 10084 10085 224,84,252`
   - BED9-like fields: `chrom`, `start`, `end`, `name`, `score`, `strand`, `thickStart`, `thickEnd`, `itemRgb`.
   - `name` decomposes as `source_accession.TF.biotype` for the all file, e.g. `ENCSR387QUV.RELB.GM12878` or `GSE137250.SMARCA4.HeLa`.
   - `score` is a peak score from the MACS2/ReMap peak file; preserve as numeric source score, not as graph confidence without calibration.
2. Deduplicated/context-collapsed QC/helper input:
   - `https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_nr_macs2_hg38_v1_0.bed.gz`
   - Sample row: `chr1 9829 10459 SMARCA4:HeLa 1 . 10084 10085 224,84,252`.
   - This is useful for deduplicated interval/TF support, but it collapses original experiment accession in the BED `name`; do not use it as the only evidence source if source accession is needed.
3. Regulatory-region support / CRM helper input:
   - `https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_crm_macs2_hg38_v1_0.bed.gz`
   - Sample row has `name` as comma-separated regulators and `score` as count/support, e.g. many TF names over one interval.
   - Use as a candidate regulatory-region support table, not as row-level observed TF evidence unless decomposed back to TF-level evidence with care.
4. Biotype/cell context metadata:
   - `https://remap.univ-amu.fr/storage/remap2022/biotypes/remap2022_hsap_biotypes.xlsx`
   - The page states ReMap BED files are available by transcriptional regulator, biotype, or entire catalog. For human, GRCh38/hg38 is the supported assembly; files can be lifted to hg19.
   - XLSX fields observed during audit include: `biotype`, `description`, aliases, `BTO_id`, `EFO_id`, `cellosaurus_accession`, `Category`, `Disease`, `Sex_gender_of_cell`, `Age_of_donor`, `web_link`, `bed_url`, `peaks/0/biotype_NR`, `peaks/0/biotype_all`.

Default: stage from `all` for evidence because it preserves source experiment accession in `name`, then compute graph-edge deduplication separately. Use `nr` or `crm` only as secondary support/QC summaries.

## ReMap source semantics

ReMap is observed binding evidence from curated/remapped regulatory ChIP-seq-like experiments for transcriptional regulators. It can support `tf_binds_enhancer` after these gates pass:

- organism is human;
- genome build is harmonized to the enhancer node coordinate build;
- TF/regulator token maps to a KG TF/gene node;
- peak interval overlaps an accepted KG enhancer/regulatory interval node;
- source context and score are retained in evidence;
- the graph assertion remains TF binds enhancer, not TF regulates gene.

ReMap rows should create at most one active graph assertion per `(TF gene, enhancer node, relation)` after evidence aggregation. Multiple ReMap experiments, cell types, or scores become multiple evidence rows supporting the same graph edge.

## TF endpoint mapping

Graph endpoint policy:

- `x`: canonical KG `gene` node for the TF/regulator, preferably Ensembl `ENSG`.
- `y`: canonical KG `enhancer` node.

Mapping plan for ReMap TF symbols:

1. Parse ReMap `name`:
   - `all`: split from the right into `source_accession`, `tf_symbol`, `biotype`. ReMap accessions can be ENCODE-style (`ENCSR...`) or GEO-style (`GSE...`). Avoid naïve split assumptions if a biotype contains dots; implement robust parsing against known TF symbols / biotype list.
   - `nr`: split `tf_symbol:biotype`.
   - `crm`: split comma-separated TF symbols from `name`, but treat as CRM support rather than primary evidence.
2. Normalize TF symbol with the KG gene node/xref table:
   - exact approved HGNC symbol → Ensembl gene ID;
   - aliases/synonyms only if unambiguous;
   - reject or quarantine rows with multiple possible Ensembl genes, withdrawn symbols, histone marks, cofactors that are not TF/regulator gene products under the approved relation policy, or non-human symbols.
3. Preserve original source identifiers in evidence:
   - `source_tf_symbol` as in ReMap;
   - normalized `tf_gene_id` (`ENSG...`);
   - optional `tf_hgnc_id`, `tf_entrez_id`, `tf_uniprot_id` if available from local gene/xref mapping, but do not switch graph endpoint to protein unless a future schema explicitly does so.

This avoids projecting protein-level claims while still representing the TF gene product with the existing KG `gene` endpoint policy for `tf_binds_enhancer`.

## Enhancer endpoint and interval mapping

Current local enhancer nodes are built from OpenTargets `enhancer_to_gene` rows. The existing ingestion uses key columns `intervalId`, `geneId`, `biosampleId`, `biosampleName`, `chromosome`, `start`, `end`, `score`, `datasourceId`, `pmid`; enhancer node IDs are `intervalId`, with coordinates retained from `chromosome/start/end`.

Intersection policy:

1. Determine the enhancer node coordinate build before any ReMap overlap.
   - ReMap preferred input is hg38/GRCh38.
   - If enhancer nodes are hg38, do not liftover ReMap.
   - If enhancer nodes are hg19 or mixed, liftover the smaller side into a single build first and record both original and harmonized coordinates. Do not silently intersect mixed builds.
2. Normalize coordinate conventions.
   - Treat ReMap BED as 0-based half-open intervals.
   - Confirm the enhancer source convention; if OpenTargets `intervalId` encodes coordinates, parse and verify against stored `chromosome/start/end`.
3. Overlap threshold default.
   - Require same chromosome and at least 1 bp overlap for candidate evidence.
   - For active graph edges, recommend `peak summit within enhancer interval` OR `reciprocal overlap >= 0.10` OR `overlap_bp >= 50`, whichever passes first.
   - Store `overlap_bp`, `peak_fraction_overlap`, `enhancer_fraction_overlap`, and `summit_within_enhancer` in evidence so the threshold can be tightened later without rebuilding raw intersections.
4. Promoter/regulatory interval policy.
   - Only attach to nodes present in the accepted enhancer/regulatory interval catalog.
   - Do not create new enhancer nodes from ReMap peaks in this first builder.
   - Do not mix promoter-only intervals unless the enhancer catalog explicitly includes promoter-like regulatory intervals and the relation wording is approved to cover them.
5. Context preservation.
   - ReMap biotype/cell line context is evidence context.
   - KG enhancer nodes may have biosample context from rE2G/ABC-like sources; the binding edge can be context-specific in evidence even if the graph assertion is deduplicated.
   - Add context-compatibility fields when ReMap biotype can map to a KG tissue/cell/cell-line/biosample node, but do not require exact context match for interval overlap in the first pass. Exact context match can be a higher-confidence flag.

## Motif support integration

Motifs are predicted binding potential. They are not observed binding and not regulation.

Recommended motif sources:

1. JASPAR 2026 CORE vertebrates/human motifs.
   - Downloads page exposes JASPAR 2026 CORE PFM/MEME/TRANSFAC files and hg38 genome-wide bigBed tracks.
   - Useful files:
     - `https://jaspar.elixir.no/download/data/2026/CORE/JASPAR2026_CORE_non-redundant_pfms_meme.txt`
     - `https://jaspar.elixir.no/download/data/2026/CORE/JASPAR2026_CORE_non-redundant_pfms_jaspar.txt`
     - `https://mencius.uio.no/JASPAR/JASPAR_metadata/2026/ultimate_metadata_table_CORE.tsv`
     - `https://mencius.uio.no/JASPAR/JASPAR_familial_binding_sites/2026/hg38/JASPAR2026_hg38.bb`
   - Metadata fields observed: `collection`, `tax_group`, `matrix_id`, `base_id`, `version`, `name`, `class`, `family`, `uniprot_ids`, `validation`, `comment`, `source`, `type`, `tax_id`, `species`.
2. HOCOMOCO v12 human/mouse motifs.
   - Downloads page exposes H12CORE/H12INVIVO/H12INVITRO/H12RSNP motif bundles, annotation JSONL, thresholds, and formatted MEME/JASPAR/HOMER files.
   - Useful files:
     - `https://hocomoco12.autosome.org/final_bundle/hocomoco12/tf_masterlist.tsv`
     - `https://hocomoco12.autosome.org/final_bundle/hocomoco12/H12CORE/H12CORE_annotation.jsonl`
     - `https://hocomoco12.autosome.org/final_bundle/hocomoco12/H12CORE/formatted_motifs/H12CORE_meme_format.meme`
     - `https://hocomoco12.autosome.org/final_bundle/hocomoco12/H12CORE/H12CORE_thresholds.tar.gz`
   - Metadata fields observed in annotation JSONL include `name`, `tf`, `collection`, `datatype`, `quality`, `length`, consensus/GC/information-content metrics, `standard_thresholds`, and `masterlist_info` with gene symbol, UniProt, HGNC, Entrez, TFClass.

Motif evidence policy:

- Motif-only overlap with an enhancer should not create an active `tf_binds_enhancer` graph edge.
- Motif scan hits should be stored as `evidence_type=motif_support` or as an enhancer/TF candidate feature table.
- When a ReMap observed peak for the same TF overlaps the same enhancer and a motif hit for that TF also overlaps the peak/enhancer interval, the motif strengthens the ReMap evidence.
- The strengthened edge still owes its active graph status to `observed_binding`, not motif alone.
- Motif evidence has no biosample context unless provided by an external scan context. It can be context-compatible only through the ReMap peak or a chromatin/accessibility source, not by itself.

Motif intersection policy:

1. Scan or consume hg38 motif tracks against accepted enhancer intervals only.
2. Map motif TF names/UniProt/HGNC to the same canonical TF gene ID policy used for ReMap.
3. A motif supports a ReMap evidence row if:
   - same canonical TF gene ID;
   - same enhancer node;
   - motif hit overlaps the ReMap peak by at least 1 bp, or motif center lies inside the ReMap peak;
   - motif scan was performed on the same genome build;
   - motif threshold/source version is recorded.
4. If motif maps to a TF family rather than a unique TF gene, either store as family-level support only or quarantine until an approved family-to-gene expansion policy exists.

## Proposed evidence schema

Graph edge file, eventually:

- `x_id`: TF gene ID (`ENSG...`).
- `x_type`: `gene`.
- `y_id`: enhancer node ID (`intervalId` or accepted enhancer ID).
- `y_type`: `enhancer`.
- `relation`: `tf_binds_enhancer`.
- `display_relation`: `binds`.
- `source`: compact source label, e.g. `ReMap/remap2022` for graph edge rows.
- `credibility`: derived after evidence aggregation; do not use raw peak score directly without a documented mapping.

Evidence table, `evidence/tf_binds_enhancer.parquet`:

Required shared fields:

- `edge_key` or `x_id`, `y_id`, `relation`.
- `source_dataset`: e.g. `ReMap2022/hg38/MACS2/all`, `JASPAR2026/CORE/non-redundant`, `HOCOMOCOv12/H12CORE`.
- `source_release`: e.g. `2022`, `2026`, `v12`.
- `evidence_type`: `observed_binding` or `motif_support`.
- `predicate`: `binds_enhancer`, `motif_matches_enhancer`, or `motif_supports_observed_binding`.
- `tf_id_namespace`: `HGNC_SYMBOL`, `ENSG`, `UniProt`, `JASPAR_MATRIX`, `HOCOMOCO_MOTIF` as applicable.
- `source_tf_id`: original TF symbol/motif TF token.
- `tf_gene_id`: normalized KG TF endpoint.
- `enhancer_id`: normalized KG enhancer endpoint.
- `genome_build`: e.g. `GRCh38/hg38`.
- `chromosome`, `start`, `end`: harmonized interval coordinates for the evidence interval.
- `original_chromosome`, `original_start`, `original_end`, `original_genome_build`: raw source coordinates before liftover/harmonization.
- `source_record_id`: stable source row/accession if available.
- `original_id`: raw BED `name`, motif ID, bigBed name, or source row ID.

Observed-binding fields for ReMap:

- `remap_file`: exact URL or basename.
- `remap_peak_name`: raw BED col4.
- `remap_source_accession`: parsed ENCODE/GEO/source accession from `all` BED.
- `remap_tf_symbol`: parsed TF symbol.
- `remap_biotype`: parsed biotype/cell context.
- `biosample_name`: normalized display name.
- `biosample_id`: mapped ontology/cell-line ID if available (`EFO`, `BTO`, `Cellosaurus`, `CL`, `UBERON`, etc.).
- `biosample_category`, `disease`, `sex`, `donor_age` when available from ReMap biotypes metadata.
- `assay`: `ChIP-seq` / source-native assay if discoverable; otherwise `ReMap regulatory ChIP peak`.
- `peak_score`: numeric BED score.
- `strand`, `summit_start`, `summit_end`, `item_rgb` from BED.
- `overlap_bp`, `peak_fraction_overlap`, `enhancer_fraction_overlap`, `summit_within_enhancer`.
- `context_match_level`: `exact_biosample`, `mapped_cell_line`, `mapped_cell_type`, `mapped_tissue`, `interval_only`, or `unknown`.

Motif-support fields:

- `motif_source`: `JASPAR` or `HOCOMOCO`.
- `motif_id`: e.g. `MA0002.1` or `AHR.H12CORE.0.P.B`.
- `motif_base_id` / `motif_version` when available.
- `motif_name`, `motif_tf_symbol`, `motif_family`, `motif_class`.
- `motif_model_type`: PFM/PWM/MEME/JASPAR/HOMER/bigBed scan.
- `motif_threshold`: threshold name/value, p-value/FPR, or scan cutoff.
- `motif_score`, `motif_pvalue`, `motif_qvalue` if produced by scanner/track.
- `motif_strand`, `motif_start`, `motif_end`.
- `motif_overlaps_peak`: boolean.
- `supported_observed_evidence_id`: link to the ReMap evidence row when motif supports an observed peak; null for motif-only candidate evidence.
- `motif_only_candidate`: boolean; true rows cannot create active graph edges.

## Staged builder plan

Stage 0 — source cache/audit only:

- Download or stream headers/samples from ReMap `all`, `nr`, `crm`, and biotypes XLSX.
- Download motif metadata tables for JASPAR/HOCOMOCO.
- Record source URLs, release labels, file sizes/checksums, and sample rows in a report.

Stage 1 — ReMap observed-binding staging, no canonical promotion:

- Parse `remap2022_all_macs2_hg38_v1_0.bed.gz` into a local staging table.
- Parse `name` into `source_accession`, `tf_symbol`, `biotype`; keep raw `name`.
- Map TF symbols to KG gene IDs with explicit accepted/rejected counts.
- Map biotypes through ReMap XLSX metadata where possible.
- Intersect with existing enhancer nodes after genome-build verification.
- Write staging candidate edges and evidence under a scratch/staging root only.

Stage 2 — motif support staging:

- Select JASPAR CORE human/vertebrate and HOCOMOCO human CORE motifs.
- Either scan accepted enhancer intervals with a documented scanner/threshold or consume official hg38 motif tracks where they expose enough score/threshold metadata.
- Map motif TFs to canonical TF gene IDs.
- Join motif hits to ReMap observed-binding candidates by same TF + same enhancer + motif/peak overlap.
- Store motif-only rows as candidate/support evidence only.

Stage 3 — validation before any ingestion card:

- Endpoint anti-join: all TF endpoints exist in `nodes/gene.parquet`; all enhancer endpoints exist in `nodes/enhancer.parquet`.
- Build consistency: all ReMap/enhancer/motif coordinates in one genome build; liftover counts and failures reported if used.
- Evidence support: every active candidate edge has at least one `observed_binding` ReMap evidence row.
- Motif-only guard: zero active graph edges supported only by `motif_support`.
- Context audit: counts by ReMap biotype, mapped biosample ID type, and context match level.
- Score audit: distributions for ReMap peak scores and motif scores; no arbitrary credibility threshold without review.
- Dedup audit: number of raw ReMap rows, mapped rows, enhancer-overlap evidence rows, active unique `(TF, enhancer)` graph assertions, and evidence rows per edge.

## Recommended default decisions

- First observed source: ReMap 2022 human hg38 `all` MACS2 BED.
- Active edge requirement: at least one observed ReMap binding peak overlapping an existing enhancer node after coordinate harmonization.
- Motif support: JASPAR/HOCOMOCO hits can strengthen/annotate evidence only; motif-only remains candidate/evidence-only.
- Enhancer creation: do not create new enhancer nodes from ReMap peaks in the first builder.
- Context: preserve ReMap biotype and mapped ontology/cell-line metadata in evidence; do not flatten to global context-free truth in evidence.
- `tf_regulates_gene`: explicitly out of scope. Any future TF→gene relation must come from source-native directional regulation or from an approved context-qualified derived relation, not from this binding audit.

## Chunked staging implementation note (2026-06-22)

The first sampled builder proved the evidence semantics but a larger attempt was killed while repeatedly scanning the full 48.8M-row enhancer table. The staged implementation now streams ReMap BED rows in bounded batches, maps TF symbols per batch, then intersects only chromosome/window-specific enhancer slices. The memory bound is therefore approximately the chosen ReMap batch plus the largest enhancer slice for a genomic window, not the entire ReMap file or all enhancer nodes.

Representative review run used 20k chr22 ReMap rows with `--remap-batch-size 2000 --window-bp 10000`, producing 1,657,030 active candidate edges and 6,719,613 observed evidence rows with max 1,962 ReMap rows and 5,526 enhancer rows in a single window event. macOS `/usr/bin/time -l` reported ~6.8 GB max RSS and ~499 s wall time on the Mac mini. Smaller windows reduce enhancer rows per join but increase DuckDB setup/scan events; larger batches reduce source parsing overhead but raise pandas peak memory.

Full or chromosome-specific staging command shape:

```bash
uv run python .omoc/scripts/stage_remap_tf_binds_enhancer.py \
  --kg-root .omoc/gcs-cache/kg-v2 \
  --stage-root .omoc/staging/remap-tf-binds-enhancer-<run-id> \
  --max-remap-rows 0 \
  --remap-batch-size 2000 \
  --window-bp 10000 \
  --chromosomes 1,2,3 \
  --force
```

Omit `--chromosomes` for all chromosomes. Keep staged outputs remote under `gs://jouvencekb/kg/staging/source-native-expansion/remap-tf-binds-enhancer-chunked/` for review; do not promote canonical KG files from this proposal/build step.

## Compact feature-first redesign note (2026-06-22)

The first all-chromosome attempt was manually stopped because chr1 alone produced ~13 GiB / 213 local files before any finalization. The unsafe pattern was not the chromosome/window join itself; it was materializing one observed-evidence row per active ReMap peak × enhancer overlap in local `_chunks/evidence/*.parquet` before final aggregation.

Replacement prototype: `.omoc/scripts/stage_remap_tf_binds_enhancer_compact.py` keeps the accepted source-native semantics but changes the physical plan:

1. Stream ReMap rows in bounded batches and partition by chromosome/window as before.
2. For each window, join ReMap peaks to only the matching enhancer coordinate slice in DuckDB.
3. Immediately aggregate active overlaps to compact `(TF gene, enhancer, chromosome/window)` support features: observed binding count, distinct ReMap peak count, source-accession/biosample support summaries, max peak score, max overlap, summit support count.
4. Write only compact support shards under `_compact_chunks/support/`; do **not** write raw per-overlap observed evidence chunks.
5. Finalize directly from compact support shards to compact edge/evidence Parquets. Edge rows remain one active `tf_binds_enhancer` assertion per `(TF, enhancer)`. Evidence rows are compact observed-binding aggregate rows keyed by `ReMap2022:compact:<md5(edge_key)>`, with aggregate support metadata in `text_span` and `supporting_observed_evidence_count` on the edge.
6. Enforce `--max-stage-gib`; the builder aborts as soon as the local stage root exceeds the configured budget. Report records `max_stage_bytes_observed`, `max_stage_bytes_allowed`, `max_rss_bytes_observed`, and `raw_observed_evidence_rows_materialized=0`.

Prototype command used for the reviewed chr22 20k comparison:

```bash
/usr/bin/time -l uv run python .omoc/scripts/stage_remap_tf_binds_enhancer_compact.py \
  --kg-root .omoc/gcs-cache/kg-v2 \
  --stage-root .omoc/staging/remap-tf-binds-enhancer-compact-20260622-chr22-20k-t_4f108a31 \
  --remap-bed .omoc/staging/remap-tf-binds-enhancer-20260622-chr22/source_cache/remap2022_chr22_hg38.bed \
  --max-remap-rows 20000 \
  --remap-batch-size 2000 \
  --window-bp 10000 \
  --chromosomes 22 \
  --max-stage-gib 1 \
  --force
```

Observed prototype result for the same accepted chr22 20k slice:

- active overlap rows before aggregation: 6,719,613 (same raw support scale as accepted run);
- compact support chunks: 38 files / ~81 MiB;
- final active edges: 1,657,030;
- final compact evidence rows: 1,657,030, all `observed_binding`;
- raw observed evidence rows materialized locally: 0;
- peak local stage size before cleanup: 304,815,860 bytes (~291 MiB), below the 1 GiB guard;
- `/usr/bin/time -l`: 19.47 s wall, 3,384,934,400 byte max RSS;
- endpoint anti-joins: TF 0, enhancer 0;
- duplicate active edges: 0;
- duplicate `(source_record_id, edge_key)`: 0;
- active edges without observed binding: 0;
- `tf_regulates_gene` edge/evidence rows: 0.

Remote review prefix:

`gs://jouvencekb/kg/staging/source-native-expansion/remap-tf-binds-enhancer-compact/chr22-20k-compact-t_4f108a31/`

After remote byte parity verification, local large duplicates (`edges/`, `evidence/`, `_compact_chunks/`, `source_cache/`) were pruned; only the small manifest, validation report, remote listing, time output, and verification JSON are kept locally.

Full-run recommendation: do not resume the old all-chromosome wrapper. If this compact plan is accepted, run one chromosome at a time with `--max-remap-rows 0`, `--remap-batch-size 2000`, `--window-bp 10000`, and a conservative per-chromosome `--max-stage-gib` (start at 4 GiB for chr1, lower for smaller chromosomes). Upload final compact edge/evidence/report/manifest per chromosome, verify byte parity and DuckDB validations, then delete local source/intermediate/final duplicates before moving to the next chromosome. Do not promote canonical KG until a separate reviewer accepts all chromosome outputs and the aggregate full-run validation.

## Follow-up cards to create only after approval

1. Implement a ReMap source audit/cache script that records file checksums, BED schema samples, and biotype metadata coverage.
2. Implement staged ReMap → enhancer interval overlap builder for `tf_binds_enhancer` candidates, with no canonical promotion.
3. Implement JASPAR/HOCOMOCO motif support staging and same-TF/same-enhancer support join.
4. Review staged counts and semantics with Jérémie before any canonical KG ingestion.
