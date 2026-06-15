from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

from manage_db.audit_lamindb_parity import (
    _registry_value_tokens,
    audit_node_type,
)
from manage_db.kg_storage import open_kg_root, write_nodes


class _Field:
    def __init__(self, name: str) -> None:
        self.name = name


class _Meta:
    fields = [
        _Field("ensembl_protein_id"),
        _Field("ensembl_gene_id"),
        _Field("uniprot_id"),
        _Field("refseq_protein"),
        _Field("pdb_ids"),
    ]


class _Values:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def iterator(self):
        return iter(self._values)


class _QuerySet:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def values_list(self, field: str, flat: bool = False) -> _Values:
        assert flat
        return _Values([row[field] for row in self._rows if row.get(field) is not None])


class _Objects:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def exclude(self, **kwargs) -> _QuerySet:
        (lookup, expected), = kwargs.items()
        assert lookup.endswith("__isnull")
        assert expected is True
        field = lookup.removesuffix("__isnull")
        return _QuerySet([row for row in self._rows if row.get(field) is not None])


class Protein:
    _meta = _Meta()
    objects = _Objects(
        [
            {
                "ensembl_protein_id": "ENSP00000369497",
                "ensembl_gene_id": "ENSG00000139618",
                "uniprot_id": "P51587",
                "refseq_protein": "NP_000050.2",
                "pdb_ids": "1ABC|2DEF",
            }
        ]
    )


def _empty_registry(name: str):
    return type(name, (), {"_meta": type("Meta", (), {"fields": []})(), "objects": _Objects([])})


def _install_fake_lamindb_modules(monkeypatch) -> None:
    bionty = types.SimpleNamespace(
        Gene=_empty_registry("Gene"),
        Disease=_empty_registry("BiontyDisease"),
        Phenotype=_empty_registry("Phenotype"),
        Pathway=_empty_registry("Pathway"),
        Tissue=_empty_registry("Tissue"),
        CellType=_empty_registry("CellType"),
        Organism=_empty_registry("Organism"),
        CellLine=_empty_registry("CellLine"),
    )
    pertdb = types.SimpleNamespace(Compound=_empty_registry("Compound"))
    lnschema_txgnn = types.SimpleNamespace(
        Gene=_empty_registry("TxGene"),
        Molecule=_empty_registry("TxMolecule"),
        Pathway=_empty_registry("TxPathway"),
        Tissue=_empty_registry("TxTissue"),
        CellType=_empty_registry("TxCellType"),
        Paper=_empty_registry("Paper"),
        Transcript=_empty_registry("Transcript"),
        Disease=_empty_registry("Disease"),
        Protein=Protein,
        Mutation=_empty_registry("Mutation"),
        Enhancer=_empty_registry("Enhancer"),
        Dataset=_empty_registry("Dataset"),
    )
    monkeypatch.setitem(sys.modules, "bionty", bionty)
    monkeypatch.setitem(sys.modules, "pertdb", pertdb)
    monkeypatch.setitem(sys.modules, "lnschema_txgnn", lnschema_txgnn)


def test_registry_value_tokens_split_pipe_separated_xrefs() -> None:
    assert list(_registry_value_tokens(" 1ABC | 2DEF ")) == ["1ABC", "2DEF"]


def test_audit_node_type_maps_protein_to_custom_registry(monkeypatch, tmp_path: Path) -> None:
    _install_fake_lamindb_modules(monkeypatch)
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "protein",
        pd.DataFrame(
            [
                {"id": "ENSP00000369497", "name": "matched protein", "ensembl_gene_id": None, "uniprot_id": None, "refseq_protein": None, "pdb_ids": None},
                {"id": "ENSP00000400000", "name": "missing protein", "ensembl_gene_id": None, "uniprot_id": None, "refseq_protein": None, "pdb_ids": None},
            ]
        ),
    )

    parity = audit_node_type(root, "protein", sample_size=5)

    assert parity.registry.endswith("test_audit_lamindb_parity.Protein")
    assert parity.registry_key_fields == ["ensembl_protein_id"]
    assert parity.matched_ids == 1
    assert parity.missing_ids == 1
    assert parity.sample_missing == ["ENSP00000400000"]
    assert parity.status == "missing"


def test_audit_node_type_does_not_match_protein_by_uniprot_xref(
    monkeypatch, tmp_path: Path
) -> None:
    _install_fake_lamindb_modules(monkeypatch)
    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "protein",
        pd.DataFrame(
            [
                {
                    "id": "P51587",
                    "name": "uniprot xref should not be treated as KG protein ID",
                    "ensembl_gene_id": None,
                    "uniprot_id": None,
                    "refseq_protein": None,
                    "pdb_ids": None,
                },
            ]
        ),
    )

    parity = audit_node_type(root, "protein", sample_size=5)

    assert parity.registry.endswith("test_audit_lamindb_parity.Protein")
    assert parity.registry_key_fields == ["ensembl_protein_id"]
    assert parity.matched_ids == 0
    assert parity.missing_ids == 1
    assert parity.sample_missing == ["P51587"]


def test_audit_node_type_reports_schema_pending_for_missing_registry_table(monkeypatch, tmp_path: Path) -> None:
    from manage_db.audit_lamindb_parity import OperationalError

    class PendingMeta(_Meta):
        db_table = "lnschema_txgnn_protein"

    class PendingObjects(_Objects):
        def exclude(self, **kwargs):
            raise OperationalError("no such table: lnschema_txgnn_protein")

    class PendingProtein:
        _meta = PendingMeta()
        objects = PendingObjects([])

    _install_fake_lamindb_modules(monkeypatch)
    sys.modules["lnschema_txgnn"].Protein = PendingProtein

    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "protein",
        pd.DataFrame([{
            "id": "ENSP00000369497",
            "ensembl_gene_id": None,
            "uniprot_id": None,
            "refseq_protein": None,
            "pdb_ids": None,
        }, {
            "id": "ENSP00000439902",
            "ensembl_gene_id": None,
            "uniprot_id": None,
            "refseq_protein": None,
            "pdb_ids": None,
        }]),
    )

    parity = audit_node_type(root, "protein", sample_size=1)

    assert parity.status == "schema_pending"
    assert parity.lamindb_key_values == 0
    assert parity.matched_ids == 0
    assert parity.missing_ids == 2
    assert parity.sample_missing == ["ENSP00000369497"]


def test_audit_node_type_does_not_hide_other_operational_errors(monkeypatch, tmp_path: Path) -> None:
    from manage_db.audit_lamindb_parity import OperationalError
    import pytest

    class ErrorMeta(_Meta):
        db_table = "lnschema_txgnn_protein"

    class ErrorObjects(_Objects):
        def exclude(self, **kwargs):
            raise OperationalError("no such column: broken_column")

    class ErrorProtein:
        _meta = ErrorMeta()
        objects = ErrorObjects([])

    _install_fake_lamindb_modules(monkeypatch)
    sys.modules["lnschema_txgnn"].Protein = ErrorProtein

    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(root, "protein", pd.DataFrame([{
        "id": "ENSP00000369497",
        "ensembl_gene_id": None,
        "uniprot_id": None,
        "refseq_protein": None,
        "pdb_ids": None,
    }]))

    with pytest.raises(OperationalError, match="broken_column"):
        audit_node_type(root, "protein")


def test_audit_node_type_normalizes_disease_ids(monkeypatch, tmp_path: Path) -> None:
    class DiseaseMeta:
        fields = [_Field("ontology_id"), _Field("name")]

    class Disease:
        _meta = DiseaseMeta()
        objects = _Objects([{"ontology_id": "MONDO:0005148", "name": "type 2 diabetes mellitus"}])

    _install_fake_lamindb_modules(monkeypatch)
    sys.modules["lnschema_txgnn"].Disease = Disease

    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "disease",
        pd.DataFrame([
            {"id": "MONDO_0005148", "name": "type 2 diabetes mellitus", "mondo_id": "MONDO_0005148", "omim_id": None, "doid_id": None, "icd10_code": None, "mesh_id": None, "hp_id": None},
            {"id": "EFO_0000094", "name": "EFO_0000094", "mondo_id": None, "omim_id": None, "doid_id": None, "icd10_code": None, "mesh_id": None, "hp_id": None},
        ]),
    )

    parity = audit_node_type(root, "disease", sample_size=5)

    assert parity.matched_ids == 1
    assert parity.missing_ids == 1
    assert parity.sample_missing == ["EFO:0000094"]


def test_audit_node_type_uses_custom_exact_id_registry_for_residual_public_gaps(
    monkeypatch, tmp_path: Path
) -> None:
    class GeneMeta:
        fields = [_Field("ensembl_gene_id"), _Field("symbol")]

    class Gene:
        _meta = GeneMeta()
        objects = _Objects([{"ensembl_gene_id": "ENSG00000139618", "symbol": "BRCA2"}])

    _install_fake_lamindb_modules(monkeypatch)
    sys.modules["lnschema_txgnn"].Gene = Gene

    root = open_kg_root(str(tmp_path / "kg"))
    write_nodes(
        root,
        "gene",
        pd.DataFrame([
            {
                "id": "ENSG00000139618",
                "gene_name": "BRCA2",
                "ncbi_gene_id": None,
                "hgnc_id": None,
                "uniprot_id": None,
            },
            {
                "id": "ENSG00000200000",
                "gene_name": "missing exact gene",
                "ncbi_gene_id": None,
                "hgnc_id": None,
                "uniprot_id": None,
            },
        ]),
    )

    parity = audit_node_type(root, "gene", sample_size=5)

    assert parity.registry.endswith("test_audit_lamindb_parity.Gene")
    assert parity.registry_key_fields == ["ensembl_gene_id"]
    assert parity.matched_ids == 1
    assert parity.missing_ids == 1
    assert parity.sample_missing == ["ENSG00000200000"]
