from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from manage_db import sync_parquet_edges_to_lamindb as live_sync


def _write_edge_fixture(root: Path) -> None:
    (root / "edges").mkdir(parents=True)
    (root / "evidence").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "OpenTargets",
                "credibility": 3,
                "score": 0.88,
            },
            {
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "MONDO:0019391",
                "y_type": "disease",
                "relation": "disease_associated_gene",
                "display_relation": "associated gene",
                "source": "TxGNN",
                "credibility": 1,
                "score": None,
            },
        ]
    ).to_parquet(root / "edges" / "disease_associated_gene.parquet", index=False)
    pd.DataFrame(
        [
            {
                "edge_key": "legacy-key-is-recomputed",
                "relation": "disease_associated_gene",
                "x_id": "NCBI:672",
                "x_type": "gene",
                "y_id": "EFO:0000305",
                "y_type": "disease",
                "evidence_type": "database_record",
                "source": "OpenTargets",
                "source_dataset": "reactome",
                "source_record_id": "fixture-record",
                "paper_id": None,
                "dataset_id": None,
                "study_id": None,
                "evidence_score": 0.88,
                "predicate": "disease_associated_gene",
                "direction": "forward",
                "release": "fixture",
            }
        ]
    ).to_parquet(root / "evidence" / "disease_associated_gene.parquet", index=False)


class FakeQuerySet:
    def __init__(self, records: dict[str, dict[str, Any]], relation: str):
        self.records = records
        self.relation = relation

    def count(self) -> int:
        return sum(1 for row in self.records.values() if row.get("relation") == self.relation)


class FakeManager:
    def __init__(self):
        self.records: dict[str, dict[str, Any]] = {}

    def update_or_create(self, defaults: dict[str, Any], **lookup: str):
        key_field, key = next(iter(lookup.items()))
        record = dict(defaults)
        record[key_field] = key
        created = key not in self.records
        self.records[key] = record
        return record, created

    def filter(self, *, relation: str):
        return FakeQuerySet(self.records, relation)


class FakeKGEdge:
    objects = FakeManager()


class FakeKGEdgeEvidence:
    objects = FakeManager()


def test_live_sync_dry_run_does_not_touch_models(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "kg"
    _write_edge_fixture(root)
    FakeKGEdge.objects = FakeManager()
    FakeKGEdgeEvidence.objects = FakeManager()
    monkeypatch.setattr(live_sync, "_connect_lamin", lambda _: None)
    monkeypatch.setattr(live_sync, "_configure_sqlite_timeout", lambda: None)
    monkeypatch.setattr(live_sync, "_registry_models", lambda: (FakeKGEdge, FakeKGEdgeEvidence))

    summaries = live_sync.sync_parquet_edges_to_lamindb(
        root,
        relations=["disease_associated_gene"],
        edge_limit=1,
        evidence_limit=1,
        write=False,
    )

    assert summaries[0].status == "dry_run"
    assert summaries[0].edge_rows_available == 2
    assert summaries[0].edge_rows_selected == 1
    assert summaries[0].evidence_rows_available == 1
    assert summaries[0].evidence_rows_selected == 1
    assert FakeKGEdge.objects.records == {}
    assert FakeKGEdgeEvidence.objects.records == {}


def test_live_sync_write_is_idempotent_and_preserves_exact_fields(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "kg"
    _write_edge_fixture(root)
    FakeKGEdge.objects = FakeManager()
    FakeKGEdgeEvidence.objects = FakeManager()
    monkeypatch.setattr(live_sync, "_connect_lamin", lambda _: None)
    monkeypatch.setattr(live_sync, "_configure_sqlite_timeout", lambda: None)
    monkeypatch.setattr(live_sync, "_registry_models", lambda: (FakeKGEdge, FakeKGEdgeEvidence))

    summaries = []
    for _ in range(2):
        summaries = live_sync.sync_parquet_edges_to_lamindb(
            root,
            relations=["disease_associated_gene"],
            edge_limit=2,
            evidence_limit=1,
            write=True,
        )

    summary = summaries[0]
    assert summary.status == "bounded live sync accepted"
    assert summary.edge_upserts == 2
    assert summary.evidence_upserts == 1
    assert summary.edge_count_after == 2
    assert summary.evidence_count_after == 1
    assert len(FakeKGEdge.objects.records) == 2
    assert len(FakeKGEdgeEvidence.objects.records) == 1

    edge = next(row for row in FakeKGEdge.objects.records.values() if row["source"] == "OpenTargets")
    assert edge["x_id"] == "NCBI:672"
    assert edge["x_type"] == "gene"
    assert edge["y_id"] == "EFO:0000305"
    assert edge["y_type"] == "disease"
    assert edge["relation"] == "disease_associated_gene"
    assert edge["metadata"] == {"score": 0.88}

    evidence = next(iter(FakeKGEdgeEvidence.objects.records.values()))
    assert evidence["edge_key"] != "legacy-key-is-recomputed"
    assert evidence["source_dataset"] == "reactome"
    assert evidence["source_record_id"] == "fixture-record"
    assert evidence["metadata"] == {"release": "fixture"}
