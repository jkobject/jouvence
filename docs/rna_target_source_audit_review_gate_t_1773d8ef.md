# RNA target source audit fan-in review gate

Task: `t_1773d8ef`  
Status: review gate decision; no canonical KG writes.

## Gate decision

Approved as a source-audit/policy fan-in gate, not as approval for canonical RNA-target edges.

No reviewed child produced a policy-valid non-empty active edge/evidence candidate for the current KG. The only accepted outputs are audit reports, source-schema summaries, mapping/support artifacts, and context/sidecar recommendations under `docs/` and `artifacts/staged/<task-id>/`.

Do not promote any RNA target relation from this fan-out to canonical `gs://jouvencekb/kg/v2` yet.

## Evidence reviewed

- Policy gate: `docs/rna_target_policy_t_f5016884.md`.
- Parent blocker report: `docs/transcript_rna_relation_blockers_t_40a66443.md`.
- POSTAR3/ENCORI audit: `docs/rbp_postar_encori_endpoint_audit_t_deed17cc.md` and `artifacts/staged/t_deed17cc/`.
- NPInter/RNAInter audit: `docs/npinter_rnainter_direct_experimental_audit_t_e76149bc.md` and `artifacts/staged/t_e76149bc/`.
- miRTarBase/DIANA/miRBase gate: `docs/mirtarbase_diana_mirna_target_gate_t_407c41ec.md` and `artifacts/staged/t_407c41ec/`.
- LncRNA2Target/LncTarD audit: `docs/lncrna2target_lnctard_audit_t_74dc3d9c.md` and `artifacts/staged/t_74dc3d9c/`.
- Prior independent reviewer acceptance for miRNA source/schema gate: reviewer card `t_d6ad6c13` accepted producer `t_407c41ec` as a zero-target-edge source/schema gate only.

## No-write / isolation checks

Checked the four child artifact directories for active edge/evidence outputs:

- `artifacts/staged/t_deed17cc/`: no `edges/`, `evidence/`, `candidate_kg/edges/`, or `candidate_kg/evidence/` directories.
- `artifacts/staged/t_e76149bc/`: no `edges/`, `evidence/`, `candidate_kg/edges/`, or `candidate_kg/evidence/` directories.
- `artifacts/staged/t_407c41ec/`: no `edges/`, `evidence/`, `candidate_kg/edges/`, or `candidate_kg/evidence/` directories.
- `artifacts/staged/t_74dc3d9c/`: no `edges/`, `evidence/`, `candidate_kg/edges/`, or `candidate_kg/evidence/` directories.

Workspace `.omoc` search found no `.omoc` paths under `/Users/jkobject/.openclaw/workspace/work/txgnn` during review.

Git reviewability remains limited: this `work/txgnn` directory is a shared workspace under the parent OpenClaw repo with unrelated dirty state, not an isolated TxGNN branch/worktree. Since this gate is docs/artifact review with no code/canonical promotion, this is not blocking for this card; code-heavy follow-up should use `/Users/jkobject/.openclaw/worktrees/txgnn/<task-or-branch>`.

## Child findings

### POSTAR3 / ENCORI RBP audit (`t_deed17cc`)

Verdict: accepted as audit/context-sidecar recommendation only; no edge candidate approved.

Evidence:

- POSTAR3 human RBP export streamed 31,190,710 rows, all 11-column BED-like coordinate rows.
- POSTAR target endpoint classification: coordinate-only BED intervals; `ENST` regex hits 0, RefSeq transcript hits 0.
- POSTAR RBP endpoint classification: gene symbol/name-only; UniProt/ENSP-like hits 0.
- ENCORI inspected RBP modules are query-scoped mRNA/lncRNA/circRNA/sncRNA/pseudogene/caRNA exports. Targets are gene/ncRNA/repeat scoped and RBP endpoints are symbols, not source-native protein identifiers.
- `artifacts/staged/t_deed17cc/rbp_binding_site_context_recommendation.json` reports `edge_candidate_rows: 0`, `evidence_candidate_rows: 0`, and recommends `rbp_binding_site_context`.

Gate decision: keep POSTAR/ENCORI out of `transcript_interacts_protein` until separate coordinate-to-transcript and RBP-symbol-to-protein projection policies pass. Context/sidecar path is appropriate.

### NPInter / RNAInter audit (`t_e76149bc`)

Verdict: accepted as source/audit sidecars only; no active relation candidate approved.

Evidence:

- NPInter v5 parsed counts: 2,580,617 computational rows and 15,566 experimental rows.
- RNAInter v4 parsed counts include RP 37,067,587 rows, RR 9,484,609 rows, RD 138,552 rows, RC 10,889 rows, and RH 1,060,684 rows.
- `artifacts/staged/t_e76149bc/endpoint_candidate_screen.json` active-relation screen is zero for all checked current-relation candidates:
  - NPInter experimental ENST+gene RNA-gene: 0.
  - NPInter experimental ENST+UniProt RNA-protein: 0.
  - NPInter RefSeq+UniProt needing transcript mapping: 0.
  - RNAInter RP ENST+UniProt/ENSP RNA-protein: 0.
  - RNAInter RP RefSeq+UniProt/ENSP needing mapping: 0.
  - RNAInter supported ENST+UniProt: 0.
  - RNAInter all ENST+gene RNA-gene-like: 0.
- Report downgrades computational/confidence-only, disease/chemical/histone/context, RNA-RNA/RNA-DNA, and subtype ncRNA rows to future relation/context buckets.

Gate decision: keep as source classification. Future staging needs explicit subtype RNA node/relation policy plus source-native endpoint mapping and source-of-source provenance.

### miRTarBase / DIANA-TarBase / miRBase gate (`t_407c41ec`)

Verdict: accepted as miRNA source/schema/access gate and miRBase mapping support only; not an accepted miRNA target-edge pilot.

Evidence:

- `artifacts/staged/t_407c41ec/prepare/mirbase_catalog.parquet` has 4,573 rows with precursor/mature miRBase support columns.
- `artifacts/staged/t_407c41ec/prepare/transcript_mirbase_mapping.parquet` has 644 conservative transcript-miRBase mapping rows.
- `artifacts/staged/t_407c41ec/prepare/source_access_and_schema_gate.json` reports miRTarBase target rows 0, DIANA-TarBase target rows 0, `mirna_targets_gene` edge/evidence 0/0, and `mirna_targets_transcript` edge/evidence 0/0.
- Live miRTarBase XLSX access failed in the producer/reviewer path; DIANA exposed a form page rather than a verified static bulk payload/license path.
- Report correctly keeps gene-level MTIs as future `mirna_targets_gene`, blocks routing into `transcript_interacts_gene`, and downgrades CLIP/Ago support, reporter/protein readouts, prediction-only, ceRNA, and correlation fields to evidence/context.

Gate decision: mapping support artifacts may inform later node/schema work, but no target-edge staging is approved until real miRTarBase/DIANA exports and license/access are obtained and validated.

### LncRNA2Target / LncTarD audit (`t_74dc3d9c`)

Verdict: accepted as source access/license/schema audit only; no active edge candidate approved.

Evidence:

- LncRNA2Target access/terms/schema were not verified: probed source endpoints refused/redirected.
- LncTarD 2.0 downloaded only with TLS verification disabled due certificate hostname mismatch; no explicit redistribution license was found in inspected pages.
- LncTarD table has 8,360 rows and 35 columns; lncRNA-regulator rows 7,773; lncRNA-to-PCG/TF rows 6,643.
- Endpoint anti-join artifact `artifacts/staged/t_74dc3d9c/reports/lnctard2_endpoint_antijoin.json` reports:
  - canonical gene node rows: 267,830;
  - canonical transcript node rows: 507,365;
  - no canonical `nodes/lncrna.parquet`;
  - unique target ENSG ids: 1,798, with 1,758 present and 40 missing from gene nodes;
  - unique regulator ENST ids: 15, all present in transcript nodes;
  - unique regulator ENSG ids: 835, of which 809 are present as gene nodes but invalid as lncRNA/transcript relation endpoints.
- Refined counts show many mixed classes: 2,913 ceRNA/sponge rows and 2,381 expression-association rows in the lncRNA-to-gene bucket.

Gate decision: block active `transcript_interacts_gene` staging. Use LncTarD only as future context/evidence input after explicit license review, lncRNA node/mapping policy, and relation-specific row-class splitting.

## Approved staged candidates

None for active KG edges.

Approved/accepted non-edge artifacts:

- `rbp_binding_site_context` recommendation for POSTAR3/ENCORI.
- NPInter/RNAInter source classification and endpoint-candidate screen sidecars.
- miRBase catalog and conservative transcript-miRBase mapping support artifacts.
- LncTarD schema/refined-count/endpoint anti-join audit artifacts.

## Rejected or blocked source paths

- POSTAR3 coordinate-only + RBP-symbol-only rows are blocked from `transcript_interacts_protein`.
- ENCORI RBP module rows are blocked from `transcript_interacts_protein` because inspected targets are gene/ncRNA/repeat scoped and RBP endpoints are symbols.
- NPInter/RNAInter direct active generic relation staging is blocked because active candidate screens found zero endpoint-valid current-relation rows.
- miRTarBase/DIANA target-edge staging is blocked by source access/license/export verification failure in this run.
- LncRNA2Target build is blocked by source access/terms/schema failure.
- LncTarD active edge staging is blocked by license/TLS ambiguity, lack of lncRNA node/mapping policy, mostly gene-level lncRNA regulator endpoints, and mixed disease/ceRNA/expression-association mechanism classes.

## Remaining policy/schema blockers

1. No approved mature miRNA node/relation implementation for production target edges yet; `mirna_targets_gene` remains a future relation path pending schema/node implementation and source export access.
2. No approved lncRNA node/mapping policy or `lncrna_regulates_gene` relation implementation for broad lncRNA regulation staging.
3. No coordinate-to-transcript mapping policy for CLIP/site rows.
4. No RBP gene-symbol-to-protein projection policy.
5. No RNA-RNA/RNA-DNA/context relation policy for the large subtype-specific NPInter/RNAInter buckets.
6. Source license/redistribution gates remain open for POSTAR, NPInter/RNAInter, miRTarBase/DIANA export payloads, LncRNA2Target, and LncTarD.

## Recommended next cards

1. CTO/schema card: decide and implement minimal `mirna`/mature-miRNA node plus `mirna_targets_gene` schema/tests, using the accepted miRBase mapping support as input.
2. Dev source-access card: obtain release-pinned miRTarBase and DIANA-TarBase exports/license evidence, then stage a bounded `mirna_targets_gene` candidate only if endpoint anti-joins and evidence fields pass.
3. CTO/schema card: decide lncRNA node/mapping policy and `lncrna_regulates_gene` relation before any broad LncTarD/LncRNA2Target build.
4. Dev source-access/license card: resolve LncTarD and LncRNA2Target redistribution/terms and build only a row-class split report or ENST-only smoke candidate after policy approval.
5. CTO/policy card: decide coordinate-to-transcript and RBP-symbol-to-protein projection gates before revisiting POSTAR/ENCORI as `transcript_interacts_protein`; otherwise build context sidecars only.

## Final gate

Approved: true for audit fan-in closure.  
Verdict: done.  
Approval scope: source audits and sidecar/mapping support only.  
Canonical promotion: not approved.  
Active RNA target edge candidates approved: 0.
