from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def fake_work(openalex_id: str, *, pmid: str, doi: str, title: str, refs: list[str] | None = None) -> dict:
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "doi": f"https://doi.org/{doi}",
        "title": title,
        "publication_date": "2024-01-01",
        "ids": {
            "openalex": f"https://openalex.org/{openalex_id}",
            "doi": f"https://doi.org/{doi}",
            "pmid": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
        },
        "referenced_works": [f"https://openalex.org/{r}" for r in (refs or [])],
    }


def test_paper_dataset_provenance_builder_stages_metadata_only(tmp_path: Path, monkeypatch) -> None:
    from manage_db import build_paper_dataset_provenance as mod

    works = {
        "PMID:39657122": fake_work("WOT", pmid="39657122", doi="10.1093/nar/gkae1128", title="Open Targets Platform", refs=["WREF1"]),
        "PMID:28753430": fake_work("WDEP", pmid="28753430", doi="10.1016/j.cell.2017.06.010", title="Defining a Cancer Dependency Map", refs=["WREF2"]),
        "WREF1": fake_work("WREF1", pmid="11111111", doi="10.1000/ref1", title="Reference 1"),
        "WREF2": fake_work("WREF2", pmid="22222222", doi="10.1000/ref2", title="Reference 2"),
    }

    def mock_fetch(identifier: str) -> dict:
        key = identifier if identifier in works else identifier.rsplit("/", 1)[-1]
        return works[key]

    monkeypatch.setattr(mod, "fetch_openalex_work", mock_fetch)
    monkeypatch.setattr(
        mod,
        "audit_metadata_sources",
        lambda accessed_at: [
            {
                "source": "OpenAlex",
                "url": "https://api.openalex.org/works?per-page=1",
                "ok": True,
                "status": 200,
                "license": "OpenAlex CC0",
                "used_for": "citation metadata",
                "accessed_at": accessed_at,
            }
        ],
    )

    raw_root = tmp_path / "raw"
    drug_dir = raw_root / "opentargets" / "26.03" / "drug_molecule"
    drug_dir.mkdir(parents=True)
    pd.DataFrame([{"id": "CHEMBL1", "name": "Drug A"}, {"id": "not-a-chembl", "name": "skip"}]).to_parquet(drug_dir / "part.parquet", index=False)

    te_dir = raw_root / "opentargets-26.03" / "target_essentiality"
    te_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "id": "ENSG000001",
                "geneEssentiality": [
                    {
                        "isEssential": True,
                        "depMapEssentiality": [
                            {
                                "tissueId": "UBERON_0002107",
                                "screens": [
                                    {
                                        "depmapId": "ACH-000001",
                                        "diseaseCellLineId": "EFO_0000305",
                                        "cellLineName": "A",
                                    },
                                    {"depmapId": "ACH-000002", "diseaseCellLineId": "SIDM0001"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    ).to_parquet(te_dir / "part.parquet", index=False)

    kg_root = tmp_path / "kg"
    nodes = kg_root / "nodes"
    nodes.mkdir(parents=True)
    pd.DataFrame([{"id": "CHEMBL1"}]).to_parquet(nodes / "molecule.parquet", index=False)
    pd.DataFrame([{"id": "ACH-000001"}, {"id": "ACH-000002"}]).to_parquet(nodes / "cell_line.parquet", index=False)
    pd.DataFrame([{"id": "UBERON:0002107"}]).to_parquet(nodes / "tissue.parquet", index=False)
    pd.DataFrame([{"id": "EFO:0000305"}]).to_parquet(nodes / "disease.parquet", index=False)
    pd.DataFrame([{"id": "CL:0000576", "name": "monocyte", "source": "OpenTargets"}]).to_parquet(nodes / "cell_type.parquet", index=False)

    result = mod.build_paper_dataset_provenance(raw_root, kg_root, max_rows=10, max_refs_per_paper=1)
    out = tmp_path / "stage"
    manifest = mod.write_outputs(result, out)

    assert manifest["ok"]
    assert manifest["canonical_promotion"] is False
    assert result.validation["only_metadata_or_literature_relations"] is True
    assert result.validation["no_paper_comention_biological_assertions"] is True

    produced = pd.read_parquet(out / "edges" / "paper_produced_dataset.parquet")
    assert set(produced["relation"]) == {"paper_produced_dataset"}
    assert "PMID:39657122" in set(produced["x_id"])
    assert set(produced["y_type"]) == {"dataset"}

    citations = pd.read_parquet(out / "edges" / "paper_cites_paper.parquet")
    assert set(citations["citation_direction"]) == {"x_cites_y"}
    assert {"PMID:11111111", "PMID:22222222"} <= set(citations["y_id"])

    molecules = pd.read_parquet(out / "edges" / "dataset_contains_molecule.parquet")
    assert molecules.to_dict("records")[0]["y_id"] == "CHEMBL1"

    disease = pd.read_parquet(out / "edges" / "dataset_contains_disease.parquet")
    assert set(disease["y_id"]) == {"EFO:0000305"}

    cell_types = pd.read_parquet(out / "edges" / "dataset_contains_cell_type.parquet")
    assert cell_types.to_dict("records")[0]["y_id"] == "CL:0000576"

    ev = pd.read_parquet(out / "evidence" / "paper_produced_dataset.parquet")
    assert {"doi", "pmid", "source_record_id", "mapping_confidence", "source_release"} <= set(ev.columns)
    assert ev["doi"].str.startswith("DOI:").all()

    report = json.loads((out / "validation" / "paper_dataset_provenance_build_report.json").read_text())
    assert report["validation"]["endpoint_anti_joins"]["dataset_contains_molecule"]["missing_y_count"] == 0
