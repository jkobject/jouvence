# SV-PILOT TOFIX staged source-native structural-variation sample

Task: `t_eabf0eec`
Fixes producer: `t_15ac808c`
Date: 2026-07-08
Status: staged-only / review-required

## Scope and guardrails

This tofix reruns the tiny SV pilot using actual source-native dbVar VCF structural-variation records rather than ClinVar `CLNVC` deletion/duplication class rows. It did not write canonical KG data, did not promote edges/evidence/proof/nodes, did not run LaminDB/PyG/GNN/embedding/ReMap/all-relation work, and did not use macOS GCS-FUSE.

Preflight/runtime evidence:

- Launch/inspection used `gcloud compute ssh txgnn-worker --zone=europe-west1-b` from the Mac.
- Worker `hostname`: `txgnn-worker`.
- Related process check before launch found no active `sv-pilot|structural|clinvar|dbvar|gnomad|dgv|decipher|t_eabf0eec` writer/process.
- Remote worker initially had no `uv` on PATH; this run installed user-local `uv 0.11.28` under `/home/jkobject/.local/bin/uv` and invoked the bounded stdlib script through `uv run --no-project`.
- `run_manifest.json` records `uv_invocation="uv run --no-project /tmp/t_eabf0eec_build_sv_pilot.py"`.
- Forbidden path guard: the script aborts if the output path starts with `/Users/jkobject/mnt/gcs`; the manifest records outputs under `/tmp/t_eabf0eec_sv_pilot` on `txgnn-worker` before copy-back to local staged artifacts.

## Outputs

Staged artifacts are under:

- `artifacts/staged/t_eabf0eec/`

Files:

- `build_sv_pilot.py` — bounded stdlib builder invoked remotely through `uv run --no-project`.
- `run_manifest.json` — host/path/counts/uv/preflight evidence.
- `source_license_manifest.json` — source/license/access manifest with URLs, checked timestamps, status/headers where available, and terms caveats.
- `sv_nodes.jsonl` — 5 dbVar GRCh38 source-native SV mutation-node sample rows selected by VCF `INFO/SVTYPE`, symbolic ALT, `INFO/END`, and length >= 50 bp.
- `sv_evidence.jsonl` — 5 dbVar source-native SV evidence sidecar rows preserving source record metadata.
- `sv_edge_candidates.jsonl` — present but empty because the sampled dbVar records did not expose source `GENEINFO`; no endpoint claims were inferred from coordinates.
- `schema_conformance_report.json` — field-level node schema checks and verification of source-native SV selection criterion.
- `endpoint_antijoin_report.json` — records that canonical anti-join was not run and no candidate edges are canonical-ready.
- `assembly_liftover_report.json` — source-native GRCh38 preserved; no liftOver attempted.
- `duplicate_overlap_report.json` — exact evidence dedupe keys; graph assertion dedupe separate from evidence; no blind interval merge performed.
- `no_go_reject_report.json` — explicit rejected/no-go cases.
- `dbvar_sample_headers.txt` — selected VCF header provenance lines including `SVTYPE`, `END`, `SVLEN`, and `DBVARID` definitions when present.

## Source/license/access manifest summary

`source_license_manifest.json` records bounded checks for:

- dbVar by-study index — primary NCBI public dbVar archive; preserve study/submitter/source IDs and controlled-access caveats.
- dbVar `dstd1.GRCh38.variant_call.vcf.gz` — source sampled for records with native VCF `INFO/SVTYPE`, symbolic ALT (`<DEL>` in this sample), `INFO/END`, and length >= 50 bp.
- dbVar `dstd1.meta.tsv.gz` — small study metadata sidecar noted for provenance.
- ClinVar maintenance/use — open NCBI clinical assertion archive; not used for row sampling in this fix.
- ClinGen terms — public curated resource requiring citation/attribution; not bulk fetched.
- gnomAD terms — population source; terms must be rechecked before ingestion; not sampled here.
- DGVa about — open EVA/DGVa context; not sampled here.
- DECIPHER data sharing — restricted/license-gated no-go without explicit approval; not sampled.

## Sample contents and selection criterion

The source-backed node sample is a tiny dbVar GRCh38 streamed VCF subset selected by actual VCF structural-variation fields:

- source: `https://ftp.ncbi.nlm.nih.gov/pub/dbVar/data/Homo_sapiens/by_study/vcf/dstd1.GRCh38.variant_call.vcf.gz`
- criterion: records with source-native `INFO/SVTYPE` or symbolic ALT, source `INFO/END`, and computed/source length >= 50 bp.
- observed sample: 5 records, all dbVar `DEL` rows with symbolic ALT `<DEL>`, `INFO/END`, source `SVLEN`, and dbVar IDs `dssv2`, `dssv4`, `dssv8`, `dssv9`, `dssv12`.

Counts from `run_manifest.json`:

- nodes: 5
- evidence rows: 5
- edge candidates: 0
- rejected runtime records: 0

The pilot intentionally preserves source-native metadata and does not assert population, clinical, disease, enhancer, transcript, or gene truth beyond evidence sidecars. Because the sampled dbVar rows did not expose source `GENEINFO`, `sv_edge_candidates.jsonl` is empty rather than inventing coordinate-derived endpoint claims.

## Validation evidence

Schema conformance:

- `schema_conformance_report.json` checks required node fields: `id`, `node_type`, `source`, `variant_type`, `assembly`, `chromosome`, `start`, `end`, `source_url`, `source_variant_id`, `source_study_ids`, `length_bp`, and `source_info`.
- All 5 staged node rows passed.
- The report verifies every staged node has source `SVTYPE`, source `END`, and length >= 50 bp.

Endpoint anti-joins:

- `endpoint_antijoin_report.json` records `canonical_antijoin_run=false` because this tiny staged pilot did not read canonical KG endpoints.
- `sv_edge_candidates.jsonl` is empty because no source endpoint field was present in the sampled dbVar rows.
- `pass_for_canonical=false`; no unresolved or inferred endpoint is promoted.

Assembly/liftOver:

- `assembly_liftover_report.json` records source-native `GRCh38` for all 5 node rows.
- LiftOver status is `not_attempted_source_native_grch38_preserved`.
- No ambiguous or unsupported lifted coordinate was used for a relation.

Duplicate/overlap:

- `duplicate_overlap_report.json` records exact evidence dedupe keys over `(source, source_release, source_variant_id, subject_id, evidence_type)`.
- No exact duplicate evidence rows were produced.
- Evidence dedupe is explicitly separate from graph assertion dedupe.
- Near-duplicate interval clustering/merging was not performed; no rows were blindly interval-merged.

No-go/reject cases:

- DECIPHER/restricted sources: rejected/no-go without explicit license approval.
- Unknown assembly coordinate relations: rejected; emitted rows are source-native GRCh38.
- Ambiguous liftOver: rejected/not attempted.
- Population-frequency-as-pathogenicity: rejected; no population frequency translated to disease truth.
- Coordinate-only enhancer observed-regulation claims: rejected; no enhancer edges emitted.

## Limitations and reviewer notes

- This is intentionally tiny and dbVar-centered. ClinVar, ClinGen, gnomAD, DGV/DGVa, and DECIPHER are represented by manifest/caveats, not by bulk ingestion.
- The sample is source-native SV/CNV evidence and fixes the prior CLNVC-only issue, but it is not full SV source coverage.
- No canonical endpoint anti-join was attempted against live KG nodes because that would require canonical KG reads beyond this tiny staged pilot. All candidate edge promotion remains blocked.
- No canonical promotion should occur before separate reviewer acceptance.
