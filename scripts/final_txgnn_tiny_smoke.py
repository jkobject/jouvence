"""Final bounded TxGNN smoke test.

Creates only temporary local scratch data, never mutates canonical GCS or
LaminDB. Intended to run under systemd resource limits, e.g.:

    systemd-run --user --wait --collect -p CPUQuota=200% -p MemoryMax=4G \
      --working-directory=/home/ubuntu/.openclaw/workspace/work/txgnn \
      uv run python scripts/final_txgnn_tiny_smoke.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import dgl
import pandas as pd
import torch

from manage_db.kg_schema import EDGE_PARQUET_COLUMNS, NODE_TYPES, NodeType
from manage_db.kg_storage import open_kg_root, write_edges, write_nodes
from txgnn import KGLoader
from txgnn.TxGNN import TxGNN
from txgnn.utils import Full_Graph_NegSampler


def _node_frame(node_type: NodeType, ids: list[str]) -> pd.DataFrame:
    cols = ["id", *NODE_TYPES[node_type].xref_columns]
    rows = []
    for node_id in ids:
        row = {col: None for col in cols}
        row["id"] = node_id
        rows.append(row)
    return pd.DataFrame(rows)


def _edge_frame(rows: list[tuple[str, str]]) -> pd.DataFrame:
    data = []
    for x_id, y_id in rows:
        row = {name: "smoke" for name, _ in EDGE_PARQUET_COLUMNS}
        row.update(
            {
                "x_id": x_id,
                "x_type": "disease",
                "y_id": y_id,
                "y_type": "gene",
                "relation": "disease_associated_gene",
                "display_relation": "disease associated gene",
                "source": "smoke",
                "credibility": 3,
            }
        )
        data.append(row)
    return pd.DataFrame(data)


def _write_loader_smoke_kg(root_dir: Path) -> dict[str, int | bool]:
    root = open_kg_root(str(root_dir / "kg"))
    write_nodes(root, "disease", _node_frame(NodeType.DISEASE, ["EFO:SMOKE1", "EFO:SMOKE2"]))
    write_nodes(root, "gene", _node_frame(NodeType.GENE, ["ENSGSMOKE1", "ENSGSMOKE2"]))
    write_edges(
        root,
        "disease_associated_gene",
        _edge_frame([("EFO:SMOKE1", "ENSGSMOKE1"), ("EFO:SMOKE2", "ENSGSMOKE2")]),
    )
    report = KGLoader(root_dir).validate()
    return {
        "kgloader_ok": report.ok,
        "kgloader_nodes": report.total_nodes,
        "kgloader_edges": report.total_edges,
        "kgloader_dangling": report.total_dangling_edges,
    }


def _make_txgnn_data(tmpdir: Path) -> SimpleNamespace:
    num_drugs = 3
    num_diseases = 3
    graph_data = {
        ("drug", "contraindication", "disease"): (torch.tensor([0, 1]), torch.tensor([0, 1])),
        ("drug", "indication", "disease"): (torch.tensor([1, 2]), torch.tensor([1, 2])),
        ("drug", "off-label use", "disease"): (torch.tensor([0, 2]), torch.tensor([2, 0])),
        ("disease", "rev_contraindication", "drug"): (torch.tensor([0, 1]), torch.tensor([0, 1])),
        ("disease", "rev_indication", "drug"): (torch.tensor([1, 2]), torch.tensor([1, 2])),
        ("disease", "rev_off-label use", "drug"): (torch.tensor([2, 0]), torch.tensor([0, 2])),
    }
    graph = dgl.heterograph(graph_data, num_nodes_dict={"drug": num_drugs, "disease": num_diseases})

    rows = []
    for (_src_type, relation, _dst_type), (src, dst) in graph_data.items():
        for x_idx, y_idx in zip(src.tolist(), dst.tolist(), strict=True):
            rows.append(
                {
                    "x_idx": x_idx,
                    "y_idx": y_idx,
                    "relation": relation,
                    "x_type": _src_type,
                    "y_type": _dst_type,
                    "x_id": f"{_src_type}:{x_idx}",
                    "y_id": f"{_dst_type}:{y_idx}",
                }
            )
    df = pd.DataFrame(rows)
    # Keep validation/test tiny but include every TxGNN drug-disease relation so
    # model_initialize builds positive/negative graphs for the hard-coded etypes.
    df_valid = df.copy()
    df_test = df.copy()
    return SimpleNamespace(
        G=graph,
        df=df,
        df_train=df.copy(),
        df_valid=df_valid,
        df_test=df_test,
        data_folder=str(tmpdir),
        disease_eval_idx=[],
        split="tiny_smoke",
        no_kg=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="txgnn-final-smoke-") as tmp:
        tmpdir = Path(tmp)
        loader_summary = _write_loader_smoke_kg(tmpdir)
        data = _make_txgnn_data(tmpdir)
        model = TxGNN(data=data, weight_bias_track=False, device="cpu")
        model.model_initialize(
            n_hid=4,
            n_inp=4,
            n_out=4,
            proto=False,
            proto_num=1,
            attention=False,
            num_walks=1,
            path_length=1,
        )
        neg_graph = Full_Graph_NegSampler(model.G, 1, "fix_dst", model.device)(model.G)
        pred_pos, pred_neg, _, _ = model.model(
            model.G,
            neg_graph,
            model.G,
            pretrain_mode=False,
            mode="smoke",
        )
        summary = {
            **loader_summary,
            "torch": torch.__version__,
            "dgl": dgl.__version__,
            "model_class": type(model.model).__name__,
            "canonical_etypes": len(model.G.canonical_etypes),
            "pred_pos_relations": len(pred_pos),
            "pred_neg_relations": len(pred_neg),
            "device": str(model.device),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        assert summary["kgloader_ok"] is True
        assert summary["pred_pos_relations"] >= 6
        assert summary["pred_neg_relations"] >= 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
