from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _write_node_fixtures(node_root: Path) -> None:
    node_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"id": "ENSG00000141510", "description": "tumor protein p53", "source": "OpenTargets", "name": "TP53"}]
    ).to_parquet(node_root / "gene.parquet", index=False)
    pd.DataFrame(
        [{"id": "ENSP00000269305", "uniprot_id": "P04637", "name": "TP53_HUMAN", "source": "OpenTargets"}]
    ).to_parquet(node_root / "protein.parquet", index=False)
    pd.DataFrame(
        [{"id": "EFO:0000305", "description": "A disease of abnormal cell proliferation.", "source": "OpenTargets"}]
    ).to_parquet(node_root / "disease.parquet", index=False)
    pd.DataFrame([{"id": "UBERON:0002107", "name": "liver", "source": "OpenTargets"}]).to_parquet(
        node_root / "tissue.parquet", index=False
    )
    pd.DataFrame(
        [{"id": "CHEMBL1000", "description": "Small molecule drug with approved indications.", "source": "OpenTargets"}]
    ).to_parquet(node_root / "molecule.parquet", index=False)
    pd.DataFrame([{"id": "GO:0006915", "go_id": "GO:0006915", "name": "apoptotic process", "source": "GO"}]).to_parquet(
        node_root / "pathway.parquet", index=False
    )


def _write_obo(path: Path, term_id: str, name: str, definition: str) -> None:
    path.write_text(
        f"format-version: 1.2\n\n[Term]\nid: {term_id}\nname: {name}\ndef: \"{definition}\" [xref]\n",
        encoding="utf-8",
    )


def test_stage_textual_summary_features_writes_all_fixture_tables(tmp_path: Path) -> None:
    from manage_db.build_textual_summary_features import stage_textual_summary_features

    node_root = tmp_path / "nodes"
    _write_node_fixtures(node_root)
    uberon = tmp_path / "uberon-basic.obo"
    go = tmp_path / "go-basic.obo"
    _write_obo(uberon, "UBERON:0002107", "liver", "An organ that metabolizes nutrients and detoxifies compounds.")
    _write_obo(go, "GO:0006915", "apoptotic process", "A programmed cell death process.")
    entries_json = tmp_path / "uniprot_entries.json"
    entries_json.write_text(
        json.dumps(
            {
                "release": "2099_01",
                "entries": [
                    {
                        "primaryAccession": "P04637",
                        "comments": [
                            {"commentType": "FUNCTION", "texts": [{"value": "Acts as a tumor suppressor."}]},
                            {
                                "commentType": "SUBCELLULAR LOCATION",
                                "locations": [{"location": {"value": "Nucleus"}}],
                            },
                            {"commentType": "SIMILARITY", "texts": [{"value": "Ignored."}]},
                        ],
                    }
                ],
            }
        )
    )

    output = tmp_path / "staged"
    summary = stage_textual_summary_features(
        node_root=str(node_root),
        output_root=str(output),
        release="fixture_release",
        uberon_obo=str(uberon),
        go_obo=str(go),
        uniprot_entries_json=str(entries_json),
    )

    assert summary["staging_only"] is True
    assert summary["canonical_promotion"] is False
    for table in [
        "gene_textual_summary",
        "protein_textual_summary",
        "disease_textual_summary",
        "tissue_textual_summary",
        "molecule_textual_summary",
        "pathway_textual_summary",
    ]:
        assert summary["tables"][table]["rows"] == 1
        assert (output / "features" / f"{table}.parquet").exists()
    assert (output / "reports" / "textual_summary_source_audit.csv").exists()
    assert (output / "reports" / "textual_summary_features_summary.json").exists()

    protein = pd.read_parquet(output / "features" / "protein_textual_summary.parquet")
    assert "FUNCTION: Acts as a tumor suppressor." in protein.loc[0, "summary_text"]
    assert "Subcellular location: Nucleus" in protein.loc[0, "summary_text"]


def test_stage_textual_summary_features_records_missing_sources_without_placeholder_tables(tmp_path: Path) -> None:
    from manage_db.build_textual_summary_features import stage_textual_summary_features

    node_root = tmp_path / "nodes"
    node_root.mkdir(parents=True)
    pd.DataFrame([{"id": "ENSP00000269305", "uniprot_id": "P04637"}]).to_parquet(
        node_root / "protein.parquet", index=False
    )

    summary = stage_textual_summary_features(
        node_root=str(node_root), output_root=str(tmp_path / "staged"), release="fixture_release"
    )

    assert summary["tables"]["protein_textual_summary"]["rows"] == 0
    assert "No acceptable local source rows" in summary["tables"]["protein_textual_summary"]["reason"]
    assert not (tmp_path / "staged" / "features" / "protein_textual_summary.parquet").exists()
