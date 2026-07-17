# LncRNA2Target / LncTarD lncRNA regulation source audit

Task: `t_74dc3d9c`  
Status: source access / license / schema audit only; no canonical KG writes; no active edge staging.

## Decision

Do not stage direct mechanism edges from either source in this task.

Reason:

1. Policy gate `t_f5016884` says lncRNA target-gene regulation should prefer future `lncrna_regulates_gene`; active `transcript_interacts_gene` is allowed only for source-native ENST/RefSeq/GENCODE transcript endpoints with perturbation/mechanism/direction/effect.
2. LncRNA2Target public access is not currently reliable from this worker, so its downloadable schema, license, and endpoint namespaces cannot be verified.
3. LncTarD 2.0 is downloadable and mechanism-rich, but the public site uses a TLS certificate hostname mismatch and no explicit license/redistribution terms were found in the inspected pages. Its lncRNA regulator endpoint is mostly gene-level Ensembl IDs (`ENSG...`) or names; only 15 unique ENST regulator IDs appeared in lncRNA->gene candidate rows. Gene-level lncRNA IDs are not approved as `transcript_interacts_gene` x endpoints without a reviewed lncRNA node/mapping gate.
4. LncTarD rows are disease-context functional regulations. They are valuable context/evidence for a future `lncrna_regulates_gene` relation, but disease-associated, ceRNA/sponge, expression-association, RNA-RNA, and RNA-protein rows must not be collapsed into a direct transcript->gene mechanism edge.

## Policy handoff consumed

From `docs/rna_target_policy_t_f5016884.md`:

- Do not use generic transcript relations as a backdoor for subtype-specific RNA biology.
- `transcript_interacts_gene` is allowed only for a source-native transcript/RNA endpoint representable as a current transcript node plus target gene, with regulatory/mechanistic assertion and perturbation/direction/effect support.
- `lncrna_regulates_gene` is the preferred future relation for lncRNA target-gene regulation, with approved lncRNA/ncRNA nodes or source-native ENST/GENCODE lncRNA transcript endpoints.
- Reject disease-only, ceRNA/correlation-only, pathway enrichment, and context-only rows as direct mechanism edges.

## Source access and license status

| Source | Access checked | Result | License / redistribution status | Build decision |
|---|---|---|---|---|
| LncRNA2Target v2.0 | `http://bio-annotation.cn/lncrna2target/`, `https://bio-annotation.cn/lncrna2target/`, `http://www.lncrna2target.org/`, `https://www.lncrna2target.org/` | `bio-annotation.cn` refused connections; `www.lncrna2target.org` redirected to unrelated `https://alittledelightful.com/`. PubMed confirms v2.0 was described as freely accessible at `http://123.59.132.21/lncrna2target`, but this task did not obtain a stable source export. | Not verified. No page/export terms could be inspected from live source access. | No build. Use only literature-level source recommendation until exact export and terms are recovered. |
| LncTarD 2.0 | `http://bio-bigdata.hrbmu.edu.cn/LncTarD/` redirects to `https://lnctard.bio-database.com/`; `/download` links `/downloadfile/lnctard2.0.zip`. | Download succeeded only with TLS verification disabled because the certificate is not valid for `lnctard.bio-database.com`. Archive SHA256: `f4205dcdbb6af5cf84190907ea46bd546f7585fb4b713c6d7f65cb0d9610c7c2`. | Not approved. Inspected home/download/help/search pages include copyright text and public download links, but no explicit license or redistribution/commercial-use terms were found. | No active edge staging. Keep source-audit artifacts only; require license/contact review before redistributed candidate tables. |

Source papers used for orientation:

- LncRNA2Target: PMID `25399422` (2015), PMID `30380072` (v2.0, 2019). The v2.0 abstract says it retrieved lncRNA-target relationships from papers and RNA-seq datasets before/after lncRNA knockdown or overexpression in human and mouse.
- LncTarD: PMID `31713618` (2020), PMID `36321659` (LncTarD 2.0, 2023). The v2.0 abstract reports 8,360 key lncRNA-target regulations, 419 disease subtypes, and 1,355 lncRNAs.

## LncTarD 2.0 downloadable schema

Downloaded file: `artifacts/staged/t_74dc3d9c/raw/lnctard2.0.zip`  
Extracted table: `lnctard2.0.txt`  
Rows: `8,360`  
Columns: `35`

Columns:

- `DiseaseName`
- `Regulator`
- `Target`
- `RegulationDiretion` (source spelling)
- `Experimental.method.for.lncRNA.target`
- `ExpressionPattern`
- `Experimental.method.for.lncRNA.expression`
- `Data.accession`
- `Data.accession2`
- `influencedFunction`
- `regulatoryMechanism`
- `regulatoryType`
- `levelOfRegulation`
- `Drugs`
- `cancerStemCell`
- `hallmark`
- `diseaseCategory`
- `DiseaseName2`
- `RegulatorType`
- `TargetType`
- `RegulatorEnsembleID` (source spelling)
- `lncRegulatorPosition`
- `TargetEnsembleID` (source spelling)
- `lncTargetPosition`
- `RegulatorEntrezID`
- `TargetEntrezID`
- `RegulatorAliases`
- `TargetAliases`
- `Evidence`
- `PubMedID`
- `RID`
- `SearchregulatoryMechanism`
- `clincal.application` (source spelling)
- `RegulatorCTC`
- `TargetCTC`

The LncTarD help page defines key user-facing fields as:

- `DiseaseName`: associated disease.
- `Regulator`: regulator gene name.
- `Target`: target gene name.
- `RegulationDirection`: regulator negatively or positively regulated the target gene.
- `InfluencedFunctions`: biological function positively/negatively affected by the lncRNA-target regulation.
- `RegulatoryMechanism`: lncRNA-mediated regulatory mechanism in human disease.

## LncTarD 2.0 row class counts

All-source table:

| Class | Count |
|---|---:|
| total rows | 8,360 |
| `RegulatorType == lncRNA` | 7,773 |
| `TargetType == PCG` | 5,072 |
| `TargetType == TF` | 1,583 |
| `TargetType == miRNA` | 1,103 |
| `TargetType == lncRNA` | 598 |
| rows with non-empty `regulatoryMechanism` field | 8,360 |
| rows with non-empty `RegulationDiretion` field | 8,360 |
| rows with non-empty experimental lncRNA-target method | 8,020 |
| rows with non-empty `PubMedID` field | 8,360 |
| rows mentioning ceRNA/sponge in any field | 3,850 |
| rows mentioning expression correlation/coexpression in any field | 1,628 |

Refined lncRNA-regulator to gene-target bucket (`RegulatorType == lncRNA` and `TargetType in {PCG, TF}`):

| Class | Count |
|---|---:|
| lncRNA -> PCG/TF target rows | 6,643 |
| lncRNA -> PCG rows | 5,063 |
| lncRNA -> TF rows | 1,580 |
| unique lncRNA regulator names in this bucket | 1,230 |
| unique target names in this bucket | 1,975 |
| unique lncRNA regulator Ensembl IDs | 850 |
| unique target Ensembl IDs | 1,798 |
| rows with target `ENSG...` | 6,296 |
| rows where regulator has only `ENSG...` and no `ENST...` | 5,953 |
| rows where regulator has `ENST...` | 25 |
| rows with non-NA regulation direction | 6,586 |
| rows with non-NA mechanism | 4,296 |
| rows with experimental lncRNA-target method | 6,414 |
| rows with disease context | 6,643 |
| rows tagged ceRNA/sponge in `SearchregulatoryMechanism` | 2,913 |
| rows tagged expression association in `SearchregulatoryMechanism` | 2,381 |

Top LncTarD values:

- `RegulationDiretion`: `positively-E` 5,069; `negatively-E` 1,972; `negatively-F` 691; `interact` 346; `positively-F` 194; `NA` 70.
- `regulatoryType`: `regulation` 4,885; `binding/interaction` 1,960; `association` 1,498; `NA` 17.
- `levelOfRegulation`: `RNA-protein` 2,743; `RNA-RNA` 916; `protein-RNA` 101; `protein-DNA` 86; `RNA-DNA` 54; `NA` 4,456.
- `SearchregulatoryMechanism`: `ceRNA or sponge` 3,719; `expression association` 2,829; `interact with protein` 706; `transcriptional regulation` 595; `epigenetic regulation` 436; `interact with mRNA` 62; `chromatin looping` 13.

These buckets show that LncTarD is not a clean direct lncRNA->gene mechanism table. It mixes gene regulation, RNA-RNA/ceRNA, RNA-protein/protein-RNA, binding/interaction, expression association, and disease-context rows.

## Endpoint namespace and anti-join proof

Canonical root checked: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`

Canonical node counts loaded from Parquet with the project `.venv`:

- `nodes/gene.parquet`: `267,830` ids.
- `nodes/transcript.parquet`: `507,365` ids.
- No `nodes/lncrna.parquet` exists in the current canonical KG root.

For the 6,643 LncTarD lncRNA->PCG/TF candidate rows:

| Endpoint check | Result |
|---|---:|
| unique target `ENSG...` IDs | 1,798 |
| target `ENSG...` present in canonical gene nodes | 1,758 |
| target `ENSG...` missing from canonical gene nodes | 40 |
| unique regulator `ENST...` IDs | 15 |
| regulator `ENST...` present in canonical transcript nodes | 15 |
| regulator `ENST...` missing from canonical transcript nodes | 0 |
| unique regulator `ENSG...` IDs | 835 |
| regulator `ENSG...` present in gene nodes but invalid as lncRNA/transcript relation endpoint | 809 |
| regulator `ENSG...` missing from gene nodes | 26 |

Interpretation:

- Target gene mapping is mostly feasible for future staging after version/mapping cleanup, but 40 unique target `ENSG...` ids still anti-join against current canonical gene nodes.
- LncRNA regulator mapping is the blocker. Most LncTarD lncRNA regulators are source names plus Ensembl gene IDs, not transcript/lncRNA node IDs. Only 15 unique ENST regulators were observed in the candidate gene-target bucket.
- The current canonical KG has transcript nodes but no active lncRNA node family. Therefore source rows should wait for `lncrna_regulates_gene` plus approved lncRNA node/mapping policy, or a narrow ENST-only pilot that excludes the overwhelming majority of rows and still needs license review.

## Row handling recommendations

Do not stage as active direct mechanism edges now:

- LncRNA2Target rows: source export and terms are not accessible/verified.
- LncTarD disease-associated expression association rows.
- LncTarD ceRNA/sponge rows as direct lncRNA->gene mechanism edges.
- LncTarD RNA-RNA, RNA-protein, protein-RNA, protein-DNA, or binding/interaction rows as `transcript_interacts_gene`.
- LncTarD lncRNA regulator rows where the endpoint is only a name or `ENSG...` gene ID.
- Rows with missing/anti-joined target `ENSG...` until mapped or dropped.

Recommended future sidecar / builder path:

1. Get explicit LncTarD and LncRNA2Target license/redistribution approval or document terms sufficient for internal staged artifacts.
2. Add or approve an lncRNA node/mapping gate using GENCODE/RNAcentral/Ensembl transcript provenance. Preserve source lncRNA name, `RegulatorEnsembleID`, Entrez ID, aliases, genomic position, and mapping confidence.
3. Add future `lncrna_regulates_gene` relation before full staging. Use evidence fields for disease, mechanism, direction, function, assay, expression pattern, PMID, RID, data accession, and clinical/CTC flags.
4. For LncTarD, split classes before building:
   - `regulatoryType == regulation` and `TargetType in {PCG, TF}` with non-NA mechanism/direction/experimental method: possible future `lncrna_regulates_gene` candidates.
   - `SearchregulatoryMechanism == expression association`: context sidecar, not mechanism edge.
   - `ceRNA or sponge`, `RNA-RNA`, target miRNA/lncRNA: future RNA-RNA/ceRNA context relation or sidecar, not lncRNA->gene.
   - `RNA-protein` / `interact with protein`: future `lncrna_interacts_protein` only after protein endpoint mapping, not gene regulation.
5. Consider a later ENST-only smoke candidate from the 25 rows with ENST regulators only after license review and after proving every row has a resolved target gene and supported regulatory assertion.

## Artifacts produced by this audit

Source-audit artifacts only; no active edge/evidence Parquet was staged.

- `artifacts/staged/t_74dc3d9c/raw/lnctard2.0.zip`
- `artifacts/staged/t_74dc3d9c/raw/lnctard2_0_extracted/lnctard2.0.txt`
- `artifacts/staged/t_74dc3d9c/raw/lnctard_download.html`
- `artifacts/staged/t_74dc3d9c/raw/lnctard_help.html`
- `artifacts/staged/t_74dc3d9c/raw/lnctard_search.html`
- `artifacts/staged/t_74dc3d9c/reports/lnctard2_schema_summary.json`
- `artifacts/staged/t_74dc3d9c/reports/lnctard2_refined_counts.json`
- `artifacts/staged/t_74dc3d9c/reports/lnctard2_endpoint_antijoin.json`
- `artifacts/staged/t_74dc3d9c/reports/lnctard2_lncrna_to_pc_gene_sample.tsv` (50-row inspection sample only, not an edge candidate)
- `artifacts/staged/t_74dc3d9c/reports/source_pubmed_summaries.json`

No canonical writes were performed. No `.omoc` outputs were produced by this task.
