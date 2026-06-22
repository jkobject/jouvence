from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.build_cell_type_context_relations import REL_DISEASE, REL_SUBTYPE, REL_TISSUE, build


def _write_nodes(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"id": ids}), path)


def test_build_cell_type_context_relations_conservative_edges(tmp_path: Path) -> None:
    obo = tmp_path / "cl.obo"
    obo.write_text(
        """
format-version: 1.2
data-version: releases/2099-01-01
ontology: cl

[Term]
id: CL:0000001
name: parent cell

[Term]
id: CL:0000002
name: child cell
is_a: CL:0000001 ! parent cell
relationship: part_of UBERON:0001000 ! explicit tissue
relationship: develops_from UBERON:0002000 ! rejected lineage context
relationship: RO:0001025 UBERON:0003000 ! located in tissue

[Term]
id: CL:0000003
name: noncanonical child
is_a: CL:0000001 ! parent cell
relationship: part_of UBERON:0001000 ! rejected noncanonical cell

[Term]
id: CL:0000004
name: obsolete child
is_obsolete: true
is_a: CL:0000001 ! parent cell

[Term]
id: CL:0000005
name: missing parent child
is_a: CL:9999999 ! missing parent
relationship: part_of UBERON:9999999 ! missing tissue
""".strip()
        + "\n"
    )
    cell_nodes = tmp_path / "nodes" / "cell_type.parquet"
    tissue_nodes = tmp_path / "nodes" / "tissue.parquet"
    disease_nodes = tmp_path / "nodes" / "disease.parquet"
    _write_nodes(cell_nodes, ["CL:0000001", "CL:0000002", "CL:0000005"])
    _write_nodes(tissue_nodes, ["UBERON:0001000", "UBERON:0003000"])
    _write_nodes(disease_nodes, ["EFO:0000001"])

    report = build(
        cl_obo_path=obo,
        canonical_cell_type_path=str(cell_nodes),
        canonical_tissue_path=str(tissue_nodes),
        canonical_disease_path=str(disease_nodes),
        output_dir=tmp_path / "out",
    )

    subtype_edges = pq.read_table(tmp_path / "out" / "edges" / f"{REL_SUBTYPE}.parquet").to_pandas()
    tissue_edges = pq.read_table(tmp_path / "out" / "edges" / f"{REL_TISSUE}.parquet").to_pandas()
    tissue_evidence = pq.read_table(tmp_path / "out" / "evidence" / f"{REL_TISSUE}.parquet").to_pandas()

    assert set(map(tuple, subtype_edges[["x_id", "y_id"]].to_records(index=False))) == {("CL:0000002", "CL:0000001")}
    assert set(map(tuple, tissue_edges[["x_id", "y_id"]].to_records(index=False))) == {
        ("CL:0000002", "UBERON:0001000"),
        ("CL:0000002", "UBERON:0003000"),
    }
    assert set(tissue_evidence["predicate"]) == {"part_of", "located_in"}
    assert report["relations"][REL_SUBTYPE]["evidence_rows"] == 1
    assert report["relations"][REL_TISSUE]["evidence_rows"] == 2
    assert report["validation"]["subtype_endpoint_antijoin_pass"] is True
    assert report["validation"]["tissue_cell_endpoint_antijoin_pass"] is True
    assert report["validation"]["tissue_tissue_endpoint_antijoin_pass"] is True
    assert report["source_audit"]["disease_cell_enrichment_resources"]["status"] == "blocked_source_gap"
    assert (tmp_path / "out" / "reports" / f"{REL_DISEASE}_source_gap.json").exists()
    assert not (tmp_path / "out" / "edges" / f"{REL_DISEASE}.parquet").exists()
