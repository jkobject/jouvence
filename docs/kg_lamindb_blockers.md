# KG / LaminDB blockers

Last updated: 2026-06-11

This file is the running list of questions that block TxGNN/Jouvence KG completion.

## Open Questions

- GCS remote verification in unauthenticated shells still needs ADC/project auth
  for `jkobject-1549353370965`; unauthenticated `gsutil` can fail with 401.
- Remaining expanded-KG coverage work excludes the now-promoted safe variant
  disease/gene/protein-change slices; next slices should be chosen from still
  missing schema files in `docs/kg_coverage_audit.md`.

## Execution Notes

- 2026-06-11: Human organism slice promoted. Added `nodes/organism.parquet` with `NCBITaxon:9606`, `edges/organism_has_gene.parquet` with `109,325` rows, and `edges/organism_has_tissue.parquet` with `16,061` rows. Targeted endpoint validation reports zero dangling organism/gene/tissue endpoints, and `bionty.Organism` parity reports `missing_ids=0`. The same full canonical parity audit exposed remaining non-target registry gaps that block final completion: `transcript` missing `507,365`, `gene` missing `30,604`, `molecule` missing `21,672`, `pathway` missing `1,566`, `tissue` missing `291`, and `cell_type` missing `76`.

- 2026-06-11: Canonical ontology separator normalization completed scratch-first. Affected disease and cell-type node IDs plus all disease/cell-type endpoint columns were rewritten from underscore forms (`EFO_...`, `MONDO_...`, `CL_...`, etc.) to CURIE forms in `/mnt/gcs/jouvencekb/kg/v2`; pre-normalization files were backed up under `/mnt/gcs/jouvencekb/kg/local-archive/canonical-v2-pre-ontology-id-normalization-20260611T113134Z`. Targeted canonical validation reports `0` missing selected endpoints and `0` remaining underscore selected endpoints; disease parity reports `missing_ids=0`. Disease node rows are now `41,859` after collapsing `11,030` duplicate normalized IDs.

- 2026-06-11: `mutation_associated_disease` promoted after custom disease registry parity was available. Merged archived known-variant and GWAS disease evidence into canonical `/mnt/gcs/jouvencekb/kg/v2`: disease nodes increased `48,291 → 52,889` (`+4,598` rows) and `edges/mutation_associated_disease.parquet` now has `4,656,171` rows (`3,807,475` known-variant + `848,696` GWAS, no duplicates). Targeted endpoint validation reports `0` missing mutation endpoints and `0` missing disease endpoints; canonical disease sync created `3,536` additional `lnschema_txgnn.Disease` records, and parity audit reports `missing_ids=0` for canonical disease and mutation nodes.

- 2026-06-11: Disease registry policy unblocked for KG parity. OpenTargets underscore IDs are syntax-normalized (`EFO_0000094` → `EFO:0000094`, `MONDO_...` → `MONDO:...`, `HP_...` → `HP:...`). Live `bionty.Disease` remains MONDO-backed, so TxGNN now uses custom `lnschema_txgnn.Disease` keyed by normalized source ontology ID for KG disease nodes and still does not insert EFO/OBA/HP/Orphanet/GO/MP/NCIT disease-like IDs directly into `bionty.Disease`. Migration `0005_custom_disease` deployed live and canonical `/mnt/gcs/jouvencekb/kg/v2` disease sync created `38,323` custom disease records; parity audit reports `missing_ids=0` for canonical disease nodes. `mutation_associated_disease` promotion is complete in canonical GCS with zero-dangling targeted endpoint validation and passing disease/mutation parity.
- 2026-06-10: OMX parallel lanes were attempted for LaminDB completion and GCS promotion. `lnschema_txgnn` migration `0004_protein` completed successfully and created `lnschema_txgnn_protein`. The initial GCS promotion lane was stopped because it materialized/concatenated too much canonical KG state under 5G cgroup pressure and stopped making file progress; this is an implementation strategy issue, not a user-facing blocker. Continue with bounded one-lane streaming promotion/sync.
- 2026-06-10: `sync_parquet_nodes_to_lamindb` was patched to bulk-create custom `lnschema_txgnn.*` records in bounded batches. Live sync wrote `233,995` protein records total (`1,966` from an interrupted per-row run plus `232,029` bulk-created), `2,165,367` combined-scratch mutation records, and `422,685` additional GWAS mutation records. Parity now passes for combined protein/mutation and GWAS mutation/gene.
- 2026-06-10: Safe GCS promotion completed using ADC-token `gcloud storage cp` after unauthenticated `gsutil` failed. Promoted files: `nodes/mutation.parquet` (`2,589,509` unioned mutation rows), `edges/mutation_causes_protein_change.parquet` (`177,735` rows), and `edges/mutation_associated_gene.parquet` (`535,093` rows). Full canonical streaming validation passed: `6,562,289` nodes, `27,014,101` edges, `total_dangling_edges: 0`.

- 2026-06-11: LaminDB cloud path/parity pass. `sync_parquet_nodes_to_lamindb` now
  skips an explicit `ln.connect("jkobject/jouvencekb")` hub refresh when that slug
  is already current, avoiding stale hub metadata that resolves SQLite to the
  wrong `gs://jouvencekb/.lamindb/lamin.db` path instead of the actual storage
  root `gs://jouvencekb/lamin/.lamindb/lamin.db`. Canonical GCS parity was
  repaired without `/home/ubuntu/data`: created `30,851` missing canonical paper
  records and `1,456` remaining gnomAD-like mutation records, plus reconciled
  gnomAD-like IDs onto existing rsID mutation rows where needed. Targeted parity
  now passes for canonical `paper`, `mutation`, and `protein` nodes with
  `missing_ids=0`.

- 2026-06-10: Paper registry sync completed for
  `/mnt/gcs/jouvencekb/kg/local-archive/home-ubuntu-data-txgnn-20260611T0940Z/txgnn-literature.tar.zst (retired literature KG)`. Initial live
  `lnschema_txgnn.Paper` count was `1`. A long first bulk write was killed
  after creating `3,850,000` paper records; the bounded resume created the
  remaining `325,039`. Final dry-run sync reports `seen=4,175,039`,
  `existing=4,175,039`, `would_create=0`, and live
  `lnschema_txgnn.Paper.objects.count()` is `4,175,040` because pre-existing
  PMID `37778123` is not present in that literature node file. Local literature
  KG validation passed with `4,340,155` nodes, `5,848,026` edges, and
  `total_dangling_edges=0`.

## Current Doctrine

- A KG slice is only done when clean Parquet nodes/edges are promoted to canonical/versioned GCS and validate with zero dangling edges, and the corresponding node IDs are represented in LaminDB/bionty/custom registries.
- TxGNN `protein` nodes are Ensembl Protein translation products (`ENSP`) stored in custom `lnschema_txgnn.Protein`.
- `uniprot_id` is an xref on `lnschema_txgnn.Protein`, not the primary identity.
- Non-bionty entities and TxGNN disease source terms use custom `lnschema_txgnn.<Object>` registries.
- Safe variant directions only: `mutation_causes_protein_change` is mutation→protein, `mutation_associated_disease` is mutation→disease, and `mutation_associated_gene` is mutation→gene. Do not materialize inverse edges for simple mappings.

## Resolved Decisions

- 2026-06-11: TxGNN disease KG nodes are represented in `lnschema_txgnn.Disease` by normalized source ontology ID. Do not direct-insert non-MONDO disease IDs into MONDO-backed `bionty.Disease`; add exact MONDO mappings later only as xrefs/equivalence-backed enrichment.
- 2026-06-10: Do not use `bt.Protein` as the primary registry for ENSP nodes. A future optional xref/link to `bt.Protein` can be added for UniProt-backed proteins.
- 2026-06-10: Promote only the safe variant relations with validated endpoints. Do not promote full all-variant `mutation_in_gene` or `mutation_affects_transcript`.

## 2026-06-10 disease variant completion pass

- `EFO_0000094`-style OpenTargets IDs are syntactically canonicalized to CURIE form (`EFO:0000094`) for disease evidence paths. This is a syntax normalization only; it does not prove bionty source support.
- Live bionty inspection found `bt.Disease` fields include `ontology_id`, `name`, `abbr`, `synonyms`, and `description`; ontology IDs are MONDO-backed in this instance (`MONDO:` count `30,371`; `EFO:` and `EFO_` counts `0`).
- Historical note: code previously refused missing non-MONDO `bionty.Disease` direct inserts; this is superseded by the 2026-06-11 custom `lnschema_txgnn.Disease` registry policy.
- Historical note: local normalized endpoint checks showed zero dangling disease endpoints inside the scratch roots; `mutation_associated_disease.parquet` was promoted on 2026-06-11 after custom disease registry parity was available.

## 2026-06-11 Task 26/27 parity resolution: custom exact-ID registries

Task 26 repaired the custom `lnschema_txgnn.Transcript` gap by syncing all
canonical `nodes/transcript.parquet` ENST IDs into LaminDB; the targeted parity
audit now reports `transcript missing_ids=0`.

The remaining canonical gaps were not safe to repair through the public
bionty/pertdb write APIs in the current environment:

- `bionty.Gene` writes for missing ENSG IDs can resolve by same gene symbol and
  mutate an existing source-backed row from an Ensembl ID to an `NCBI:<id>` value.
- `pertdb.Compound` writes for missing ChEMBL IDs can resolve by same/similar
  compound name and mutate an existing DrugBank/other row to the ChEMBL ID.
- The same public-registry exact-ID risk applies to `bionty.Pathway`,
  `bionty.Tissue`, and `bionty.CellType` unless a lower-level exact-ID insertion
  policy is approved.

Jérémie approved the safe policy on 2026-06-11: represent those exact KG primary
IDs in custom TxGNN registries rather than mutating public bionty/pertdb rows.
The live schema now includes `lnschema_txgnn.Gene`, `Molecule`, `Pathway`,
`Tissue`, and `CellType`; `manage_db.sync_parquet_nodes_to_lamindb` maps those
node types to the custom registries and bulk-creates them safely.

Evidence files:

- `.omoc/reports/lamindb-parity-after-task26-repair-*.json`
- `.omoc/reports/lamindb-public-registry-write-block-task26-*.json`
- `.omoc/reports/lamindb-gene-side-effect-repair-*.txt`

Historical targeted parity before custom-registry repair:

- `transcript`: `missing_ids=0`
- `gene`: `missing_ids=30,604`
- `molecule`: `missing_ids=21,672`
- `pathway`: `missing_ids=1,566`
- `tissue`: `missing_ids=291`
- `cell_type`: `missing_ids=76`

Hermes verification after the custom-registry repair:

- Command: `uv run python -m manage_db.audit_lamindb_parity /mnt/gcs/jouvencekb/kg/v2 --node-types gene molecule pathway tissue cell_type transcript disease protein paper mutation organism --json`
- Evidence: `.omoc/reports/hermes-parity-custom-registries-*.json`
- Result: `missing_ids=0` for all audited canonical node types.

Final TxGNN smoke is no longer blocked by LaminDB parity. Hermes ran the final
tiny model smoke on 2026-06-12 under `CPUQuota=200%` and `MemoryMax=4G`; it
completed successfully with peak memory `449.1M`. Evidence:
`.omoc/reports/hermes-final-txgnn-tiny-smoke-20260612T182202Z.txt`.
The reproducible wrapper `scripts/run_final_txgnn_tiny_smoke_systemd.sh` was
verified on 2026-06-14 and completed with peak memory `389.6M`; evidence:
`.omoc/reports/hermes-final-txgnn-tiny-smoke-wrapper-*.txt`.
