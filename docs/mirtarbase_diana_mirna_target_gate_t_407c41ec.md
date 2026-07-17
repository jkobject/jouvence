# miRTarBase / DIANA-TarBase miRNA target schema-gated pilot

Task: `t_407c41ec`  
Status: source/schema gate completed; no canonical KG writes; no target edge pilot staged because target-source access/license/schema gate did not pass in this run.

## Policy gate result

Parent policy `t_f5016884` approves a staged-only miRNA path, but not use of generic transcript relations as a backdoor:

- represent mature miRNA products as distinct staged `mirna` nodes when they are not true existing ENST transcript identities;
- allow `mirna_targets_gene` for source-native gene-level validated target rows;
- allow `mirna_targets_transcript` only for source-native transcript/UTR/site endpoints or a separately reviewed coordinate-to-transcript mapping;
- do not route mature miRNA target rows into `transcript_interacts_gene`;
- do not expand gene-level target rows to transcripts or proteins;
- keep protein-effect assays, CLIP support, reporter/protein readouts, prediction-only fields, and ceRNA/correlation fields as evidence/context unless they are native graph endpoints under a separately approved relation.

The approved relation target for these sources is therefore `mirna_targets_gene` only for validated human gene-level MTIs that resolve to canonical `gene` nodes (`ENSG...`). `mirna_targets_transcript` is not approved for miRTarBase/DIANA rows unless the exact export row gives transcript/UTR/site-native endpoints and passes transcript anti-join validation.

## Source access and schema inspection

Artifact summary: `artifacts/staged/t_407c41ec/prepare/source_access_and_schema_gate.json`.

### miRBase node/catalog support

Live `miRNA.dat` download succeeded from `https://mirbase.org/download/miRNA.dat`.

Observed/parsed schema fields:

- precursor/hairpin: `AC` accession (`MI...`), `ID` name (`hsa-mir-*`), HGNC/Entrez DR xrefs when present;
- mature product: `FT miRNA` entries with `/accession="MIMAT..."` and `/product="hsa-miR-*-5p/3p"`;
- species filtered to human (`hsa`) by parser.

Counts from live parse:

- miRBase human catalog rows: 4,573;
- precursor/hairpin rows: 1,917;
- mature rows: 2,656;
- conservative ENST↔miRBase mapping rows: 644, via canonical `gene_has_transcript` + HGNC fallback after live BioMart miRNA-xref query returned 0 rows.

Staged support artifacts written for mapping audit only:

- `artifacts/staged/t_407c41ec/raw/miRNA.dat`
- `artifacts/staged/t_407c41ec/prepare/mirbase_catalog.parquet`
- `artifacts/staged/t_407c41ec/prepare/transcript_mirbase_mapping.parquet`

These are not target edges and were not promoted canonically.

### miRTarBase

Expected schema from project policy/code path (`manage_db.prepare_real_mirna_sources.normalise_mirtarbase`) for miRTarBase 9.0 MTI XLSX:

- organism fields: `Species (miRNA)`, `Species (Target Gene)`;
- miRNA endpoint: `miRNA` mature name, resolved against release-pinned miRBase mature catalog to `MIMAT...`;
- target endpoint: `Target Gene`, `Target Gene (Entrez ID)` mapped to canonical `ENSG...` gene nodes through BioMart/unique gene-symbol mapping;
- source/evidence fields: `miRTarBase ID`, `Experiments`, `Support Type`, `References (PMID)`;
- endpoint level: gene-level only for this path, so candidate relation is `mirna_targets_gene`.

Live source access did not pass today:

- attempted public URL: `https://mirtarbase.cuhk.edu.cn/~miRTarBase/miRTarBase_2025/cache/download/9.0/miRTarBase_MTI.xlsx`;
- Python `requests`: TLS handshake failure;
- `curl -L -k` with HTTP/1.1/user-agent/TLS variants: empty reply from server;
- no local cache was found under the workspace.

Decision: do not emit miRTarBase target edges/evidence from undocumented or fabricated rows. The source remains recommended by policy once a real export is available, but this run could not verify the live XLSX schema/license/export payload.

### DIANA-TarBase v8

Live page access succeeded for the DIANA download form:

- URL: `https://dianalab.e-ce.uth.gr/html/diana/web/index.php?r=tarbasev8%2Fdownloaddataform`;
- saved HTML: `artifacts/staged/t_407c41ec/raw/diana_tarbase_download_form.html`.

Observed page fields from HTML inspection:

- form action: `https://dianalab.e-ce.uth.gr/html/diana/web/index.php?r=site/test-mailer`;
- inputs include `_csrf`, `fullname1`, `email1`, `subscribe1`, and `tool1`;
- no direct static bulk export URL was identified from the form HTML in this run.

Expected source schema from project policy/proposal, pending direct export confirmation:

- organism/species fields;
- miRNA name/ID;
- target gene/gene identifier;
- experimental method/support type;
- cell/tissue/cell-line/context;
- regulation direction/validation type where provided;
- PMID/source record.

Decision: defer DIANA-TarBase ingestion until export terms and a direct bulk data payload are confirmed. Do not stage DIANA-derived edges from a form-only page.

## Endpoint namespace mapping

Approved mapping rules applied in this gate:

- miRNA regulator (`x_id`): mature miRBase accession (`MIMAT...`) as staged `mirna` node for target edges; precursor/hairpin (`MI...`) only as catalog/mapping support unless a row explicitly targets that entity;
- gene target (`y_id`): canonical KG gene node (`ENSG...`) after exact Entrez or high-confidence unique gene-symbol mapping;
- transcript target (`y_id`): canonical KG transcript node (`ENST...`) only if source-native transcript/UTR/site endpoint exists; no gene→all-transcripts expansion;
- protein endpoint: not used for these sources; western blot/protein readouts remain evidence fields only.

Canonical endpoint tables checked/available for future anti-joins:

- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/gene.parquet`
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/nodes/transcript.parquet`
- `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2/edges/gene_has_transcript.parquet`

## Pilot outcome

No `mirna_targets_gene` or `mirna_targets_transcript` edge/evidence Parquets were emitted in this task.

Reason: target-source gate failed before endpoint validation could run on real target rows:

- miRTarBase target XLSX was not retrievable from this environment;
- DIANA-TarBase only exposed a download request/contact form, not a verified bulk payload/license path;
- the acceptance criteria require direct validated target assertions and endpoint anti-join proof, so zero target rows is the only honest staged outcome.

Counts:

| Item | Count |
|---|---:|
| miRBase human catalog rows | 4,573 |
| miRBase precursor/hairpin rows | 1,917 |
| miRBase mature rows | 2,656 |
| conservative transcript-miRBase mapping rows | 644 |
| miRTarBase target rows accepted | 0 |
| DIANA-TarBase target rows accepted | 0 |
| `mirna_targets_gene` edges/evidence | 0 / 0 |
| `mirna_targets_transcript` edges/evidence | 0 / 0 |

## Downgrade / exclusion decisions

- CLIP/Ago support fields are evidence/context, not transcript endpoints unless source-native transcript/UTR/site mapping is present and reviewed.
- Reporter assays and western blot/protein readouts are evidence fields, not `mirna_targets_protein` or protein endpoint edges.
- Prediction-only, ceRNA, correlation, and context-only fields are not mechanism edges under this policy.
- Gene-level MTIs must remain `mirna_targets_gene`; they must not be routed into `transcript_interacts_gene`, `mirna_targets_transcript`, or protein edges.

## Files written

- Report: `docs/mirtarbase_diana_mirna_target_gate_t_407c41ec.md`
- Source/access gate JSON: `artifacts/staged/t_407c41ec/prepare/source_access_and_schema_gate.json`
- Raw miRBase download: `artifacts/staged/t_407c41ec/raw/miRNA.dat`
- Raw DIANA form snapshot: `artifacts/staged/t_407c41ec/raw/diana_tarbase_download_form.html`
- Mapping audit Parquets:
  - `artifacts/staged/t_407c41ec/prepare/mirbase_catalog.parquet`
  - `artifacts/staged/t_407c41ec/prepare/transcript_mirbase_mapping.parquet`

No canonical writes were performed and no `.omoc` outputs were created by this task.
