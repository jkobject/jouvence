"""Run a bounded PyG GNN smoke/training step on a Jouvence KG PyG export.

The input is an export produced by :mod:`manage_db.build_pyg_export`.  The smoke
job intentionally stays small and deterministic: it loads the exported
``HeteroData`` object, validates node features/edge tensors/reverse edges/splits,
then trains a two-layer heterogeneous GraphSAGE encoder plus dot-product link
predictor on one selected primary relation. Other forward/reverse relations in
the HeteroData object remain in the message-passing graph as auxiliary context;
heldout leakage checks apply to the selected primary relation.
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv


@dataclass(frozen=True)
class SmokeConfig:
    export_root: Path
    relation: str | None = None
    epochs: int = 3
    hidden_channels: int = 16
    seed: int = 13
    max_train_edges: int = 4096
    learning_rate: float = 0.01
    output_json: Path | None = None


@dataclass
class SmokeResult:
    status: str
    export_root: str
    relation: str
    edge_type: tuple[str, str, str]
    reverse_edge_type: tuple[str, str, str] | None
    node_types: list[str]
    edge_types: list[tuple[str, str, str]]
    auxiliary_edge_types: list[tuple[str, str, str]]
    graph_sizes: dict[str, Any]
    feature_shapes: dict[str, list[int]]
    split_counts: dict[str, int]
    metrics: dict[str, Any]
    validation: dict[str, Any]
    config: dict[str, Any]


class HeteroSageLinkPredictor(nn.Module):
    def __init__(self, metadata: tuple[list[str], list[tuple[str, str, str]]], in_channels: int, hidden_channels: int, edge_attr_dim: int | None = None) -> None:
        super().__init__()
        edge_types = metadata[1]
        self.conv1 = HeteroConv({edge_type: SAGEConv((in_channels, in_channels), hidden_channels) for edge_type in edge_types}, aggr="sum")
        self.conv2 = HeteroConv({edge_type: SAGEConv((hidden_channels, hidden_channels), hidden_channels) for edge_type in edge_types}, aggr="sum")
        self.edge_attr_projection = nn.Linear(edge_attr_dim, 1, bias=False) if edge_attr_dim else None

    def encode(self, data: HeteroData) -> dict[str, torch.Tensor]:
        x_dict = {node_type: data[node_type].x.float() for node_type in data.node_types}
        x_dict = self.conv1(x_dict, data.edge_index_dict)
        x_dict = {node_type: F.relu(x) for node_type, x in x_dict.items()}
        x_dict = self.conv2(x_dict, data.edge_index_dict)
        return x_dict

    def score(self, z_dict: dict[str, torch.Tensor], edge_type: tuple[str, str, str], edge_label_index: torch.Tensor, edge_attr: torch.Tensor | None = None) -> torch.Tensor:
        src_type, _, dst_type = edge_type
        src_z = z_dict[src_type][edge_label_index[0]]
        dst_z = z_dict[dst_type][edge_label_index[1]]
        score = (src_z * dst_z).sum(dim=-1)
        if self.edge_attr_projection is not None:
            if edge_attr is None:
                edge_attr = torch.zeros((edge_label_index.size(1), self.edge_attr_projection.in_features), dtype=score.dtype, device=score.device)
            score = score + self.edge_attr_projection(edge_attr.float()).squeeze(-1)
        return score


def run_smoke(config: SmokeConfig) -> SmokeResult:
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)

    data = _load_heterodata(config.export_root)
    _ensure_features(data)
    edge_type = _select_edge_type(data, config.relation)
    reverse_edge_type = _find_reverse_edge_type(data, edge_type)
    train_pos, valid_pos, test_pos, train_idx, valid_idx, test_idx = _split_edges(data[edge_type].edge_index, config.max_train_edges, config.seed)
    train_neg = _negative_edges(data, edge_type, train_pos.size(1), config.seed + 1)
    valid_neg = _negative_edges(data, edge_type, valid_pos.size(1), config.seed + 2)
    test_neg = _negative_edges(data, edge_type, test_pos.size(1), config.seed + 3)
    edge_attr_dim = int(data[edge_type].edge_attr.size(1)) if hasattr(data[edge_type], "edge_attr") and data[edge_type].edge_attr is not None else None
    message_passing_data = _build_training_message_passing_graph(data, edge_type, reverse_edge_type, train_idx, valid_idx, test_idx)

    model = HeteroSageLinkPredictor(data.metadata(), in_channels=data[data.node_types[0]].x.size(1), hidden_channels=config.hidden_channels, edge_attr_dim=edge_attr_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    losses: list[float] = []
    for _ in range(config.epochs):
        model.train()
        optimizer.zero_grad()
        z_dict = model.encode(message_passing_data)
        train_edge_attr = data[edge_type].edge_attr[train_idx] if edge_attr_dim else None
        pos_score = model.score(z_dict, edge_type, train_pos, train_edge_attr)
        neg_score = model.score(z_dict, edge_type, train_neg, None)
        logits = torch.cat([pos_score, neg_score], dim=0)
        labels = torch.cat([torch.ones_like(pos_score), torch.zeros_like(neg_score)], dim=0)
        loss = F.binary_cross_entropy_with_logits(logits, labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))

    model.eval()
    with torch.no_grad():
        z_dict = model.encode(message_passing_data)
        valid_edge_attr = data[edge_type].edge_attr[valid_idx] if edge_attr_dim else None
        valid_loss, valid_accuracy = _evaluate_edges(model, z_dict, edge_type, valid_pos, valid_neg, valid_edge_attr)
        test_edge_attr = data[edge_type].edge_attr[test_idx] if edge_attr_dim else None
        test_loss, test_accuracy = _evaluate_edges(model, z_dict, edge_type, test_pos, test_neg, test_edge_attr)

    validation = _validate_data(
        data,
        message_passing_data,
        edge_type,
        reverse_edge_type,
        train_pos,
        valid_pos,
        test_pos,
        train_neg,
        valid_neg,
        test_neg,
        edge_attr_dim is not None,
    )
    result = SmokeResult(
        status="pass" if validation["status"] == "pass" and losses else "fail",
        export_root=str(config.export_root),
        relation=edge_type[1],
        edge_type=edge_type,
        reverse_edge_type=reverse_edge_type,
        node_types=list(data.node_types),
        edge_types=list(data.edge_types),
        auxiliary_edge_types=[et for et in data.edge_types if et not in {edge_type, reverse_edge_type}],
        graph_sizes=_graph_sizes(data, edge_type, reverse_edge_type, message_passing_data),
        feature_shapes={node_type: list(data[node_type].x.shape) for node_type in data.node_types},
        split_counts={
            "train_positive_edges": int(train_pos.size(1)),
            "train_negative_edges": int(train_neg.size(1)),
            "valid_positive_edges": int(valid_pos.size(1)),
            "valid_negative_edges": int(valid_neg.size(1)),
            "test_positive_edges": int(test_pos.size(1)),
            "test_negative_edges": int(test_neg.size(1)),
        },
        metrics={
            "epochs": float(config.epochs),
            "train_loss_trace": losses,
            "initial_train_loss": losses[0],
            "final_train_loss": losses[-1],
            "valid_loss": float(valid_loss.detach().cpu()),
            "valid_accuracy": float(valid_accuracy.detach().cpu()),
            "test_loss": float(test_loss.detach().cpu()),
            "test_accuracy": float(test_accuracy.detach().cpu()),
        },
        validation=validation,
        config={
            "epochs": config.epochs,
            "hidden_channels": config.hidden_channels,
            "seed": config.seed,
            "max_train_edges": config.max_train_edges,
            "learning_rate": config.learning_rate,
            "relation_role": "primary_link_prediction_relation_with_other_relations_as_auxiliary_message_passing_context",
        },
    )
    if config.output_json:
        config.output_json.parent.mkdir(parents=True, exist_ok=True)
        config.output_json.write_text(json.dumps(_jsonable(asdict(result)), indent=2, sort_keys=True) + "\n")
    return result


def _load_heterodata(export_root: Path) -> HeteroData:
    path = export_root / "heterodata" / "full_graph.pt"
    if not path.exists():
        raise FileNotFoundError(f"Missing HeteroData artifact: {path}")
    with path.open("rb") as fh:
        data = pickle.load(fh)
    if not isinstance(data, HeteroData):
        raise TypeError(f"Expected torch_geometric.data.HeteroData in {path}, got {type(data)!r}")
    if not data.edge_types:
        raise ValueError(f"HeteroData artifact has no edge types: {path}")
    return data


def _ensure_features(data: HeteroData) -> None:
    widths = {int(data[node_type].x.size(1)) for node_type in data.node_types if hasattr(data[node_type], "x") and data[node_type].x is not None}
    if not widths:
        raise ValueError("HeteroData has no node feature tensors")
    if len(widths) != 1:
        raise ValueError(f"All node feature tensors must share width for this smoke model, got {sorted(widths)}")
    for node_type in data.node_types:
        if not hasattr(data[node_type], "x") or data[node_type].x is None:
            raise ValueError(f"Node type {node_type!r} missing x feature tensor")
        if int(data[node_type].x.size(0)) != int(data[node_type].num_nodes):
            raise ValueError(f"Node feature row count mismatch for {node_type!r}")


def _select_edge_type(data: HeteroData, relation: str | None) -> tuple[str, str, str]:
    candidates = [edge_type for edge_type in data.edge_types if not edge_type[1].startswith("rev_")]
    if relation:
        candidates = [edge_type for edge_type in candidates if edge_type[1] == relation]
    if not candidates:
        raise ValueError(f"No forward edge type found for relation={relation!r}; available={data.edge_types}")
    edge_type = max(candidates, key=lambda et: int(data[et].edge_index.size(1)))
    if int(data[edge_type].edge_index.size(1)) < 3:
        raise ValueError(f"Need at least 3 positive edges for train/valid/test split, got {data[edge_type].edge_index.size(1)} for {edge_type}")
    return edge_type


def _find_reverse_edge_type(data: HeteroData, edge_type: tuple[str, str, str]) -> tuple[str, str, str] | None:
    src_type, relation, dst_type = edge_type
    rev = (dst_type, f"rev_{relation}", src_type)
    return rev if rev in data.edge_types else None


def _evaluate_edges(
    model: HeteroSageLinkPredictor,
    z_dict: dict[str, torch.Tensor],
    edge_type: tuple[str, str, str],
    pos_edges: torch.Tensor,
    neg_edges: torch.Tensor,
    pos_edge_attr: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    pos_score = model.score(z_dict, edge_type, pos_edges, pos_edge_attr)
    neg_score = model.score(z_dict, edge_type, neg_edges, None)
    logits = torch.cat([pos_score, neg_score], dim=0)
    labels = torch.cat([torch.ones_like(pos_score), torch.zeros_like(neg_score)], dim=0)
    loss = F.binary_cross_entropy_with_logits(logits, labels)
    accuracy = ((torch.sigmoid(logits) >= 0.5) == labels.bool()).float().mean()
    return loss, accuracy

def _graph_sizes(
    data: HeteroData,
    primary_edge_type: tuple[str, str, str],
    reverse_edge_type: tuple[str, str, str] | None,
    message_passing_data: HeteroData,
) -> dict[str, Any]:
    return {
        "node_counts": {node_type: int(data[node_type].num_nodes) for node_type in data.node_types},
        "edge_counts": {str(edge_type): int(data[edge_type].edge_index.size(1)) for edge_type in data.edge_types},
        "forward_edge_counts": {
            edge_type[1]: int(data[edge_type].edge_index.size(1))
            for edge_type in data.edge_types
            if not edge_type[1].startswith("rev_")
        },
        "primary_relation": primary_edge_type[1],
        "primary_edge_type": primary_edge_type,
        "primary_edge_count": int(data[primary_edge_type].edge_index.size(1)),
        "primary_message_passing_edge_count": int(message_passing_data[primary_edge_type].edge_index.size(1)),
        "primary_reverse_edge_type": reverse_edge_type,
        "auxiliary_forward_relations": [
            edge_type[1]
            for edge_type in data.edge_types
            if not edge_type[1].startswith("rev_") and edge_type != primary_edge_type
        ],
        "auxiliary_edge_types": [edge_type for edge_type in data.edge_types if edge_type not in {primary_edge_type, reverse_edge_type}],
    }


def _edge_attr_usage(data: HeteroData, edge_type: tuple[str, str, str], selected_edge_attr_consumed: bool) -> dict[str, Any]:
    edge_attr_shapes: dict[str, list[int] | None] = {}
    for et in data.edge_types:
        value = data[et].edge_attr if hasattr(data[et], "edge_attr") else None
        edge_attr_shapes[str(et)] = list(value.shape) if value is not None else None
    return {
        "all_edge_types_have_edge_attr": all(shape is not None for shape in edge_attr_shapes.values()),
        "selected_edge_type": edge_type,
        "selected_edge_attr_shape": edge_attr_shapes.get(str(edge_type)),
        "selected_edge_attr_consumed_by_predictor": bool(selected_edge_attr_consumed),
        "edge_attr_shapes": edge_attr_shapes,
    }



def _build_training_message_passing_graph(
    data: HeteroData,
    edge_type: tuple[str, str, str],
    reverse_edge_type: tuple[str, str, str] | None,
    train_idx: torch.Tensor,
    valid_idx: torch.Tensor,
    test_idx: torch.Tensor,
) -> HeteroData:
    if set(train_idx.tolist()) & set(valid_idx.tolist()) or set(train_idx.tolist()) & set(test_idx.tolist()) or set(valid_idx.tolist()) & set(test_idx.tolist()):
        raise ValueError("Train/validation/test positive edge indices must be disjoint")
    del valid_idx, test_idx  # validated above; heldout labels are excluded by retaining train_idx only.
    message_passing_data = data.clone()
    message_passing_data[edge_type].edge_index = data[edge_type].edge_index[:, train_idx].long().contiguous()
    if hasattr(data[edge_type], "edge_attr") and data[edge_type].edge_attr is not None:
        message_passing_data[edge_type].edge_attr = data[edge_type].edge_attr[train_idx].contiguous()
    if reverse_edge_type is not None:
        message_passing_data[reverse_edge_type].edge_index = data[edge_type].edge_index[[1, 0], :][:, train_idx].long().contiguous()
        if hasattr(data[reverse_edge_type], "edge_attr") and data[reverse_edge_type].edge_attr is not None:
            message_passing_data[reverse_edge_type].edge_attr = data[reverse_edge_type].edge_attr[train_idx].contiguous()
    return message_passing_data


def _edge_pair_set(edge_index: torch.Tensor) -> set[tuple[int, int]]:
    return set(map(tuple, edge_index.t().tolist()))


def _heldout_edges_removed_from_message_passing(
    message_passing_data: HeteroData,
    edge_type: tuple[str, str, str],
    reverse_edge_type: tuple[str, str, str] | None,
    valid_pos: torch.Tensor,
    test_pos: torch.Tensor,
) -> bool:
    heldout_pairs = _edge_pair_set(valid_pos) | _edge_pair_set(test_pos)
    message_pairs = _edge_pair_set(message_passing_data[edge_type].edge_index)
    if heldout_pairs & message_pairs:
        return False
    if reverse_edge_type is not None:
        reverse_heldout_pairs = {(dst, src) for src, dst in heldout_pairs}
        reverse_message_pairs = _edge_pair_set(message_passing_data[reverse_edge_type].edge_index)
        if reverse_heldout_pairs & reverse_message_pairs:
            return False
    return True


def _split_edges(edge_index: torch.Tensor, max_train_edges: int, seed: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    edge_count = int(edge_index.size(1))
    if edge_count < 3:
        raise ValueError(f"Need at least 3 positive edges for train/valid/test split, got {edge_count}")
    generator = torch.Generator().manual_seed(seed)
    perm = torch.randperm(edge_count, generator=generator)
    test_count = max(1, min(edge_count // 5, 1024))
    valid_count = max(1, min(edge_count // 5, 1024))
    remaining_for_train = edge_count - valid_count - test_count
    if remaining_for_train < 1:
        valid_count = 1
        test_count = 1
        remaining_for_train = edge_count - 2
    train_count = max(1, min(remaining_for_train, max_train_edges))
    train_idx = perm[:train_count]
    valid_idx = perm[train_count : train_count + valid_count]
    test_idx = perm[train_count + valid_count : train_count + valid_count + test_count]
    return (
        edge_index[:, train_idx].long(),
        edge_index[:, valid_idx].long(),
        edge_index[:, test_idx].long(),
        train_idx.long(),
        valid_idx.long(),
        test_idx.long(),
    )


def _negative_edges(data: HeteroData, edge_type: tuple[str, str, str], count: int, seed: int) -> torch.Tensor:
    src_type, _, dst_type = edge_type
    existing = set(map(tuple, data[edge_type].edge_index.t().tolist()))
    src_count = int(data[src_type].num_nodes)
    dst_count = int(data[dst_type].num_nodes)
    rng = random.Random(seed)
    negatives: list[tuple[int, int]] = []
    attempts = 0
    max_attempts = max(10_000, count * 100)
    while len(negatives) < count and attempts < max_attempts:
        attempts += 1
        pair = (rng.randrange(src_count), rng.randrange(dst_count))
        if pair not in existing:
            existing.add(pair)
            negatives.append(pair)
    if len(negatives) < count:
        raise ValueError(f"Could only sample {len(negatives)} negative edges out of requested {count}")
    return torch.tensor(negatives, dtype=torch.long).t().contiguous()


def _validate_data(
    data: HeteroData,
    message_passing_data: HeteroData,
    edge_type: tuple[str, str, str],
    reverse_edge_type: tuple[str, str, str] | None,
    train_pos: torch.Tensor,
    valid_pos: torch.Tensor,
    test_pos: torch.Tensor,
    train_neg: torch.Tensor,
    valid_neg: torch.Tensor,
    test_neg: torch.Tensor,
    selected_edge_attr_consumed: bool,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["feature_tensors_present"] = all(hasattr(data[node_type], "x") and data[node_type].x is not None for node_type in data.node_types)
    checks["edge_tensors_present"] = all(hasattr(data[et], "edge_index") and data[et].edge_index.size(0) == 2 for et in data.edge_types)
    checks["edge_attr_tensors_present"] = all(hasattr(data[et], "edge_attr") and data[et].edge_attr is not None and data[et].edge_attr.size(0) == data[et].edge_index.size(1) for et in data.edge_types)
    checks["selected_edge_attr_consumed_by_predictor"] = bool(selected_edge_attr_consumed)
    checks["selected_edge_endpoint_bounds"] = _edge_label_bounds_ok(data, edge_type, data[edge_type].edge_index)
    checks["split_endpoint_bounds"] = all(_edge_label_bounds_ok(data, edge_type, edges) for edges in (train_pos, valid_pos, test_pos, train_neg, valid_neg, test_neg))
    checks["nonempty_splits"] = all(int(edges.size(1)) > 0 for edges in (train_pos, valid_pos, test_pos, train_neg, valid_neg, test_neg))
    checks["heldout_edges_removed_from_message_passing"] = _heldout_edges_removed_from_message_passing(message_passing_data, edge_type, reverse_edge_type, valid_pos, test_pos)
    checks["message_passing_edge_count_matches_train_split"] = int(message_passing_data[edge_type].edge_index.size(1)) == int(train_pos.size(1))
    if reverse_edge_type is not None:
        forward = data[edge_type].edge_index
        reverse = data[reverse_edge_type].edge_index
        checks["reverse_edges_present"] = True
        checks["reverse_edge_count_matches"] = int(forward.size(1)) == int(reverse.size(1))
        checks["reverse_edges_are_transpose"] = torch.equal(forward[[1, 0], :], reverse)
    else:
        checks["reverse_edges_present"] = False
        checks["reverse_edge_count_matches"] = False
        checks["reverse_edges_are_transpose"] = False
    return {
        "status": "pass" if all(bool(v) for v in checks.values()) else "fail",
        "checks": checks,
        "edge_attr_usage": _edge_attr_usage(data, edge_type, selected_edge_attr_consumed),
    }


def _edge_label_bounds_ok(data: HeteroData, edge_type: tuple[str, str, str], edge_index: torch.Tensor) -> bool:
    src_type, _, dst_type = edge_type
    if edge_index.numel() == 0:
        return False
    return bool(
        int(edge_index[0].min()) >= 0
        and int(edge_index[1].min()) >= 0
        and int(edge_index[0].max()) < int(data[src_type].num_nodes)
        and int(edge_index[1].max()) < int(data[dst_type].num_nodes)
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def parse_args(argv: list[str] | None = None) -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run a bounded PyG GNN smoke/training job on an exported HeteroData graph")
    parser.add_argument("--export-root", required=True, type=Path)
    parser.add_argument("--relation", default=None)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--hidden-channels", type=int, default=16)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--max-train-edges", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--output-json", type=Path, default=None)
    ns = parser.parse_args(argv)
    return SmokeConfig(
        export_root=ns.export_root,
        relation=ns.relation,
        epochs=ns.epochs,
        hidden_channels=ns.hidden_channels,
        seed=ns.seed,
        max_train_edges=ns.max_train_edges,
        learning_rate=ns.learning_rate,
        output_json=ns.output_json,
    )


def main(argv: list[str] | None = None) -> int:
    result = run_smoke(parse_args(argv))
    print(json.dumps(_jsonable(asdict(result)), indent=2, sort_keys=True))
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
