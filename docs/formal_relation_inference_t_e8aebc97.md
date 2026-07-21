# Expanded formal relation inference rerun — `t_e8aebc97`

Status: **staged-only / review-required**

No canonical, observed-edge, cloud, VM, GCS/FUSE, or LaminDB write occurred.

## Accepted immutable input gate

The rerun consumed only the independently accepted parent `t_abbfe5e7` artifact at producer revision `69caf8d9cd75ae547c832a670e523339e78e4e6c` (PR #32, reviewer `approved=true`). Fresh readback matched the accepted handoff exactly:

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `edges/molecule_targets_protein.parquet` | 2,119 | `08b5b4f2abdd4f92c4512f889fb18abe1dedc6a024147b99df09b7da447ced91` |
| `evidence/molecule_targets_protein.parquet` | 2,132 | `afe5ed235e9c109940a9009d47a88d66d829d7067992aba8b7fa300ef4aa5a88` |
| `edges/disease_associated_protein.parquet` | 3,243 | `1371f0e627e0cc7db32714864aeaeabbd7b7f2e7ba3aa30b0723ee1ef33eec3d` |
| `evidence/disease_associated_protein.parquet` | 35,839 | `6a3cb7a53fd0a0ab55071f5e806ad92ede52b2e6c25926ac99d3cbdfe3a6d352` |

The executor's fresh input-manifest digest is `01c8b5c99f1103714890f05520fcb07044ffe95912d78f18e75309122c827727`.

## Implementation delta

The allowlisted executor now:

- reads the accepted plural materialized fields (`action_direction`, `target_modulation`, `action_types`, `causal_mechanisms`, and `effect_directions`) without treating compatible representations such as `negative`, `decrease`, and `inhibitor` as a conflict;
- honors aggregate `action_status`, `mechanism_status`, and `effect_direction_status` fail-closed;
- emits separate signed treatment and contraindication rules for both gene and protein targets using the three-operand algebra `p = action × disease mechanism × disease outcome direction`; `p = -1` is therapeutic and `p = +1` is harmful;
- preserves source releases, input snapshot hash, context compatibility, sign computation, epistemic class, conflict state, premise paths/evidence IDs, and anti-join receipts in inferred evidence;
- keeps disease mechanism and disease outcome direction as distinct required operands: agonist/increase and GoF/risk are `+1`, inhibitor/decrease and LoF/protective are `-1`; missing, unknown, or conflicting operands fail closed with no one-dimensional fallback;
- records bounded rejected-path samples, including full typed premises, instead of hiding zero-output reasons;
- treats legacy contraindication edges without direct evidence as an incomplete canonical anti-join inventory;
- validates contraindication anti-join completeness only from an accepted `canonical-target-inventory-v1` receipt bound to the exact relation, snapshot/source identity, edge/evidence file hashes, edge-key-set hashes, and zero gap/orphan coverage counts.

The receipt is expected at `manifest/canonical_target_inventory/molecule_contraindicates_disease.json` under the immutable input root. Its `receipt_sha256` is recomputed over the complete receipt payload excluding that field and must equal the independently accepted hash supplied as `BuildConfig.canonical_target_inventory_receipt_sha256` or CLI `--canonical-target-inventory-receipt-sha256`. The executor likewise requires the independently accepted source identity explicitly (`BuildConfig.canonical_target_inventory_source_identity` or CLI `--canonical-target-inventory-source-identity`) rather than equating it with the inference-policy revision. Missing, empty, unrelated, partial, stale, malformed, self-hash-mismatched, accepted-hash-mismatched, source-mismatched, or evidence-file-hash-mismatched inventories fail closed as `canonical_target_inventory_missing`. A validated receipt hash is preserved on every inferred evidence row that survives strict anti-join.

The production tree remains atomic: a rerun that yields zero replaces the prior rule-owned tree and removes stale inferred Parquets.

## Bounded exact-snapshot pilot

The local pilot ran all 24 inferred-edge templates with `max_rows_per_file=50,000`, `max_paths_per_template=5,000`, `sample_limit=10`, and required canonical target inventories for any candidate surviving semantic gates. Derived/coherence views were intentionally excluded because this card permits only inferred edge/evidence outputs.

Two consecutive runs produced identical input-manifest hashes, per-rule counts, rejection counts, and rejected samples.

- templates evaluated: **24**
- inferred edge rows: **0**
- inferred evidence rows: **0**
- observed `edges/` or `evidence/` outputs: **0**
- derived-view outputs: **0**
- signed protein paths evaluated per signed endpoint rule: **701**
- `signed_protein_target_treatment_v2`: **701 rejected** as `missing_sign_or_causal_support`
- `signed_protein_target_contraindication_v2`: **701 rejected** as `missing_sign_or_causal_support`

All 24 templates are honest zero-output rules on this exact snapshot. Twenty-two have no complete premise inventory locally. The two protein signed rules have complete endpoint joins, but all 3,243 protein-disease edges retain unknown mechanism and effect direction; therefore none may become treatment or contraindication. The zero result is the required fail-closed scientific result, not a failed build.

No canonical target anti-join was bypassed. No candidate reached anti-join because semantic polarity/causal-support gates rejected every complete signed path. The exact accepted parent contains no validated contraindication completeness receipt, so its legacy/provenance-free pairs cannot authorize strict contraindication inference.

## Human-readable rejected paths

Each path below is a **plausible hypothesis rejected for missing source-backed disease sign/causal support**, not a treatment claim and not a novelty claim. The accepted parent contains only the protein signed family, so honest cross-family stratification is impossible without fabricating absent mutation, mapping, expression, pathway, phenotype, tissue, or pharmacogenomic premises.

1. `CHEMBL1068 -> ENSP00000390600 -> MONDO:0014246`
2. `CHEMBL1068 -> ENSP00000396320 -> MONDO:0008195`
3. `CHEMBL1068 -> ENSP00000396320 -> MONDO:0008224`
4. `CHEMBL1068 -> ENSP00000396320 -> MONDO:0018959`
5. `CHEMBL107 -> ENSP00000259818 -> Orphanet:300573`
6. `CHEMBL107 -> ENSP00000264071 -> Orphanet:98805`
7. `CHEMBL1089636 -> ENSP00000259818 -> Orphanet:300573`
8. `CHEMBL1089636 -> ENSP00000264071 -> Orphanet:98805`
9. `CHEMBL108 -> ENSP00000390600 -> MONDO:0014246`
10. `CHEMBL108 -> ENSP00000396320 -> MONDO:0008195`

The machine report stores typed relation names, all premise edge/evidence IDs, source releases, sign computation, and complete reject reasons for these samples.

## Local staged artifacts

Task-local control artifacts are under `artifacts/staged/t_e8aebc97/manifest/`:

- `input_manifest.json` — SHA-256 `9ac5ffaf591d817f4cbdd82f4085026c5cee83d50e3ac07534801f0b4b8ff878`
- `pilot_report.json` — SHA-256 `e5e5223d33feefb7f06b4cb578cd1886b2eb1933de95622d93ac30871be8a7b5`
- `template_registry_v2.json` — SHA-256 `e23e34dfe51e3a568b2ee9e928ed6ddce4c8395bcac540c2b03dfcf03bb45e1a`

Because every rule emitted zero, `edges_inferred/` and `evidence_inferred/` contain no Parquets and stale outputs are absent.

## Validation

Focused TDD tests cover:

- compatible plural action representations;
- treatment versus contraindication sign routing;
- the complete agonist/inhibitor × GoF/LoF × risk/protective truth table, including `agonist × LoF × risk => treatment` and `agonist × LoF × protective => contraindication`;
- missing, unknown, or conflicting mechanism/direction aggregate states yielding zero claims;
- aggregate mechanism conflict failing closed;
- unknown parent-shaped disease sign yielding zero;
- source releases and snapshot hash preservation;
- context/sign/conflict/epistemic/anti-join provenance;
- ten bounded human-readable rejected paths;
- existing context conflicts, direct-versus-evidence conflicts, unknown sign, circular reuse, duplicate inflation, shared-phenotype exclusion, pathway fanout, mapping ambiguity, and rerun-to-zero deletion gates.
- absent, empty, unrelated, partial, stale, malformed, receipt-self-hash-mismatched, accepted-receipt-hash-mismatched, source-identity-mismatched, and evidence-hash-mismatched contraindication inventories, plus one exact complete accepted receipt.

Final exact commands and pass counts are recorded in the Kanban handoff.
