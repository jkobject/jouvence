# SV-PILOT staged structural-variation source sample

Task: `t_15ac808c`
Date: 2026-07-08
Status: staged-only / review-required

## Scope and guardrails

This is a tiny VM-run staged pilot following the accepted design in `docs/structural_variation_source_schema_design_t_baad8ddb.md`. It did not write canonical KG data, did not promote edges/evidence/proof/nodes, did not run LaminDB/PyG/GNN/embedding/ReMap/all-relation work, and did not use macOS GCS-FUSE.

Preflight evidence:

- Launch/inspection used `gcloud compute ssh txgnn-worker --zone=europe-west1-b` from the Mac.
- Worker `hostname`: `txgnn-worker`.
- Related process check before launch found no `sv-pilot|structural|clinvar|dbvar|gnomad|dgv|decipher|t_15ac808c` writer/process.
- Forbidden path guard: output script aborts if working/output path starts with `/Users/jkobject/mnt/gcs`; run manifest records no such path used.
- Remote caveat: `uv` was not on PATH on `txgnn-worker`, so the bounded pilot script used Python 3.10 stdlib only and records that caveat in `run_manifest.json`.

## Outputs

Staged artifacts are under:

- `artifacts/staged/t_15ac808c/`

Files:

- `run_manifest.json` — host/path/counts/caveats.
- `source_license_manifest.json` — live URL/access checks with checked UTC timestamp, status, content type/length where available, sample hashes, and terms caveats.
- `sv_nodes.jsonl` — 5 ClinVar GRCh38 mutation-node sample rows with source-preserved deletion/duplication metadata.
- `sv_evidence.jsonl` — 5 ClinVar clinical assertion sidecar rows.
- `sv_edge_candidates.jsonl` — 5 `mutation_in_gene` candidate rows from source `GENEINFO`; endpoints intentionally remain `gene_symbol:*` unresolved and are marked not canonical-ready.
- `schema_conformance_report.json` — field-level node schema checks.
- `endpoint_antijoin_report.json` — endpoint anti-join status for candidate edges.
- `assembly_liftover_report.json` — source-native GRCh38 preserved; no liftOver attempted.
- `duplicate_overlap_report.json` — exact evidence dedupe keys; no interval merge performed.
- `no_go_reject_report.json` — explicit rejected/no-go cases.
- `clinvar_sample_headers.txt` — selected VCF header provenance lines.

## Source/license/access manifest summary

`source_license_manifest.json` records live checks for:

- ClinVar maintenance/use page: reachable HTTP 200; public NCBI archive; preserve submitter/review status/condition/assertion provenance.
- ClinVar GRCh38 VCF: reachable HTTP 200; `application/x-gzip`, content length recorded as 192,290,992; only a tiny streamed sample was used.
- dbVar Homo sapiens by-study FTP index: reachable HTTP 200; public NCBI FTP index; preserve study/submitter attribution and controlled-access caveats.
- ClinGen terms and gene-dosage search: reachable HTTP 200; public resource requiring citation/attribution; no bulk export fetched.
- gnomAD terms: reachable HTTP 200; exact release/reuse terms still need reviewer/implementation recheck before any ingestion.
- DGVa about: reachable HTTP 200; EBI/EVA open-access context recorded; Toronto DGV-specific terms still need recheck before DGV-specific ingestion.
- DECIPHER data-sharing URL: HTTP 503 during this run, but preserved as restricted/license-gated no-go without explicit approval.

## Sample contents

The source-backed node sample is a tiny ClinVar GRCh38 streamed VCF subset selected by source-native `CLNVC` deletion/duplication class. Counts from `run_manifest.json`:

- nodes: 5
- evidence rows: 5
- edge candidates: 5
- rejected runtime fetch/parse records: 0

The pilot intentionally preserves source-native metadata and does not assert population or clinical truth beyond evidence sidecars. The sampled `mutation_in_gene` candidates are based on source `GENEINFO` fields only; they are not canonical-ready until symbols are normalized and anti-joined against canonical gene node IDs.

## Validation evidence

Schema conformance:

- `schema_conformance_report.json` checks required node fields: `id`, `node_type`, `source`, `variant_type`, `assembly`, `chromosome`, `start`, `end`, and `source_url`.
- All 5 staged node rows passed the pilot schema check.

Endpoint anti-joins:

- `endpoint_antijoin_report.json` contains 5 `mutation_in_gene` candidates.
- All are marked `anti_join_status=unresolved_symbol_not_canonical_id` and `pass_for_canonical=false` because this pilot did not read canonical gene nodes or promote edges.

Assembly/liftOver:

- `assembly_liftover_report.json` records source-native `GRCh38` for all 5 node rows.
- LiftOver status is `not_attempted_source_native_grch38_preserved`.
- No ambiguous or unsupported lifted coordinate was used for a relation.

Duplicate/overlap:

- `duplicate_overlap_report.json` records exact evidence dedupe keys over `(source, source_variant_id/source_study_id, subject_id, evidence_type)`.
- No exact duplicate evidence rows were produced.
- Near-duplicate interval clustering was not performed for the n=5 sample and no rows were merged.

No-go/reject cases:

- DECIPHER/restricted sources: rejected/no-go without explicit license approval.
- Unknown assembly coordinate relations: rejected; none emitted.
- Ambiguous liftOver: rejected/not attempted.
- Population-frequency-as-pathogenicity: rejected; no population frequency translated to disease truth.
- Coordinate-only enhancer observed-regulation claims: rejected; no enhancer edges emitted.

## Limitations and reviewer notes

- This pilot is intentionally tiny and ClinVar-centered. dbVar, ClinGen, gnomAD, and DGV/DGVa were represented by live access/terms checks and manifest caveats, not by bulk data ingestion.
- The ClinVar rows are deletion/duplication class rows from `CLNVC`, not necessarily large interval SV records with `INFO/SVTYPE`; they are sufficient to exercise the accepted source-preserving schema shape but should not be treated as full SV source coverage.
- `uv` is absent on the remote worker PATH. If strict `uv run` is required for future pilots, install/activate `uv` on `txgnn-worker` or provide the canonical repo environment there before rerunning.
- No canonical endpoint anti-join was attempted against live KG nodes because that would require canonical KG reads beyond this tiny staged pilot. Candidate endpoints are therefore explicitly non-canonical-ready.
