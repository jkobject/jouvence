from __future__ import annotations

from pathlib import Path

import pandas as pd

from manage_db.kg_storage import open_kg_root, write_edges


def test_backfill_edge_evidence_from_existing_edges(tmp_path: Path) -> None:
    from manage_db.audit_edge_evidence import audit_edge_evidence
    from manage_db.backfill_edge_evidence import backfill_edge_evidence
    from manage_db.kg_evidence import read_evidence

    root = open_kg_root(str(tmp_path / "kg"))
    write_edges(
        root,
        "disease_involves_pathway",
        pd.DataFrame(
            [
                {
                    "x_id": "EFO:1",
                    "x_type": "disease",
                    "y_id": "R-HSA-1",
                    "y_type": "pathway",
                    "relation": "disease_involves_pathway",
                    "display_relation": "involves pathway",
                    "source": "OpenTargets/reactome",
                    "credibility": 2,
                    "score": 0.71,
                    "pathway_name": "Example pathway",
                }
            ]
        ),
    )

    assert backfill_edge_evidence(tmp_path / "kg", ["disease_involves_pathway"]) == {
        "disease_involves_pathway": 1
    }

    evidence = read_evidence(root, "disease_involves_pathway")
    assert len(evidence) == 1
    assert evidence.loc[0, "edge_key"] == "disease_involves_pathway|EFO:1|R-HSA-1"
    assert evidence.loc[0, "source"] == "OpenTargets"
    assert evidence.loc[0, "source_dataset"] == "reactome"
    assert evidence.loc[0, "source_record_id"] == "OpenTargets/reactome:disease_involves_pathway:EFO:1:R-HSA-1"
    assert evidence.loc[0, "evidence_score"] == 0.71
    assert evidence.loc[0, "predicate"] == "disease_involves_pathway"

    audit = audit_edge_evidence(tmp_path / "kg", relations=["disease_involves_pathway"])
    assert audit.ok
