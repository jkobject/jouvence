# Source-backed disease causal operands — `t_causal_disease_operands`

Status: **staged feature enrichment built / review-required**

Base: accepted staged-only producer `69caf8d9cd75ae547c832a670e523339e78e4e6c` (PR #32). No canonical, cloud, VM, GCS/FUSE, or LaminDB write occurred.

## Extraction rules

The builder enriches the accepted `disease_associated_protein` rows without changing relation identities or source-row cardinality.

- UniProtKB reviewed DISEASE comments emit `gain_of_function` plus disease direction `risk` only for the strict source phrase `disease|disorder due to a gain-of-function defect`, with exact UniProt-accession-to-protein and disease-xref-to-disease mappings. The source must be exactly `UniProtKB`, and record ID and release must be non-empty. One source assertion on `ENSP00000361850 -> MONDO:0011136` satisfies this rule.
- UniProtKB humsavar emits disease direction `risk` for `LP/P` only when the row preserves an exact UniProt accession, canonical protein endpoint, source disease identifier, and exact disease mapping; the source must be exactly `UniProtKB/humsavar`, record ID and release must be non-empty, and the source record ID must equal the UniProt FTId. It emits no mechanism: pathogenicity and missense/consequence text do not establish GoF or LoF.
- `US` and `LB/B` remain unsigned. Benign is not protective.
- Mixed/non-canonical isoforms, missing variant or disease identity, ambiguous mappings, generic association, consequence-only rows, nearest-gene/LD, OpenTargets L2G, and absent source snapshots fail closed.
- Every assertion retains source family, record ID, release, exact mapping path, separate mechanism and disease-direction operands, confidence/support class, conflict flags, reject reason, and contract version.
- Evidence `relation|x_id|y_id` must reconstruct `edge_key` exactly and belong to one unique edge identity. Any inherited `materialization_assertion_conflict` marks both operands conflicting and can never produce `single`, `consensus`, or `both_operands_known=true`.
- Edge aggregation states remain exactly `single|consensus|conflicting|unknown`; inference must reject `conflicting` and `unknown`.

The bounded local inspection found no local ClinVar/OpenTargets raw snapshot with an exact variant-to-protein plus disease mapping beyond the accepted UniProt/humsavar evidence. That family is recorded with denominator 0 and `missing_local_source_snapshot`; no source fields were fabricated and no network fetch occurred.

## Exact staged delta

| Measure | Before | After |
| --- | ---: | ---: |
| disease edges | 3,243 | 3,243 |
| disease evidence rows | 35,839 | 35,839 |
| mechanism known | 0 | 1 |
| mechanism unknown | 3,243 | 3,242 |
| mechanism conflicting | 0 | 0 |
| disease direction known | 0 | 2,243 |
| disease direction unknown | 3,243 | 1,000 |
| disease direction conflicting | 0 | 0 |
| both operands known | 0 | 1 |
| joined molecule→protein→disease paths | 701 | 701 |
| joined paths with signed drug action | 637 | 637 |
| joined fully signed paths | 0 | 0 |

The one edge with both disease operands is not among the 701 current molecule-target joins. Therefore this snapshot truthfully improves source-backed operand coverage but still yields zero fully signed joined paths. This is a coverage result, not a biological or novelty claim.

## Source inventory

- UniProtKB reviewed DISEASE comments: 15,006 evidence rows, 3,243 distinct materialization assertions, 1 eligible/mapped explicit causal assertion, release `2026_02`.
- UniProtKB humsavar: 20,833 evidence rows/assertions, 18,412 eligible/mapped `LP/P` disease-direction assertions, 2,421 rejected as non-eligible, release `2026_02 of 10-Jun-2026`.
- ClinVar/OpenTargets local exact protein-native snapshot: absent; denominator 0, mapped 0.

Machine-readable field semantics, releases/licenses, denominators, mapped counts, and rejection reasons are in `artifacts/staged/t_causal_disease_operands/reports/source_operand_inventory.json`.

## Determinism and artifacts

Two clean task-local rebuilds produced byte-identical Parquets, identical semantic hashes, and identical coverage counts. The final files are:

- `artifacts/staged/t_causal_disease_operands/edges/disease_associated_protein.parquet`
  - SHA-256 `98c1b444efa2e3a0fcaecabed948c9752b52100d8cc8b9ec012c478a3f453dc2`
  - semantic SHA-256 `6f1ce8325d32450871912cbfd5dc7cfe2b772db6825726c3430e0b6fe54774d8`
- `artifacts/staged/t_causal_disease_operands/evidence/disease_associated_protein.parquet`
  - SHA-256 `0e125397708f8f8678984eeeeb99b803669e3838357b9025a2d1af5a4c8b9d12`
  - semantic SHA-256 `c7bd9ae64ba3d827f4a3d7a584859b882e2277c32e9754f20c2dd13631618c68`
- `reports/source_operand_inventory.json`
- `reports/coverage_before_after.json`
- `reports/materialization_manifest.json`
- `reports/determinism_check.json`
- `scripts/validate_staged_disease_causal_operands.py` independently re-derives operands and assertion metadata from raw assertions and rechecks endpoint types/key pairing, inherited conflicts, provenance consistency, aggregate derivation, source-inventory counts and field semantics, required input receipts, molecule input semantics, joined-path coverage, conservation, and hashes. It also requires the manifest task ID to match the candidate root, `staging_only=true`, `canonical_write=false`, and an exact four-receipt output inventory with descriptor paths equal to the expected task-local artifacts. Task IDs plus descriptor-relative exclusive writes (`O_NOFOLLOW`) contain every output beneath the local staging root even if a pathname is replaced concurrently.

The manifest records accepted input hashes, output hashes, staging-only status, conservation checks, and coverage. The determinism report records the independent two-run comparison and validator PASS on both clean roots. The invalid review-1 artifacts are retained as rejected evidence under `artifacts/staged/t_causal_disease_operands_rejected_review1/`; they are not the candidate.

## Missingness boundary

The accepted UniProt snapshot has one strict explicit GoF causal phrase and no accepted strict LoF phrase. Humsavar provides disease-specific pathogenicity but not functional mechanism. The builder intentionally does not reinterpret hypomorphic wording qualified by `probably`, pathogenicity classes, amino-acid consequences, generic disease descriptions, or relation direction as mechanisms. More signed joins require a separately reviewed source snapshot that explicitly supplies disease-specific functional mechanism on proteins already present in the 701-path join.
