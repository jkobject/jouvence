from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db.kg_ids import normalize_ontology_curie
from manage_db.normalize_ontology_id_separators import normalize_kg


def _write(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def test_normalize_ontology_curie_supports_disease_and_cell_type_prefixes() -> None:
    assert normalize_ontology_curie("EFO_0000094") == "EFO:0000094"
    assert normalize_ontology_curie("MONDO_0001493") == "MONDO:0001493"
    assert normalize_ontology_curie("CL_0000576") == "CL:0000576"
    assert normalize_ontology_curie("DOID_0050890") == "DOID:0050890"
    assert normalize_ontology_curie("NCIT_C117245") == "NCIT:C117245"
    assert normalize_ontology_curie("Orphanet_1259") == "Orphanet:1259"


def test_normalize_kg_rewrites_selected_nodes_and_edge_endpoints(tmp_path: Path) -> None:
    input_root = tmp_path / "kg"
    output_root = tmp_path / "out"
    _write(
        input_root / "nodes" / "disease.parquet",
        pd.DataFrame(
            [
                {"id": "EFO_0000094", "mondo_id": "MONDO_0000001", "hp_id": "HP_0000001"},
                {"id": "MONDO:0000002", "mondo_id": "MONDO:0000002", "hp_id": None},
            ]
        ),
    )
    _write(
        input_root / "nodes" / "cell_type.parquet",
        pd.DataFrame([{"id": "CL_0000576", "mesh_id": None, "uberon_id": "UBERON_0002048"}]),
    )
    _write(
        input_root / "edges" / "disease_subtype_of_disease.parquet",
        pd.DataFrame(
            [
                {
                    "x_id": "EFO_0000094",
                    "x_type": "disease",
                    "y_id": "MONDO_0000002",
                    "y_type": "disease",
                    "relation": "disease_subtype_of_disease",
                    "display_relation": "subtype of",
                    "source": "test",
                    "credibility": 1,
                }
            ]
        ),
    )
    _write(
        input_root / "edges" / "cell_type_expresses_gene.parquet",
        pd.DataFrame(
            [
                {
                    "x_id": "CL_0000576",
                    "x_type": "cell_type",
                    "y_id": "ENSG000001",
                    "y_type": "gene",
                    "relation": "cell_type_expresses_gene",
                    "display_relation": "expresses",
                    "source": "test",
                    "credibility": 1,
                }
            ]
        ),
    )

    reports = normalize_kg(input_root, output_root)

    assert {report.name for report in reports} == {
        "disease",
        "cell_type",
        "disease_subtype_of_disease",
        "cell_type_expresses_gene",
    }
    disease = pq.read_table(output_root / "nodes" / "disease.parquet").to_pandas()
    assert disease.loc[0, "id"] == "EFO:0000094"
    assert disease.loc[0, "mondo_id"] == "MONDO:0000001"
    assert disease.loc[0, "hp_id"] == "HP:0000001"
    cell = pq.read_table(output_root / "nodes" / "cell_type.parquet").to_pandas()
    assert cell.loc[0, "id"] == "CL:0000576"
    assert cell.loc[0, "uberon_id"] == "UBERON:0002048"
    edge = pq.read_table(output_root / "edges" / "disease_subtype_of_disease.parquet").to_pandas()
    assert edge.loc[0, "x_id"] == "EFO:0000094"
    assert edge.loc[0, "y_id"] == "MONDO:0000002"
    cell_edge = pq.read_table(output_root / "edges" / "cell_type_expresses_gene.parquet").to_pandas()
    assert cell_edge.loc[0, "x_id"] == "CL:0000576"
    assert cell_edge.loc[0, "y_id"] == "ENSG000001"
