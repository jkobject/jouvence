# ReMap pre-overlap / CRM alternative spike

_Date: 2026-06-23_
_Status: spike only; no canonical writes._

## Question

Can we avoid many hours of raw ReMap all-peak intersection for `tf_binds_enhancer` by using an already-overlapped dataset or the smaller ReMap CRM file?

Short answer: no source found in this spike can cleanly replace the current provenance-preserving all-peak ReMap intersection. ReMap CRM is useful as a much smaller regulatory-region/QA/support input and may justify a bounded pilot, but it should not be the primary `observed_binding` evidence source unless the reviewer accepts explicit provenance loss.

## Recommendation

Recommended path: continue the current all-peak ReMap pipeline for primary `tf_binds_enhancer` evidence, and optionally run a bounded CRM-first pilot as a fast triage/support lane.

Decision: `use_crm_as_support_or_triage_only`.

Rationale:

1. `tf_binds_enhancer` needs observed TF binding evidence with source record/provenance, assay/context, score, coordinates, and source release preserved.
2. ReMap `all` BED rows preserve source accession, TF symbol, and biotype in the BED name, e.g. `GSE137250.SMARCA4.HeLa`.
3. ReMap CRM rows collapse many regulators into one CRM interval with comma-separated TF symbols in column 4. This is excellent for reducing interval volume and finding candidate regulatory regions, but it removes per-experiment accession and per-peak evidence granularity.
4. ENCODE SCREEN provides hg38 cCRE class BED downloads, including TF/CTCF-related cCRE classes, but the public download evidence observed in this spike is cCRE annotation/classification, not a per-TF observed TF×cCRE overlap table suitable for `tf_binds_enhancer` edges.
5. ChIP-Atlas is legally usable (site states all data/tools are CC-BY 4.0) and has ChIP-seq peak/target-gene tooling, but the observed public surface is not an accepted direct TF×our-enhancer pre-overlap table. Target Genes would risk drifting into `tf_regulates_gene`/gene-target semantics.
6. GeneHancer/GeneCards is not suitable for canonical ingestion without explicit redistribution clearance; access was blocked during this spike and GeneCards/GeneHancer is generally not an open bulk redistribution source.
7. EnhancerAtlas 2.0 exposes predicted enhancer annotations and target-gene prediction utilities, mostly hg19 for human in the observed page, but no clear redistribution/license signal was found in this spike and its semantics are enhancer/target prediction rather than direct observed TF binding.

## Evidence collected

### ReMap CRM

URL checked:

- `https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_crm_macs2_hg38_v1_0.bed.gz`

HEAD observed on 2026-06-23:

- HTTP 200
- `content-type: application/x-gzip`
- `content-length: 199805648`
- `last-modified: Tue, 10 Aug 2021 16:39:22 GMT`

Sample rows streamed from the gzip:

```text
chr1 9829   10459  TEAD4,ESRRA,ZNF157,TARDBP,ZBTB26,...,TERF1 148 . 10101 10102 204,120,188
chr1 136455 137130 NCOR1,HDAC1,MTA3,L3MBTL2,DPF2,...,ZNF592       33  . 136762 136763 1,115,178
chr1 180674 180998 NME2,STAT3,SMC1,NCOA2,SMC1A,ESR1,NBN,ZBTB40   12  . 180822 180823 1,115,178
chr1 181203 181789 MED1,BRD3,CTCFL,POU5F1,MYC,SETDB1,FLI1,...    14  . 181462 181463 2,158,115
chr1 191531 191865 FLI1,ERG                                        2  . 191702 191703 148,148,148
```

Interpretation:

- BED-like hg38 CRM interval file.
- Column 4 is a comma-separated regulator/TF-symbol list, not an experiment accession.
- Column 5 appears to be a support/count-like score for the CRM, not a raw per-experiment peak score.
- Per-experiment provenance from the all-peak BED is absent in the row itself.

Local policy alignment:

- `docs/proposals/remap_motif_tf_binds_enhancer_audit.md` already recommends `remap2022_all_macs2_hg38_v1_0.bed.gz` as primary observed evidence because it preserves source experiment accession in the BED `name`.
- The same proposal says CRM should be a regulatory-region support/helper input, not the only evidence source if source accession is needed.

### ReMap all/nr semantics from local audit

Existing local audit summary:

- `all` BED name decomposes like `source_accession.TF.biotype` and preserves source accession, TF symbol, and biotype.
- `nr` collapses to `TF:biotype` and is useful for deduplicated interval/TF support but loses original experiment accession.
- `crm` has comma-separated TF symbols over one interval and should be treated as candidate regulatory-region support unless decomposed with explicit provenance caveats.

This matches the desired KG evidence model: graph edges deduplicated by `(TF gene, enhancer node, relation)`, evidence rows preserving ReMap row-level source metadata.

## Candidate alternative source assessment

| Source | What it provides | Legal/source acceptability | Semantics vs `tf_binds_enhancer` | Decision |
|---|---|---:|---|---|
| ReMap all hg38 MACS2 | Per-peak observed regulatory ChIP rows with source accession, TF, biotype in row name | Public ReMap download; already selected locally | Best match for observed binding after overlap with accepted enhancer nodes | Keep as primary |
| ReMap nr hg38 MACS2 | Deduplicated TF/biotype peaks | Public ReMap download | Useful support/QC; loses source accession | Support/QC only |
| ReMap CRM hg38 MACS2 | CRM intervals with comma-separated TF lists; ~200 MB gz | Public ReMap download | Fast candidate interval/support source; lacks per-experiment provenance | Bounded pilot/support only |
| ENCODE SCREEN cCRE downloads | hg38 cCRE class BEDs: PLS, pELS, dELS, CA-CTCF, CA-TF, TF-only, CTCF-bound, etc. | ENCODE policy page says released ENCODE data are available for unrestricted use immediately upon release | cCRE class annotations identify regulatory elements and TF/CTCF-related classes, but not observed per-TF binding to our enhancer nodes | Not a replacement; possible enhancer-node source or QA class annotation |
| ChIP-Atlas | Integrated ChIP/ATAC/Bisulfite experiments; Peak Browser and Target Genes tooling | Site states data/tools are CC-BY 4.0 with attribution | Peak tooling could be another raw-peak source; Target Genes changes semantics toward gene targets/regulation | Not a pre-overlap replacement; possible future alternate raw observed-binding source |
| GeneHancer / GeneCards | Enhancer/gene associations, disease/gene card integrations | Access blocked in spike; redistribution terms not accepted here | Primarily enhancer-gene/regulatory association, not observed TF binding | Reject for canonical ingestion unless explicit license clearance |
| EnhancerAtlas 2.0 | Predicted/compiled enhancer annotations across tissues/species; target prediction utility | No clear redistribution/license signal found in spike | Mostly enhancer/target prediction; human page observed hg19, not direct TF binding | Reject for current canonical `tf_binds_enhancer` |

## Semantics comparison

### Observed binding evidence

- ReMap all: yes, after parsing each observed peak row and intersecting with accepted KG enhancer nodes.
- ReMap CRM: weaker; the interval/regulator list is derived/aggregated, not row-level observed ChIP evidence.
- SCREEN cCRE TF classes: class-level cCRE annotation; not per-TF observed binding.
- ChIP-Atlas peaks: yes as a raw source, but would still require intersection and source-specific parsing.
- Target-gene resources: no; they should not create `tf_binds_enhancer` and must not leak into `tf_regulates_gene` without an explicit approved relation/source policy.

### Per-experiment provenance

- ReMap all: preserves source accession in row name.
- ReMap nr/CRM: collapsed; original experiment accession unavailable from the row.
- SCREEN cCRE class beds: not per-experiment TF binding provenance.
- ChIP-Atlas: may preserve experiment metadata if using raw/all peaks; not verified here as pre-overlap.

### TF symbol mapping

- ReMap all/nr/CRM and ChIP-Atlas all require TF symbol normalization to canonical KG gene IDs.
- CRM explosion can create many `(TF, CRM interval)` rows quickly, but symbol ambiguity and non-TF regulator/cofactor filtering still apply.

### Cell/biotype context

- ReMap all has biotype in the row name and ReMap biotypes metadata can add context.
- CRM collapses across TFs and contexts; row-level cell/biotype context is not preserved in the observed sample.
- SCREEN cCRE classes and ChIP-Atlas have their own biosample dimensions, but this spike did not find a direct TF×accepted-enhancer pre-overlap table retaining those dimensions.

### Motif support

No candidate here changes the existing motif policy: motif-only evidence must not create active `tf_binds_enhancer` edges. Motifs can support observed-binding rows only.

### Avoiding `tf_regulates_gene`

- ReMap all/CRM overlap with enhancer nodes stays in `tf_binds_enhancer` if no enhancer→gene expansion is performed.
- ChIP-Atlas Target Genes, GeneHancer, EnhancerAtlas target prediction, and SCREEN cCRE-gene links are gene-target/regulatory-association surfaces; they should not be used as direct TF binding edges and should not be used to create `tf_regulates_gene` under this task.

## CRM-first pilot caveats

A CRM-first pilot is viable only as a bounded, reviewer-gated triage/support experiment. It should:

1. Intersect CRM intervals with existing KG enhancer nodes on one genome build, default hg38.
2. Explode CRM comma-separated TF symbols into candidate TF rows.
3. Map TF symbols to canonical KG `gene` IDs with accepted/rejected counts.
4. Write only staging artifacts, never canonical KG outputs.
5. Mark evidence type as `crm_aggregated_support` or equivalent, not `observed_binding`, unless a reviewer explicitly accepts derived CRM rows as observed-binding support.
6. Preserve caveats: no experiment accession, no per-experiment peak score, likely reduced cell/biotype context, aggregated support/count score.
7. Compare candidate edge counts against all-peak ReMap results when available, using CRM as sensitivity/coverage QA rather than replacement.

## Acceptance guidance

Use this spike to make one of these choices:

- Continue all-peak pipeline: yes, for primary observed evidence.
- Switch to CRM-first staged pilot: only as a bounded support/triage lane with strict provenance caveats.
- Use another pre-overlap source: no acceptable direct source found.
- Use CRM as support/QA only: yes, strongest recommendation.

## No canonical writes

This spike wrote only:

- `docs/remap_preoverlap_or_crm_alternative_spike.md`
- `.omoc/reports/remap_preoverlap_or_crm_alternative_spike.json`

No canonical KG paths were written.
