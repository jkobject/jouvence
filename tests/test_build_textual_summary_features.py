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
        [
            {"id": "ENSP00000269305", "uniprot_id": "P04637|Q9TEST", "name": "TP53_HUMAN", "source": "OpenTargets"},
            {"id": "ENSP00009999999", "uniprot_id": "Q9TEST", "name": "TEST_HUMAN", "source": "OpenTargets"},
        ]
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
    pd.DataFrame(
        [
            {"id": "GO:0006915", "go_id": "GO:0006915", "name": "apoptotic process", "source": "GO"},
            {"id": "R-HSA-109581", "reactome_id": "R-HSA-109581", "name": "Apoptosis", "source": "Reactome"},
        ]
    ).to_parquet(node_root / "pathway.parquet", index=False)
    pd.DataFrame([{"id": "CL:0000236", "name": "B cell", "source": "CL"}]).to_parquet(
        node_root / "cell_type.parquet", index=False
    )
    pd.DataFrame([{"id": "HP:0001250", "name": "Seizure", "source": "HPO"}]).to_parquet(
        node_root / "phenotype.parquet", index=False
    )
    pd.DataFrame([{"id": "ACH-000001", "name": "NIH:OVCAR-3", "source": "DepMap"}]).to_parquet(
        node_root / "cell_line.parquet", index=False
    )


def _write_obo(path: Path, term_id: str, name: str, definition: str) -> None:
    path.write_text(
        f"format-version: 1.2\n\n[Term]\nid: {term_id}\nname: {name}\ndef: \"{definition}\" [xref]\n",
        encoding="utf-8",
    )


def _write_cellosaurus_obo(path: Path) -> None:
    path.write_text(
        "format-version: 1.2\n"
        "data-version: 55.0\n"
        "date: 03:31:2026 12:00\n"
        "! Licensing information: we have chosen to apply the Creative Commons\n"
        "! Attribution 4.0 International (CC BY 4.0) license to Cellosaurus\n"
        "! (https://creativecommons.org/licenses/by/4.0/). This means that you are\n"
        "! free to copy and redistribute Cellosaurus in any medium or format.\n"
        "! You can remix, transform, and build upon Cellosaurus for any purpose,\n"
        "! even commercially. You must give appropriate credit, provide a link to\n"
        "! the license, and indicate if changes were made.\n\n"
        "[Term]\n"
        "id: CVCL_0465\n"
        "name: NIH:OVCAR-3\n"
        "xref: DepMap:ACH-000001\n"
        "comment: Ovarian carcinoma cell line established from malignant ascites.\n\n"
        "[Term]\n"
        "id: CVCL_UNMAPPED\n"
        "name: Unmapped\n"
        "xref: DepMap:ACH-999999\n"
        "comment: This row should not map to canonical nodes.\n",
        encoding="utf-8",
    )


def test_stage_textual_summary_features_writes_expanded_fixture_tables(tmp_path: Path) -> None:
    from manage_db.build_textual_summary_features import stage_textual_summary_features

    node_root = tmp_path / "nodes"
    _write_node_fixtures(node_root)
    uberon = tmp_path / "uberon-basic.obo"
    go = tmp_path / "go-basic.obo"
    cl = tmp_path / "cl.obo"
    hpo = tmp_path / "hp.obo"
    cellosaurus = tmp_path / "cellosaurus.obo"
    reactome = tmp_path / "reactome_pathways.tsv"
    _write_obo(uberon, "UBERON:0002107", "liver", "An organ that metabolizes nutrients and detoxifies compounds.")
    _write_obo(go, "GO:0006915", "apoptotic process", "A programmed cell death process.")
    _write_obo(cl, "CL:0000236", "B cell", "A lymphocyte of B lineage.")
    _write_obo(hpo, "HP:0001250", "Seizure", "A sudden episode of abnormal electrical activity in the brain.")
    _write_cellosaurus_obo(cellosaurus)
    reactome.write_text(
        "stable_id\tdescription\nR-HSA-109581\tProgrammed cell death pathway curated by Reactome.\n",
        encoding="utf-8",
    )
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
                    },
                    {
                        "primaryAccession": "Q9TEST",
                        "comments": [{"commentType": "PATHWAY", "texts": [{"value": "Participates in a test pathway."}]}],
                    },
                    {"primaryAccession": "Q9EMPTY", "comments": [{"commentType": "SIMILARITY", "texts": [{"value": "Ignored."}]}]},
                    {"primaryAccession": "Q9UNMAPPED", "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Unmapped."}]}]},
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
        cl_obo=str(cl),
        hpo_obo=str(hpo),
        cellosaurus_obo=str(cellosaurus),
        reactome_pathways_tsv=str(reactome),
        uniprot_entries_json=str(entries_json),
    )

    assert summary["staging_only"] is True
    assert summary["canonical_promotion"] is False
    expected_rows = {
        "gene_textual_summary": 1,
        "protein_textual_summary": 3,
        "disease_textual_summary": 1,
        "tissue_textual_summary": 1,
        "molecule_textual_summary": 1,
        "pathway_textual_summary": 2,
        "cell_type_textual_summary": 1,
        "phenotype_textual_summary": 1,
        "cell_line_textual_summary": 1,
    }
    for table, rows in expected_rows.items():
        assert summary["tables"][table]["rows"] == rows
        assert (output / "features" / f"{table}.parquet").exists()
    assert (output / "reports" / "textual_summary_source_audit.csv").exists()
    assert (output / "reports" / "textual_summary_features_summary.json").exists()

    protein = pd.read_parquet(output / "features" / "protein_textual_summary.parquet")
    assert set(protein["release"]) == {"2099_01"}
    assert "FUNCTION: Acts as a tumor suppressor." in protein.loc[protein["source_record_id"].eq("P04637"), "summary_text"].iloc[0]
    assert "Subcellular location: Nucleus" in protein.loc[protein["source_record_id"].eq("P04637"), "summary_text"].iloc[0]
    assert summary["source_counts"]["uniprot"]["distinct_accessions_requested"] == 2
    assert summary["source_counts"]["uniprot"]["entries_returned"] == 4
    assert summary["source_counts"]["uniprot"]["entries_with_accepted_comments"] == 2
    assert summary["source_counts"]["uniprot"]["protein_node_rows_emitted"] == 3

    cell_line = pd.read_parquet(output / "features" / "cell_line_textual_summary.parquet")
    assert cell_line.loc[0, "node_id"] == "ACH-000001"
    assert cell_line.loc[0, "source_record_id"] == "CVCL_0465"
    assert cell_line.loc[0, "source"] == "Cellosaurus"
    assert "Ovarian carcinoma" in cell_line.loc[0, "summary_text"]
    assert cell_line.loc[0, "license"] == (
        "Creative Commons Attribution 4.0 International (CC BY 4.0); "
        "https://creativecommons.org/licenses/by/4.0/; attribution/link/change-notice required"
    )
    assert cell_line.loc[0, "release"] == "55.0; date=03:31:2026 12:00"
    assert "data-version=55.0" in cell_line.loc[0, "provenance"]
    assert "date=03:31:2026 12:00" in cell_line.loc[0, "provenance"]
    audit = pd.read_csv(output / "reports" / "textual_summary_source_audit.csv").set_index("source")
    assert audit.loc["Cellosaurus", "license"] == cell_line.loc[0, "license"]
    assert "placeholder" not in audit.loc["Cellosaurus", "license"].lower()

    pathway = pd.read_parquet(output / "features" / "pathway_textual_summary.parquet")
    assert set(pathway["source"]) == {"GO", "Reactome"}


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


def test_stage_textual_summary_features_skips_unaccepted_uniprot_comments(tmp_path: Path) -> None:
    from manage_db.build_textual_summary_features import stage_textual_summary_features

    node_root = tmp_path / "nodes"
    node_root.mkdir(parents=True)
    pd.DataFrame([{"id": "ENSP00000269305", "uniprot_id": "P04637"}]).to_parquet(
        node_root / "protein.parquet", index=False
    )
    entries_json = tmp_path / "uniprot_entries.json"
    entries_json.write_text(
        json.dumps({"entries": [{"primaryAccession": "P04637", "comments": [{"commentType": "SIMILARITY", "texts": [{"value": "Ignored."}]}]}]}),
        encoding="utf-8",
    )

    summary = stage_textual_summary_features(
        node_root=str(node_root),
        output_root=str(tmp_path / "staged"),
        release="fixture_release",
        uniprot_entries_json=str(entries_json),
    )

    assert summary["tables"]["protein_textual_summary"]["rows"] == 0
    assert summary["source_counts"]["uniprot"]["entries_with_accepted_comments"] == 0
    assert not (tmp_path / "staged" / "features" / "protein_textual_summary.parquet").exists()
