# t_1d1eb3a1 — PyG/HeteroData + GNN runtime validation

Status: PASS for staged/bounded representative `PYG-FULL-GNN` runtime acceptance.

Important scope caveat: this is not a canonical whole-KG promotion. The validated artifact is the accepted staged representative export at `artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno`, with five node types, seven forward relations, reverse edges, and `max_edges_per_relation=20000`. It is materially beyond the previous bounded `.npy` metadata pilot because it includes a real PyG `HeteroData` `.pt` and a GraphSAGE training smoke run.

## Target

- Workspace: `/Users/jkobject/.openclaw/workspace/work/txgnn`
- Export root: `artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno`
- KG root recorded by artifact: `/Users/jkobject/mnt/gcs/jouvencekb-kg/v2`
- Fresh tester metrics JSON: `artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/tester_t_1d1eb3a1_smoke_metrics.json`

## Runtime evidence

Command run ID printed by shell:

```text
RUN_ID tester-t_1d1eb3a1-20260623T155356Z
```

Runtime import/version check:

```bash
uv run python - <<'PY'
import json, sys
import torch
import torch_geometric
from torch_geometric.data import HeteroData
print(json.dumps({
  'python': sys.version.split()[0],
  'torch': torch.__version__,
  'torch_geometric': torch_geometric.__version__,
  'heterodata_class': f'{HeteroData.__module__}.{HeteroData.__name__}',
  'cuda_available': bool(torch.cuda.is_available()),
}, indent=2, sort_keys=True))
PY
```

Observed output:

```json
{
  "cuda_available": false,
  "heterodata_class": "torch_geometric.data.hetero_data.HeteroData",
  "python": "3.11.15",
  "torch": "2.12.1",
  "torch_geometric": "2.8.0"
}
```

## HeteroData artifact evidence

Files exist and were stat'ed:

```text
artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/heterodata/full_graph.pt 5388959 bytes
artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/heterodata/full_graph.metadata.json 7930 bytes
artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/tester_t_1d1eb3a1_smoke_metrics.json 2578 bytes
artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/validation_report.json 940 bytes
```

Loaded object type:

```text
torch_geometric.data.hetero_data.HeteroData
```

Node counts / feature tensor shapes:

```json
{
  "disease": [41859, 1],
  "gene": [267830, 1],
  "molecule": [31007, 1],
  "pathway": [48575, 1],
  "phenotype": [16449, 1]
}
```

Forward edge counts:

```json
{
  "molecule_targets_gene": 20000,
  "molecule_treats_disease": 14135,
  "molecule_contraindicates_disease": 20000,
  "disease_associated_gene": 20000,
  "disease_has_phenotype": 20000,
  "gene_associated_phenotype": 3330,
  "pathway_contains_gene": 20000
}
```

Deep audit result:

- all edge endpoint bounds: PASS
- all seven forward/reverse edge counts match: PASS
- all seven reverse edge tensors equal transposed forward tensors: PASS
- validation report status: PASS
- validation issue count: 0

## GNN smoke/training evidence

Command:

```bash
uv run python -m manage_db.run_pyg_gnn_smoke \
  --export-root artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno \
  --relation molecule_treats_disease \
  --epochs 2 \
  --hidden-channels 8 \
  --max-train-edges 512 \
  --seed 101 \
  --output-json artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno/tester_t_1d1eb3a1_smoke_metrics.json
```

Observed metrics:

```json
{
  "status": "pass",
  "relation": "molecule_treats_disease",
  "edge_type": ["molecule", "molecule_treats_disease", "disease"],
  "reverse_edge_type": ["disease", "rev_molecule_treats_disease", "molecule"],
  "split_counts": {
    "train_positive_edges": 512,
    "train_negative_edges": 512,
    "valid_positive_edges": 1024,
    "valid_negative_edges": 1024
  },
  "metrics": {
    "epochs": 2.0,
    "initial_train_loss": 0.9007991552352905,
    "final_train_loss": 0.5626281499862671,
    "valid_loss": 0.38400566577911377,
    "valid_accuracy": 0.8203125
  },
  "validation": {
    "status": "pass",
    "checks": {
      "feature_tensors_present": true,
      "edge_tensors_present": true,
      "selected_edge_endpoint_bounds": true,
      "split_endpoint_bounds": true,
      "nonempty_splits": true,
      "reverse_edges_present": true,
      "reverse_edge_count_matches": true,
      "reverse_edges_are_transpose": true
    }
  }
}
```

## Reproducibility commands

Build command recorded by artifact README:

```bash
uv run python -m manage_db.build_pyg_export \
  --kg-root /Users/jkobject/mnt/gcs/jouvencekb-kg/v2 \
  --output-root artifacts/staged/t_015bd9a4_pyg_full_gnn/rep_drug_gene_disease_pathway_pheno \
  --node-types molecule gene disease pathway phenotype \
  --relations molecule_targets_gene molecule_treats_disease molecule_contraindicates_disease disease_associated_gene disease_has_phenotype gene_associated_phenotype pathway_contains_gene \
  --max-nodes-per-type 0 \
  --max-edges-per-relation 20000
```

Smoke command used by tester is shown above. The smoke is deterministic for the selected relation using `--seed 101`.

## Verdict

PASS for the accepted staged/bounded representative runtime gate: actual `torch`/`torch_geometric` are installed, a real PyG `HeteroData` object exists at `heterodata/full_graph.pt`, and a real heterogeneous GraphSAGE smoke/training job ran successfully with logged metrics.

Do not describe this as canonical full-KG production completion: it is still staged, relation/node-type bounded, and capped at 20k edges per selected relation except `molecule_treats_disease` and `gene_associated_phenotype`, which have fewer rows in this export.
