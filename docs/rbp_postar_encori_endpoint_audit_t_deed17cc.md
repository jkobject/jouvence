# POSTAR3 / ENCORI RBP endpoint audit for `transcript_interacts_protein`

Task: `t_deed17cc`  
Status: source audit / staging decision only; no canonical KG writes.

## Policy gate applied

The parent policy `docs/rna_target_policy_t_f5016884.md` allows `transcript_interacts_protein` only when a row has both:

- an RNA endpoint representable as a current KG `transcript` node (`ENST...`) or an approved transcript mapping from RefSeq/GENCODE; and
- a protein endpoint representable as a current KG `protein` node (`ENSP...`) or a source-native/approved mapped UniProt/protein accession.

It explicitly blocks coordinate-only CLIP/site rows and RBP gene-symbol-only rows from edge staging unless separate coordinate-to-transcript and RBP-symbol-to-protein projection gates are reviewed. This audit therefore did not stage `transcript_interacts_protein` edge/evidence rows.

## Source exports inspected

### POSTAR3 / POSTAR lineage

Inspected URLs/files:

- POSTAR3 landing page: `https://postar.ncrnalab.org/`, redirects to `http://111.198.139.65/`.
- POSTAR download page: `http://111.198.139.65/download.php`.
- Human RBP binding sites export: `http://111.198.139.65/download/human_RBP_binding_sites.txt.zip`.
- Zip member: `human_RBP_binding_sites.txt`.
- Other download-page RBP exports listed: `mouse_RBP_binding_sites.txt.zip`, `fly_RBP_binding_sites.txt.zip`, `worm_RBP_binding_sites.txt.zip`, `arabidopsis_RBP_binding_sites.txt.zip`, `yeast_RBP_binding_sites.txt.zip`.

Access / license notes:

- The download page is public and direct HTTP download works, but the page labels buttons as "Register and Download".
- I did not find an explicit redistribution license on the probed POSTAR pages. Treat redistribution/promotion as requiring manual terms/citation review.
- POSTAR3 page cites the POSTAR3 NAR paper (PMID: 34403477), POSTAR2 (PMID: 30239819), POSTAR (PMID: 28053162), and CLIPdb (PMID: 25652745).

Schema observed from the human export:

The file has no header in the downloaded text. All observed rows have 11 tab-separated columns and are BED-like:

| Position | Inferred field | Example |
|---:|---|---|
| 1 | chromosome | `chr10` |
| 2 | start | `98763019` |
| 3 | end | `98763040` |
| 4 | site/source id | `human_RBP_CLIPdb_2267` |
| 5 | score | `0` |
| 6 | strand | `-` |
| 7 | RBP name/symbol | `PTBP1` |
| 8 | CLIP method/caller/support label | `HITS-CLIP,CIMS` |
| 9 | cell/context | `HeLa` |
| 10 | study/sample accession(s) | `GSE19323,GSM480478` |
| 11 | support/count-like integer | `3` |

Streaming audit of the full human ZIP payload:

| Measure | Count |
|---|---:|
| Decompressed rows | 31,190,710 |
| Rows with 11 columns | 31,190,710 |
| Target classified as coordinate-only BED interval | 31,190,710 |
| Target rows containing `ENST` by regex | 0 |
| Target rows containing RefSeq transcript `NM_`/`NR_` by regex | 0 |
| RBP field classified as gene symbol/name-only | 31,190,710 |
| RBP field containing UniProt/ENSP-like protein id by regex | 0 |

POSTAR endpoint decision:

- Target endpoint classification: coordinate-only genomic binding-site interval.
- RBP endpoint classification: RBP gene symbol/name-only.
- Policy result: no passing `transcript -> protein` endpoint pair. These rows are useful `rbp_binding_site_context` candidates, not edge candidates, until both coordinate-to-transcript mapping and RBP-symbol-to-protein projection policies are approved.

### ENCORI / starBase RBP CLIP-RNA modules

Inspected pages and query-scoped text downloads:

- `https://rnasysu.com/encori/rbpClipRNA.php?source=mRNA`
- `https://rnasysu.com/encori/rbpClipRNA.php?source=lncRNA`
- `https://rnasysu.com/encori/rbpClipRNA.php?source=circRNA`
- `https://rnasysu.com/encori/rbpClipRNA.php?source=sncRNA`
- `https://rnasysu.com/encori/rbpClipRNA.php?source=pseudogene`
- `https://rnasysu.com/encori/rbpClipRNA.php?source=caRNA`

For exact schemas I used the page-advertised `moduleDownload.php` endpoint with the page default/example query values:

| Source module | Query-scoped download inspected | Rows returned in query |
|---|---|---:|
| mRNA | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;mRNA;all;1;0;MYC` | 150 |
| lncRNA | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;lncRNA;all;1;0;MALAT1` | 255 |
| circRNA | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;circRNA;all;1;0;CDR1as` | 48 |
| sncRNA | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;sncRNA;all;1;0;SCARNA11` | 38 |
| pseudogene | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;pseudogene;all;1;0;SKP1P1` | 18 |
| caRNA | `https://rnasysu.com/encori/moduleDownload.php?source=rbpClipRNA&type=txt&value=hg38;caRNA;all;1;0;L2` | 279 |

Access / license notes:

- ENCORI pages returned HTTP 200 and the `moduleDownload.php` text exports returned `application/octet-stream`.
- The page HTML starts with: `License: Creative Commons Attribution 4.0 Unported License URL: https://creativecommons.org/licenses/by/4.0/`.
- The downloads include citation preamble lines rather than only tabular data; row parsing must skip leading `#` citation lines.
- These are query-scoped exports, not a release-pinned bulk export discovered in this audit.

Schemas observed:

For mRNA, lncRNA, sncRNA, pseudogene, and caRNA query exports the tabular header is:

`RBP`, `geneID`, `geneName`, `geneType`, `clusterNum`, `clipExpNum`, `clipIDnum`, `HepG2(shRNA)`, `K562(shRNA)`, `HepG2(CRIPSR)`, `K562(CRIPSR)`, `pancancerNum`

For circRNA query export the tabular header is shorter:

`RBP`, `geneID`, `geneName`, `geneType`, `clusterNum`, `clipExpNum`, `clipIDnum`

Examples:

- mRNA: `ACIN1\tENSG00000136997\tMYC\tprotein_coding\t7\t6\t21\tNA\tNA\tNA\tNA\t15`
- lncRNA: `A1CF\tENSG00000251562\tMALAT1\tlncRNA\t3\t2\t4\tNA\tNA\tNA\tNA\t18`
- circRNA: `CPSF1\thsa_circ_0001946\tCDR1as\tcircRNA\t1\t1\t1`
- sncRNA: `ACIN1\tENSG00000251898\tSCARNA11\tscaRNA\t1\t5\t6\tNA\tNA\tNA\tNA\t9`
- pseudogene: `EIF4A3\tENSG00000231234\tSKP1P1\ttranscribed_processed_pseudogene\t1\t1\t1\tNA\tNA\tNA\tNA\t12`
- caRNA: `A1CF\tL2\tL2\tLINE\t2\t2\t4\tNA\tNA\tNA\tNA\t`

Endpoint classification of inspected ENCORI query rows:

| Module | Target endpoint fields/class | Count inspected | RBP endpoint field/class | Count inspected | Edge-stage decision |
|---|---|---:|---|---:|---|
| mRNA | `geneID` = ENSG gene id, `geneName`; gene-only target, no ENST/RefSeq transcript | 150 | `RBP` gene symbol/name-only, no UniProt/ENSP | 150 | reject edge; context only |
| lncRNA | `geneID` = ENSG locus + lncRNA name/type; lncRNA-specific/gene-level, no ENST/RefSeq transcript | 255 | `RBP` gene symbol/name-only, no UniProt/ENSP | 255 | reject edge; future `lncrna_interacts_protein` only after lncRNA/protein mapping gates |
| circRNA | `geneID` = `hsa_circ_...`; circRNA id | 48 | `RBP` gene symbol/name-only, no UniProt/ENSP | 48 | reject edge; future circRNA/ncRNA context only |
| sncRNA | `geneID` = ENSG locus + scaRNA name/type; sncRNA-specific/gene-level, no ENST/RefSeq transcript | 38 | `RBP` gene symbol/name-only, no UniProt/ENSP | 38 | reject edge; context only |
| pseudogene | `geneID` = ENSG locus + pseudogene name/type; not transcript endpoint | 18 | `RBP` gene symbol/name-only, no UniProt/ENSP | 18 | reject edge; context only |
| caRNA | repeat/chromatin-associated RNA name (`L2`) and type (`LINE`); not transcript endpoint | 279 | `RBP` gene symbol/name-only, no UniProt/ENSP | 279 | reject edge; context only |

ENCORI endpoint decision:

- The inspected RBP modules report target gene/name/type or ncRNA/repeat identifiers, not source-native ENST/RefSeq transcript endpoints.
- The RBP endpoint is an RBP gene symbol/name, not a source-native protein accession.
- Therefore none of the inspected ENCORI rows pass the current `transcript_interacts_protein` endpoint gate.

## Candidate staging decision

No `transcript_interacts_protein` edge/evidence candidate was staged.

Reason:

1. POSTAR3 human RBP export is coordinate-only for the RNA target and gene-symbol-only for the RBP endpoint.
2. ENCORI/starBase inspected RBP module exports are gene/ncRNA/repeat identifier scoped for target and RBP-symbol-only for protein.
3. Parent policy blocks both coordinate-only target mapping and RBP gene-symbol-to-protein projection without separate reviewed gates.

Because no non-empty endpoint-validated rows exist under current policy, there are no endpoint anti-join counts for candidate edges. The endpoint anti-join result is vacuously `0` staged rows / `0` missing endpoints because no edge file was produced.

## Sidecar recommendation

Use these sources as `rbp_binding_site_context` / rejected-candidate sidecars rather than active edges:

- POSTAR3: site-level context with `chromosome`, `start`, `end`, `strand`, `rbp_symbol`, `clip_method`, `cell_context`, `study_accessions`, `site_id`, and support/count field. Add a future coordinate-to-transcript mapper only after a reviewed mapping policy preserves assembly, interval, method, confidence, and source site id.
- ENCORI: query/module-level RBP-RNA context with `rbp_symbol`, `target_source_type`, `target_source_id`, `target_name`, `gene_type`, `clusterNum`, `clipExpNum`, `clipIDnum`, knockdown/CRISPR context columns, and `pancancerNum`. Keep lncRNA/circRNA/sncRNA/pseudogene/caRNA in subtype-specific context buckets until subtype nodes/relations exist.

A machine-readable audit summary and sidecar decision live at:

- `artifacts/staged/t_deed17cc/source_schema_audit_summary.json`
- `artifacts/staged/t_deed17cc/rbp_binding_site_context_recommendation.json`

## What would be needed before edge staging

1. POSTAR coordinate rows: reviewed genome assembly + interval-to-transcript/site mapping against current KG transcript nodes.
2. ENCORI gene/ncRNA target rows: source-native transcript IDs or a reviewed target mapping; lncRNA/circRNA/sncRNA subtype node policy for subtype-specific rows.
3. RBP endpoint rows from either source: source-native UniProt/ENSP/protein accession, or a reviewed RBP-symbol-to-protein projection gate with row-level ambiguity handling and original RBP symbol retained in evidence.
4. Only after those gates: write staged edge/evidence rows under `artifacts/staged/<task-id>/` and run endpoint anti-joins against current canonical `transcript` and `protein` nodes.

## Verification performed

- Streamed the POSTAR3 human ZIP from source without saving the 514 MB compressed file into the repo.
- Counted/decompressed all 31,190,710 POSTAR human rows and verified the 11-column BED-like shape.
- Queried ENCORI module pages/download endpoint for six RBP source modules and recorded headers/samples/counts.
- Wrote only repo-local `docs/` and `artifacts/staged/t_deed17cc/` outputs.
- Did not write canonical `gs://jouvencekb/kg/v2` and did not create `.omoc` outputs.
