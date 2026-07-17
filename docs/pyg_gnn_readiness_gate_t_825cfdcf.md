# PyG/GNN readiness gate — t_825cfdcf

Status: accepted with explicit limits. PyG is training-ready in architecture; production/full-scale training is still deferred to a separate VM/bucket-local compute job.

## Observable request

Gate the PyG readiness claim after the manifest, encoder policy, sampled/sidecar loader, and smoke-training cards. Reject shallow evidence, local full-training violations, unbounded `edge_index` loads, missing embedding mappings, and vague missing-feature policy. Produce wording that can truthfully say the architecture is training-ready without claiming full-scale training has already run.

## Evidence reviewed

- Parent QA report: `artifacts/reports/t_ef300535/qa_report.md`.
- Parent sidecar audit: `artifacts/reports/t_ef300535/sidecar_audit.json`.
- Parent bounded manifest: `artifacts/staged/t_ef300535/sidecar_molecule_targets_gene_64/manifest.json`.
- Parent smoke metrics: `artifacts/reports/t_ef300535/smoke_metrics_tree_monitored.json`.
- Producer readiness report: `/Users/jkobject/.openclaw/worktrees/txgnn/t_c40bdc86-pyg-readiness/docs/pyg_gnn_readiness_t_c40bdc86.md`.
- Producer worktree status/diff: `/Users/jkobject/.openclaw/worktrees/txgnn/t_c40bdc86-pyg-readiness`, branch `feat/t_c40bdc86-pyg-readiness`.
- Relevant code paths:
  - `manage_db/build_pyg_export.py`.
  - `manage_db/run_pyg_gnn_smoke.py`.
  - `tests/test_build_pyg_export.py`.
  - `tests/test_pyg_export_runbook_docs.py`.
- Re-run verification from the producer worktree:
  - `uv run python -m py_compile manage_db/build_pyg_export.py manage_db/run_pyg_gnn_smoke.py`
  - `uv run --group dev --group gnn pytest tests/test_build_pyg_export.py tests/test_pyg_export_runbook_docs.py -q`
  - observed: `14 passed, 2 warnings in 3.58s`.

## Gate verdict

Accepted.

The evidence supports this precise statement:

PyG is training-ready in architecture for Jouvence KG because the export path can produce sidecar/memmap graph artifacts, the smoke loader can train a relation-scoped bounded PyG model without requiring `heterodata/full_graph.pt`, manifest metadata records available embeddings and model-side fallback policy, and tests exercise the no-full-pickle / bounded-sidecar path. Full-scale multi-relation training on the whole KG has not been run and remains a separate reviewed compute job on `txgnn-worker` or another approved in-region worker.

## What is ready

1. Sidecar export architecture.
   - Evidence: `manifest.json` has `artifact_mode: sidecar`, `tensor_formats.heterodata/full_graph.pt` explicitly says the pickle is only for `artifact_mode=heterodata|both` or bounded auto exports, and `sidecar_artifact.metadata.json` has `heterodata_pickle: null`.
   - Audit: `sidecar_audit.json` reports `heterodata_pickle_exists: false` and `load_policy: Relation-wise sidecars are the production artifact... do not materialize a full HeteroData pickle for no-cap exports.`

2. Relation-scoped training smoke.
   - Evidence: parent smoke trained on `[molecule, molecule_targets_gene, gene]` for 1 epoch with 32 train positives, 32 train negatives, 12 validation positives, and 12 validation negatives.
   - Smoke status: `pass`.
   - Validation checks passed: feature tensors present, edge tensors present, edge attrs present, reverse edges present/count/transpose, selected/split endpoint bounds, nonempty splits, and selected edge attributes consumed by the predictor.

3. Bounded local memory behavior.
   - Evidence: local sidecar export capped `molecule_targets_gene` at 64 forward edges plus 64 reverse edges.
   - `np.load(..., mmap_mode='r')` audit saw `numpy.memmap` for both forward and reverse `edge_index.npy` arrays, each shape `[2,64]` and 1024 bytes.
   - Parent RSS evidence: build max RSS 487,063,552 bytes; smoke max RSS 488,390,656 bytes; process-tree peak sampled RSS 501,824 KB.

4. Embedding/missing-feature policy is explicit rather than vague.
   - Manifest records available node embeddings for `molecule` and `gene`: `sbiobert_snli_multinli_stsb/policy_v1`, 16 rows each, dim 768, dtype float32.
   - Manifest records available edge embeddings for `molecule_targets_gene`: `relation_value_evidence_mlp/edge_policy_v1`, 16 rows, dim 256, dtype float32.
   - Node fallback policy: use real sidecar rows when present; fill missing node rows with learned fallback embeddings at model materialization time.
   - Edge fallback policy: use real edge embedding rows where `edge_key` matches; fill missing edge rows with learned fallback embeddings at model materialization time.
   - Deferred items are named: molecule chemical encoder, gene DNA/foundation sequence embedding, and rich all-evidence payload tensor remain deferred/provenance-sidecar work.

5. Producer code/tests cover the stronger architecture claim.
   - Re-run tests in `/Users/jkobject/.openclaw/worktrees/txgnn/t_c40bdc86-pyg-readiness` passed: `14 passed, 2 warnings`.
   - Tests include no-cap sidecar export without full HeteroData pickle, selected-relation sidecar smoke with `max_loaded_edges`, embedding/fallback wiring, manifest/runbook docs, and reverse-edge `forward_edge_pos` mapping.

## False passes rejected / narrowed

- The parent smoke is not model-quality evidence. `valid_accuracy=1.0` on a 64-edge bounded fixture is not a biological or production metric; it only proves the training code executes and validates tensors/splits.
- The parent local artifact used macOS GCS-FUSE for a small bounded read. This is acceptable only as bounded smoke evidence, not as full-scale export/training evidence.
- The parent sidecar smoke in `artifacts/reports/t_ef300535` used deterministic 16-d synthetic node features and zero edge attrs from sidecar metadata. That is not final embedding materialization quality. The architecture claim depends on the producer worktree improvements/tests showing real sidecar embedding joins plus learned fallback behavior, not on the parent smoke alone.
- `manifest.bounded` is false because node maps were uncapped to keep endpoint indices valid; that is not a full-graph training claim. The edge/training relation was capped to 64 rows and no full `HeteroData` pickle was written.

## Why this avoids 100M-edge RAM materialization

- Production/no-cap exports resolve to `artifact_mode=sidecar`, not a monolithic `heterodata/full_graph.pt`.
- Each relation is stored as sidecar `edge_index.npy` plus row maps/metadata; the smoke loader selects one relation and loads its `edge_index.npy` with `mmap_mode='r'`.
- The stronger producer loader supports `--max-loaded-edges`, copying only a bounded prefix of the selected relation into the PyG `HeteroData` object for smoke/training checks.
- Node maps and edge row maps remain Parquet sidecars for joins/provenance instead of inflating every relation and evidence payload into in-memory tensors.
- Rich evidence payloads remain sidecar/provenance; dense model tensors are built only for the selected/bounded runtime path with real rows where available and learned fallback rows where missing.

## Exact larger bucket-local readiness command

Run only on `txgnn-worker` or another explicitly approved in-region worker. Do not run this from the Mac through `/Users/jkobject/mnt/gcs/...` / macOS GCS-FUSE.

```bash
# On local control host: launch/enter the approved worker.
gcloud compute ssh txgnn-worker --zone <ZONE> --project <PROJECT>

# On txgnn-worker: preflight.
hostname
pgrep -af 'build_pyg_export|run_pyg_gnn_smoke|pyg|embedding' || true
cd /path/to/TxGNN
uv sync --group gnn

# Bucket-local sidecar export; no macOS FUSE and no HeteroData full-graph pickle.
uv run python -m manage_db.build_pyg_export \
  --kg-root gs://jouvencekb/kg/v2 \
  --output-root gs://jouvencekb/kg/staging/ml/pyg/t_c40bdc86_sidecar_readiness \
  --node-types molecule gene disease pathway phenotype clinical_trial \
  --relations molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease disease_associated_gene disease_has_phenotype gene_associated_phenotype pathway_contains_gene clinical_trial_tests_molecule clinical_trial_studies_disease \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 0 \
  --artifact-mode sidecar \
  --embedding-features-root gs://jouvencekb/kg/v2/features \
  --build-name t_c40bdc86_sidecar_readiness \
  --sort-node-ids

# Stage sidecars to worker-local SSD before mmap smoke; run_pyg_gnn_smoke uses local Path/np.load semantics.
mkdir -p /mnt/disks/txgnn-ssd/pyg/t_c40bdc86_sidecar_readiness
gcloud storage rsync -r \
  gs://jouvencekb/kg/staging/ml/pyg/t_c40bdc86_sidecar_readiness \
  /mnt/disks/txgnn-ssd/pyg/t_c40bdc86_sidecar_readiness

uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root /mnt/disks/txgnn-ssd/pyg/t_c40bdc86_sidecar_readiness \
  --relation molecule_targets_gene \
  --epochs 3 \
  --hidden-channels 16 \
  --max-loaded-edges 100000 \
  --max-train-edges 4096 \
  --output-json /mnt/disks/txgnn-ssd/pyg/t_c40bdc86_sidecar_readiness/gnn_smoke_metrics.json

gcloud storage cp \
  /mnt/disks/txgnn-ssd/pyg/t_c40bdc86_sidecar_readiness/gnn_smoke_metrics.json \
  gs://jouvencekb/kg/staging/ml/pyg/t_c40bdc86_sidecar_readiness/gnn_smoke_metrics.json
```

Limits in this command:

- Full node maps are permitted by `--max-nodes-per-type 0` so endpoint indices remain valid.
- Full selected relation exports are permitted by `--max-edges-per-relation 0` only on the approved worker/bucket-local path.
- Smoke/training remains bounded by `--max-loaded-edges 100000` and `--max-train-edges 4096`.
- This is still readiness smoke, not production/full model training.

## Deferred work

- Full-scale multi-relation GNN training over the production KG.
- Production model-quality evaluation and biological validation.
- Final dense tensor materialization strategy for all desired node/edge embedding modalities at scale.
- Production molecule chemical encoder and gene/protein/DNA/foundation sequence embeddings where not already available.
- Direct remote `gs://` mmap support is not claimed; the smoke loader uses local Path semantics after staging to worker-local SSD.

## Acceptance criteria mapping

- Evidence-backed report: satisfied by parent QA/audit/manifest/smoke artifacts plus producer worktree test rerun.
- Exact commands and limits: satisfied by the VM-only command above, with explicit `--max-loaded-edges 100000` and `--max-train-edges 4096` smoke limits.
- Deferred work identified: satisfied in the Deferred work section.
- PyG training-ready wording is truthful: satisfied by narrowing the claim to architecture/readiness smoke and explicitly excluding full-scale training completion.
- Shallow evidence rejected: satisfied by rejecting the 64-edge smoke as model-quality evidence and by calling out synthetic/zero feature caveats in the parent artifact.
- Heavy-training guardrail: satisfied by requiring `txgnn-worker`, `gs://jouvencekb/kg/v2`, process preflight, worker-local SSD staging, and forbidding macOS GCS-FUSE for the larger run.
- Unbounded edge-index load risk: satisfied by sidecar/memmap architecture, no full pickle for no-cap exports, and bounded `--max-loaded-edges` smoke path in the producer worktree.
- Missing embedding mapping/policy: satisfied by manifest-recorded node/edge mappings and learned fallback policy, with deferred features named explicitly.
