# NPInter/RNAInter direct experimental subset source audit

Task: `t_e76149bc`
Status: source audit/staging only; no canonical KG writes; no `.omoc` outputs.

## Policy gate applied

This audit follows `docs/rna_target_policy_t_f5016884.md` and `docs/transcript_rna_relation_blockers_t_40a66443.md`:

- direct RNA/transcript-protein rows may only become active `transcript_interacts_protein` candidates when the row has a source-native current transcript endpoint (`ENST...` or approved transcript mapping) and a source-native/approved protein endpoint (`ENSP...` or unambiguous UniProt->KG protein mapping);
- direct RNA/transcript-gene rows may only become active `transcript_interacts_gene` candidates for source-native transcript/RNA -> gene mechanism rows with endpoint mapping, perturbation/mechanism/direction/effect support;
- miRNA, lncRNA, circRNA, snoRNA/snRNA, RNA-RNA, RNA-DNA, disease/chemical/context, and prediction-only records stay audit/context sidecars or future subtype-specific relation candidates until node/relation gates exist;
- computational/confidence-only rows are not direct mechanism edges.

## Source releases and access/licensing notes

| Source | Audited export URLs | Access/licensing notes |
|---|---|---|
| NPInter v5 | `http://bigdata.ibp.ac.cn/npinter5/download/file/interaction_NPInterv5.expr.txt.gz`, `...comp.txt.gz` | Public download page; files are ZIP archives despite `.gz` suffix. Report page carries 2022 NGDC/Institute of Biophysics footer. Redistribution/license terms were not explicit in the download table, so canonical redistribution needs a separate license check. |
| RNAInter v4 | `http://www.rnainter.org/raidMedia/download/Download_data_RR.tar.gz`, `RP`, `RD`, `RC`, `RH` | Public download page says academic users may use directly and commercial users should contact first. Archives are large; RP is ~548 MB and was downloaded from the official server for this audit. License/redistribution remains a review gate before canonical promotion. |

## Raw schemas inspected

NPInter v5 interaction rows have no header in the archive; observed 16 columns were interpreted from the download documentation/examples:

`interaction_id, rna_name, rna_id, rna_class, partner_name, partner_id, partner_class, description, method, pmid, organism, tissue_or_cell, interaction_type, action, interaction_class, source_of_source`.

RNAInter v4 files are headered TSVs with:

`RNAInterID, Interactor1.Symbol, Category1, Species1, Interactor2.Symbol, Category2, Species2, Raw_ID1, Raw_ID2, score, strong, weak, predict`.

Support buckets used here: `strong != N/A` = strong experimental; else `weak != N/A` = weak/literature/context support; else `predict != N/A` or score-only = computational/predicted/confidence-only.

## Row counts by class/status

### NPInter v5

| Export/status | Broad class | Rows |
|---|---:|---:|
| npinter_v5_computational / computational | computational/predicted/confidence-only | 2,580,617 |
| npinter_v5_experimental / experimental | RNA-RNA | 11,676 |
| npinter_v5_experimental / experimental | RNA-protein | 3,774 |
| npinter_v5_experimental / experimental | RNA-gene | 39 |
| npinter_v5_experimental / experimental | RNA-DNA | 36 |
| npinter_v5_experimental / experimental | other_direct_or_unclear | 29 |
| npinter_v5_experimental / experimental | disease/chemical/context-only | 12 |

### RNAInter v4

| Export | Broad class | Rows |
|---|---:|---:|
| rnainter_v4_RC (RNA-Compound) | disease/chemical/context-only | 10,885 |
| rnainter_v4_RC (RNA-Compound) | computational/predicted/confidence-only | 4 |
| rnainter_v4_RD (RNA-DNA) | RNA-DNA | 138,552 |
| rnainter_v4_RH (RNA-Histone) | disease/chemical/context-only | 1,060,684 |
| rnainter_v4_RP (RNA-Protein) | computational/predicted/confidence-only | 26,322,542 |
| rnainter_v4_RP (RNA-Protein) | RNA-protein | 10,745,045 |
| rnainter_v4_RR (RNA-RNA) | computational/predicted/confidence-only | 7,589,937 |
| rnainter_v4_RR (RNA-RNA) | RNA-RNA | 1,894,672 |

## RNAInter support/status counts

| Export | Support bucket | Rows |
|---|---:|---:|
| rnainter_v4_RC | strong_experimental | 7,320 |
| rnainter_v4_RC | weak_experimental_or_literature_context | 3,565 |
| rnainter_v4_RC | confidence_score_only | 4 |
| rnainter_v4_RD | weak_experimental_or_literature_context | 136,476 |
| rnainter_v4_RD | strong_experimental | 2,076 |
| rnainter_v4_RH | weak_experimental_or_literature_context | 1,060,684 |
| rnainter_v4_RP | computational/predicted/confidence-only | 26,322,514 |
| rnainter_v4_RP | weak_experimental_or_literature_context | 10,719,135 |
| rnainter_v4_RP | strong_experimental | 25,910 |
| rnainter_v4_RP | confidence_score_only | 28 |
| rnainter_v4_RR | computational/predicted/confidence-only | 7,589,777 |
| rnainter_v4_RR | weak_experimental_or_literature_context | 1,436,368 |
| rnainter_v4_RR | strong_experimental | 458,304 |
| rnainter_v4_RR | confidence_score_only | 160 |

## Policy destination counts

### NPInter

| Export | Destination | Rows |
|---|---:|---:|
| npinter_v5_computational | context_sidecar_predicted_only | 2,580,617 |
| npinter_v5_experimental | future_RNA_RNA_or_miRNA/lncRNA_relation | 11,676 |
| npinter_v5_experimental | future_miRNA_lncRNA_or_RNA_subtype_relation_or_sidecar | 3,771 |
| npinter_v5_experimental | context_sidecar_or_rejected_not_direct_mechanism_edge | 41 |
| npinter_v5_experimental | future_lncRNA/mirna_regulates_gene_or_narrow_transcript_interacts_gene_only_after_endpoint_gate | 39 |
| npinter_v5_experimental | future_RNA_DNA_context_or_relation | 36 |
| npinter_v5_experimental | blocked_no_current_transcript_or_protein_endpoint_gate | 3 |

### RNAInter

| Export | Destination | Rows |
|---|---:|---:|
| rnainter_v4_RC | context_sidecar_disease_chemical_histone_only | 10,885 |
| rnainter_v4_RC | context_sidecar_predicted_only | 4 |
| rnainter_v4_RD | future_RNA_DNA_context_or_relation | 138,552 |
| rnainter_v4_RH | context_sidecar_disease_chemical_histone_only | 1,060,684 |
| rnainter_v4_RP | context_sidecar_predicted_only | 26,322,542 |
| rnainter_v4_RP | future_lncRNA/mirna/RNA_protein_relation_or_sidecar_pending_endpoint_mapping | 10,745,045 |
| rnainter_v4_RR | context_sidecar_predicted_only | 7,589,937 |
| rnainter_v4_RR | future_RNA_RNA_or_miRNA/lncRNA_relation | 1,894,672 |

## Endpoint namespace findings

Exact active-relation candidate screen:

| Screen | Rows |
|---|---:|
| npinter_experimental_enst_gene_rna_gene | 0 |
| npinter_experimental_enst_uniprot_rna_protein | 0 |
| npinter_experimental_refseq_uniprot_rna_protein_needs_transcript_mapping | 0 |
| rnainter_RP_enst_uniprot_or_ensp_rna_protein | 0 |
| rnainter_RP_refseq_uniprot_or_ensp_rna_protein_needs_mapping | 0 |
| rnainter_RP_strong_or_weak_enst_uniprot | 0 |
| rnainter_all_enst_gene_rna_gene_like | 0 |

Result: zero source-native `ENST...` + UniProt-like RNA-protein rows and zero supported `ENST...` + gene RNA-gene-like rows were found across the audited NPInter/RNAInter exports. Therefore no non-empty endpoint-validated edge/evidence candidate was staged.

Selected NPInter endpoint namespace top counts:

| Export | Endpoint namespace pair | Rows |
|---|---|---:|
| npinter_v5_computational | `rna:miRBase_precursor_or_related|partner:other|partner_class:mRNA` | 906,222 |
| npinter_v5_computational | `rna:miRBase_precursor_or_related|partner:Ensembl_gene|partner_class:mRNA` | 745,716 |
| npinter_v5_computational | `rna:NONCODE_human_lncRNA|partner:UniProt_like|partner_class:protein` | 390,120 |
| npinter_v5_computational | `rna:NONCODE_human_lncRNA|partner:miRBase_precursor_or_related|partner_class:miRNA` | 116,998 |
| npinter_v5_computational | `rna:Ensembl_gene|partner:UniProt_like|partner_class:protein` | 91,191 |
| npinter_v5_computational | `rna:NONCODE_other|partner:UniProt_like|partner_class:protein` | 85,316 |
| npinter_v5_computational | `rna:other|partner:other|partner_class:mRNA` | 65,114 |
| npinter_v5_computational | `rna:other|partner:UniProt_like|partner_class:protein` | 46,586 |
| npinter_v5_computational | `rna:missing|partner:UniProt_like|partner_class:protein` | 26,852 |
| npinter_v5_computational | `rna:NONCODE_other|partner:miRBase_precursor_or_related|partner_class:miRNA` | 15,928 |
| npinter_v5_experimental | `rna:miRBase_precursor_or_related|partner:Ensembl_gene|partner_class:mRNA` | 3,771 |
| npinter_v5_experimental | `rna:NONCODE_human_lncRNA|partner:miRBase_precursor_or_related|partner_class:miRNA` | 3,654 |
| npinter_v5_experimental | `rna:NONCODE_human_lncRNA|partner:UniProt_like|partner_class:protein` | 1,988 |
| npinter_v5_experimental | `rna:missing|partner:miRBase_precursor_or_related|partner_class:miRNA` | 1,258 |
| npinter_v5_experimental | `rna:miRBase_precursor_or_related|partner:NONCODE_human_lncRNA|partner_class:lncRNA` | 832 |
| npinter_v5_experimental | `rna:NONCODE_other|partner:UniProt_like|partner_class:protein` | 753 |
| npinter_v5_experimental | `rna:missing|partner:UniProt_like|partner_class:protein` | 497 |
| npinter_v5_experimental | `rna:other|partner:miRBase_precursor_or_related|partner_class:miRNA` | 327 |
| npinter_v5_experimental | `rna:Ensembl_gene|partner:miRBase_precursor_or_related|partner_class:miRNA` | 313 |
| npinter_v5_experimental | `rna:miRBase_precursor_or_related|partner:other|partner_class:mRNA` | 239 |

Selected RNAInter endpoint namespace top counts:

| Export | Endpoint namespace pair | Rows |
|---|---|---:|
| rnainter_v4_RC | `raw1:other|raw2:chemical|cat1:miRNA|cat2:compound` | 7,786 |
| rnainter_v4_RC | `raw1:other|raw2:chemical|cat1:circRNA|cat2:compound` | 885 |
| rnainter_v4_RC | `raw1:NCBI_or_numeric|raw2:chemical|cat1:lncRNA|cat2:compound` | 807 |
| rnainter_v4_RC | `raw1:other|raw2:missing|cat1:miRNA|cat2:compound` | 720 |
| rnainter_v4_RC | `raw1:NCBI_or_numeric|raw2:chemical|cat1:mRNA|cat2:compound` | 304 |
| rnainter_v4_RC | `raw1:NCBI_or_numeric|raw2:chemical|cat1:pseudo|cat2:compound` | 115 |
| rnainter_v4_RC | `raw1:other|raw2:other|cat1:miRNA|cat2:compound` | 84 |
| rnainter_v4_RC | `raw1:missing|raw2:chemical|cat1:lncRNA|cat2:compound` | 70 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:DNA` | 59,918 |
| rnainter_v4_RD | `raw1:other|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:DNA` | 34,492 |
| rnainter_v4_RD | `raw1:missing|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:DNA` | 18,968 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:others|cat2:DNA` | 11,069 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:mRNA|cat2:DNA` | 9,437 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:ribozyme|cat2:DNA` | 1,788 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:snRNA|cat2:DNA` | 1,540 |
| rnainter_v4_RD | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:ncRNA|cat2:DNA` | 341 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:lncRNA|cat2:histone modification` | 474,522 |
| rnainter_v4_RH | `raw1:NCBI_or_numeric|raw2:missing|cat1:lncRNA|cat2:histone modification` | 211,763 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:pseudo|cat2:histone modification` | 123,639 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:miRNA|cat2:histone modification` | 94,053 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:others|cat2:histone modification` | 85,784 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:snRNA|cat2:histone modification` | 23,015 |
| rnainter_v4_RH | `raw1:other|raw2:missing|cat1:snoRNA|cat2:histone modification` | 21,087 |
| rnainter_v4_RH | `raw1:missing|raw2:missing|cat1:tRNA|cat2:histone modification` | 8,730 |
| rnainter_v4_RP | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:mRNA|cat2:protein` | 15,978,617 |
| rnainter_v4_RP | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:mRNA|cat2:RBP` | 4,060,736 |
| rnainter_v4_RP | `raw1:other|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:TF` | 2,435,189 |
| rnainter_v4_RP | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:mRNA|cat2:TF` | 1,743,564 |
| rnainter_v4_RP | `raw1:other|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:protein` | 1,544,102 |
| rnainter_v4_RP | `raw1:other|raw2:NCBI_or_numeric|cat1:pseudo|cat2:TF` | 1,167,548 |
| rnainter_v4_RP | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:protein` | 1,131,884 |
| rnainter_v4_RP | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:lncRNA|cat2:TF` | 1,104,749 |
| rnainter_v4_RR | `raw1:other|raw2:NCBI_or_numeric|cat1:miRNA|cat2:mRNA` | 6,897,305 |
| rnainter_v4_RR | `raw1:other|raw2:NCBI_or_numeric|cat1:tRF|cat2:mRNA` | 1,358,167 |
| rnainter_v4_RR | `raw1:missing|raw2:NCBI_or_numeric|cat1:piRNA|cat2:mRNA` | 272,200 |
| rnainter_v4_RR | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:piRNA|cat2:mRNA` | 248,153 |
| rnainter_v4_RR | `raw1:NCBI_or_numeric|raw2:NCBI_or_numeric|cat1:mRNA|cat2:mRNA` | 102,585 |
| rnainter_v4_RR | `raw1:missing|raw2:NCBI_or_numeric|cat1:miRNA|cat2:mRNA` | 74,487 |
| rnainter_v4_RR | `raw1:NCBI_or_numeric|raw2:other|cat1:lncRNA|cat2:miRNA` | 62,716 |
| rnainter_v4_RR | `raw1:other|raw2:NCBI_or_numeric|cat1:miRNA|cat2:lncRNA` | 57,794 |

Interpretation: the large apparently direct subsets are mostly catalog/ncRNA IDs, NCBI/gene-like identifiers, RefSeq/source IDs, genomic-coordinate-like IDs, or source-specific symbols. They are not current TxGNN `transcript`/`protein` endpoint pairs. RNAInter RP contains many weak/strong supported RNA-protein rows, but the raw IDs are not source-native `ENST -> UniProt/ENSP` pairs under the active policy.

## Source-of-source / provenance fields preserved

NPInter preserves row-level `source_of_source`; top observed counts:

| Export | Source of source | Rows |
|---|---|---:|
| npinter_v5_computational | miRanda with Ago CLIP data | 1,150,353 |
| npinter_v5_computational | High-throughput data | 350,877 |
| npinter_v5_computational | TargetScan with Ago CLIP data | 202,924 |
| npinter_v5_computational | ENCODE | 140,070 |
| npinter_v5_computational | RISE database | 129,579 |
| npinter_v5_computational | miRanda and TargetScan with Ago CLIP data | 102,770 |
| npinter_v5_computational | miRanda with Ago CLIP data GSE52084 | 100,430 |
| npinter_v5_computational | High-throughput data combine LncPro prediction | 80,009 |
| npinter_v5_computational | miRanda with Ago CLIP data GSE102319 | 33,618 |
| npinter_v5_computational | miRanda with Ago CLIP data GSE97061 | 31,027 |
| npinter_v5_computational | miRanda with Ago CLIP data GSE102320 | 18,434 |
| npinter_v5_computational | miRanda with Ago CLIP data GSE83410 | 18,140 |
| npinter_v5_experimental | Literature mining | 15,566 |

RNAInter preserves row-level support sources in `strong`, `weak`, and `predict`; see `artifacts/staged/t_e76149bc/rnainter_v4_audit_summary.json` for top source-count tables. Common examples include `ChIP-seq`, `CLIP-seq`, `PARIS`, `MARIO`, `RAP`, `catRAPID`, and source-specific prediction algorithms depending on category.

## Staging decision

No KG edge/evidence Parquet was staged. The only staged artifacts are audit sidecars:

- `artifacts/staged/t_e76149bc/npinter_v5_audit_summary.json`
- `artifacts/staged/t_e76149bc/npinter_v5_sample_rows.json`
- `artifacts/staged/t_e76149bc/rnainter_v4_audit_summary.json`
- `artifacts/staged/t_e76149bc/rnainter_v4_sample_rows.json`
- `artifacts/staged/t_e76149bc/endpoint_candidate_screen.json`

Reason: policy-approved active generic relations had zero direct endpoint-valid rows in this audit. Future builders remain blocked as follows:

- RNA-protein: viable as future `lncrna_interacts_protein`, miRNA/RNA subtype relations, or active `transcript_interacts_protein` only after reviewed RNA/transcript ID mapping plus protein endpoint mapping;
- RNA-gene: wait for `mirna_targets_gene`, `mirna_targets_transcript`, `lncrna_regulates_gene`, or a narrow `transcript_interacts_gene` builder with explicit ENST/RefSeq transcript-to-current transcript mapping and mechanism/effect fields;
- RNA-RNA and RNA-DNA: wait for explicit RNA-RNA/RNA-DNA relation and node policies;
- disease/chemical/histone/context and confidence/prediction-only rows: feature/context sidecars only, not direct mechanism edges.

## Verification

- Downloaded/parsed official NPInter v5 experimental and computational exports.
- Downloaded/parsed official RNAInter v4 RR/RP/RD/RC/RH exports; exact row counts above.
- Ran exact endpoint candidate screen in `artifacts/staged/t_e76149bc/endpoint_candidate_screen.json`; all active relation candidate counts are zero.
- Wrote no canonical KG files and no `.omoc` outputs.

