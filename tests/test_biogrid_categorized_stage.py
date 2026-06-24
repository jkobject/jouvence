from __future__ import annotations

import sys
import gzip
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".omoc" / "scripts"))

from stage_biogrid_categorized import (  # noqa: E402
    TAB3_COLUMNS,
    augment_refseq_map_from_uniprot_idmapping,
    build_accession_maps,
    build_ptm_sites,
    classify_experimental_system,
    ptm_site_id,
    ptmtab_refseq_rejection_table,
    refseq_xref_audit_tables,
    residue_matches_sequence,
    route_tab3_row,
)


def _tab3_row(**overrides: str) -> pd.Series:
    values = {col: "-" for col in TAB3_COLUMNS}
    values.update(
        {
            "BioGRID Interaction ID": "1",
            "Experimental System": "Two-hybrid",
            "Experimental System Type": "physical",
            "Organism ID Interactor A": "9606",
            "Organism ID Interactor B": "9606",
            "SWISS-PROT Accessions Interactor A": "P11111",
            "SWISS-PROT Accessions Interactor B": "P22222",
        }
    )
    values.update(overrides)
    return pd.Series(values)


def _maps() -> dict[str, dict[str, str]]:
    return build_accession_maps(
        pd.DataFrame(
            [
                {"id": "ENSP_A", "uniprot_id": "P11111", "refseq_protein": "NP_000001"},
                {"id": "ENSP_B", "uniprot_id": "P22222", "refseq_protein": "NP_000002"},
                {"id": "ENSP_C", "uniprot_id": "Q33333", "refseq_protein": "NP_000003"},
            ]
        )
    )


def test_biogrid_physical_routes_only_source_protein_mapped_rows() -> None:
    route, payload = route_tab3_row(_tab3_row(), _maps())
    assert route == "protein_interacts_protein"
    assert payload["x_id"] == "ENSP_A"
    assert payload["y_id"] == "ENSP_B"
    assert payload["evidence_class"] == "binary_physical"

    route, payload = route_tab3_row(
        _tab3_row(**{"SWISS-PROT Accessions Interactor B": "-", "REFSEQ Accessions Interactor B": "-"}),
        _maps(),
    )
    assert route == "excluded"
    assert "endpoint_mapping_failed" in payload["reason"]


def test_biogrid_genetic_and_nonhuman_rows_are_excluded_from_ppi() -> None:
    route, payload = route_tab3_row(
        _tab3_row(**{"Experimental System Type": "genetic", "Experimental System": "Synthetic Lethality"}),
        _maps(),
    )
    assert route == "genetic_excluded"
    assert payload["reason"] == "genetic_interaction_not_protein_mechanism"

    route, payload = route_tab3_row(_tab3_row(**{"Organism ID Interactor B": "10090"}), _maps())
    assert route == "excluded"
    assert payload["reason"] == "non_human_endpoint"


def test_complex_like_biogrid_tab3_is_physical_evidence_not_complex_node() -> None:
    assert classify_experimental_system("Affinity Capture-MS") == "complex_or_cofractionation_association"
    route, payload = route_tab3_row(_tab3_row(**{"Experimental System": "Affinity Capture-MS"}), _maps())
    assert route == "protein_interacts_protein"
    assert payload["evidence_class"] == "complex_or_cofractionation_association"


def test_ambiguous_protein_xref_is_dropped_not_projected() -> None:
    maps = build_accession_maps(
        pd.DataFrame(
            [
                {"id": "ENSP_A1", "uniprot_id": "P11111", "refseq_protein": "NP_1"},
                {"id": "ENSP_A2", "uniprot_id": "P11111", "refseq_protein": "NP_2"},
                {"id": "ENSP_B", "uniprot_id": "P22222", "refseq_protein": "NP_3"},
            ]
        )
    )
    assert "P11111" not in maps["uniprot"]
    route, payload = route_tab3_row(_tab3_row(), maps)
    assert route == "excluded"
    assert "endpoint_mapping_failed:no_source_protein_accession_mapping" in payload["reason"]


def test_ptm_site_id_is_stable_and_site_specific() -> None:
    assert ptm_site_id("ENSP_A", "Phosphorylation", "S", "42") == "PTMSite:ENSP_A_phosphorylation_S_42"


def test_refseq_ptm_mapping_can_use_uniprot_human_idmapping(tmp_path: Path) -> None:
    protein_nodes = pd.DataFrame(
        [
            {"id": "ENSP_A", "uniprot_id": "P11111", "refseq_protein": ""},
            {"id": "ENSP_B", "uniprot_id": "P22222", "refseq_protein": ""},
            {"id": "ENSP_C1", "uniprot_id": "Q33333", "refseq_protein": ""},
            {"id": "ENSP_C2", "uniprot_id": "Q33333", "refseq_protein": ""},
        ]
    )
    maps = build_accession_maps(protein_nodes)
    idmapping = tmp_path / "HUMAN_9606_idmapping.dat.gz"
    with gzip.open(idmapping, "wt", encoding="utf-8") as fh:
        fh.write("P11111\tRefSeq\tNP_000001.2\n")
        fh.write("P22222\tRefSeq\tXP_000002.1\n")
        fh.write("Q33333\tRefSeq\tNP_000003.1\n")  # ambiguous UniProt -> ENSP, rejected
        fh.write("P11111\tGeneID\t1\n")  # ignored: not protein RefSeq

    report = augment_refseq_map_from_uniprot_idmapping(maps, protein_nodes, idmapping)

    assert report["status"] == "loaded"
    assert maps["refseq"]["NP_000001"] == "ENSP_A"
    assert maps["refseq"]["XP_000002"] == "ENSP_B"
    assert "NP_000003" not in maps["refseq"]


def test_ptm_build_preserves_mapping_evidence_and_validates_residue(tmp_path: Path) -> None:
    zip_path = tmp_path / "BIOGRID-PTMS-test.ptm.zip"
    row_ok = [
        "PTM1", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000001.2", "2", "Phosphorylation", "S",
        "Author", "123", "9606", "Homo sapiens", "Yes", "note", "BioGRID",
    ]
    row_bad_residue = [
        "PTM2", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000001.2", "3", "Phosphorylation", "S",
        "Author", "123", "9606", "Homo sapiens", "Yes", "note", "BioGRID",
    ]
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("BIOGRID-PTM-test.ptmtab.txt", "\n".join("\t".join(r) for r in [row_ok, row_bad_residue]) + "\n")
        zf.writestr("BIOGRID-PTM-RELATIONSHIPS-test.ptmrel.txt", "PTM1\t1\tBG1\tSYS\tGENE\t-\tkinase\tcatalytic\tAuthor\t123\t9606\tHomo sapiens\n")

    maps = {"uniprot": {}, "refseq": {"NP_000001": "ENSP_A"}}
    nodes, edges, evidence, report = build_ptm_sites(zip_path, maps, chunksize=10)

    assert report["counts"]["ptmtab_excluded_sequence_residue_mismatch"] == 1
    assert len(nodes) == 1
    assert len(edges) == 1
    assert len(evidence) == 1
    assert evidence.iloc[0]["mapping_evidence"] == "protein_node_refseq_xref_or_uniprot_human_idmapping_refseq_to_uniprot"
    assert residue_matches_sequence("MST", "S", "2")
    assert not residue_matches_sequence("MST", "S", "3")



def test_refseq_xref_audit_and_ptmtab_rejection_tables(tmp_path: Path) -> None:
    protein_nodes = pd.DataFrame(
        [
            {"id": "ENSP_A", "uniprot_id": "P11111", "refseq_protein": ""},
            {"id": "ENSP_B1", "uniprot_id": "P22222", "refseq_protein": ""},
            {"id": "ENSP_B2", "uniprot_id": "P22222", "refseq_protein": ""},
        ]
    )
    maps = build_accession_maps(protein_nodes)
    idmapping = tmp_path / "HUMAN_9606_idmapping.dat.gz"
    with gzip.open(idmapping, "wt", encoding="utf-8") as fh:
        fh.write("P11111\tRefSeq\tNP_000001.2\n")
        fh.write("P22222\tRefSeq\tNP_000002.1\n")
        fh.write("P33333\tRefSeq\tNP_000003.1\n")
        fh.write("P11111\tGeneID\t1\n")

    augment_refseq_map_from_uniprot_idmapping(maps, protein_nodes, idmapping)
    accepted, rejected = refseq_xref_audit_tables(maps, protein_nodes, idmapping)

    assert accepted.loc[accepted["refseq_protein"] == "NP_000001", "mapped_protein_id"].item() == "ENSP_A"
    reasons = dict(zip(rejected["refseq_protein"], rejected["rejection_reason"]))
    assert reasons["NP_000002"] == "no_unambiguous_uniprot_to_protein_node"
    assert reasons["NP_000003"] == "no_unambiguous_uniprot_to_protein_node"

    zip_path = tmp_path / "BIOGRID-PTMS-test.ptm.zip"
    rows = [
        ["PTM1", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000001.2", "2", "Phosphorylation", "S", "Author", "123", "9606", "Homo sapiens", "Yes", "note", "BioGRID"],
        ["PTM2", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000003.1", "2", "Phosphorylation", "S", "Author", "123", "9606", "Homo sapiens", "Yes", "note", "BioGRID"],
        ["PTM3", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000001.2", "", "Phosphorylation", "S", "Author", "123", "9606", "Homo sapiens", "Yes", "note", "BioGRID"],
        ["PTM4", "1", "BG1", "SYS", "GENE", "-", "MST", "NP_000001.2", "2", "Phosphorylation", "S", "Author", "123", "10090", "Mus musculus", "Yes", "note", "BioGRID"],
    ]
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("BIOGRID-PTM-test.ptmtab.txt", "\n".join("\t".join(r) for r in rows) + "\n")
    rejection_table = ptmtab_refseq_rejection_table(zip_path, maps, chunksize=10)
    keyed = {(r.refseq_protein, r.reason): r.row_count for r in rejection_table.itertuples(index=False)}
    assert keyed[("NP_000001", "accepted")] == 1
    assert keyed[("NP_000003", "no_refseq_protein_mapping")] == 1
    assert keyed[("NP_000001", "missing_site_fields")] == 1
    assert keyed[("NP_000001", "non_human")] == 1
