from __future__ import annotations

import pandas as pd
import pyarrow as pa

from manage_db.build_staged_mutation_genomic_edges import build_edges_from_variants


def _variant_table() -> pa.Table:
    return pa.Table.from_pylist([
        {
            "variantId": "1_100_A_G",
            "chromosome": "1",
            "position": 100,
            "referenceAllele": "A",
            "alternateAllele": "G",
            "hgvsId": "1:g.100A>G",
            "rsIds": ["rs1"],
            "transcriptConsequences": [
                {
                    "variantFunctionalConsequenceIds": ["SO_0001627"],
                    "isEnsemblCanonical": True,
                    "targetId": "ENSG000001",
                    "transcriptId": "ENST000001",
                    "impact": "MODIFIER",
                    "biotype": "protein_coding",
                    "consequenceScore": 0.3,
                    "distanceFromTss": 0,
                    "distanceFromFootprint": 0,
                    "approvedSymbol": "GENE1",
                }
            ],
        },
        {
            "variantId": "1_500_C_T",
            "chromosome": "1",
            "position": 500,
            "referenceAllele": "C",
            "alternateAllele": "T",
            "hgvsId": "1:g.500C>T",
            "rsIds": [],
            "transcriptConsequences": [
                {
                    "variantFunctionalConsequenceIds": ["SO_0001583"],
                    "targetId": "ENSG000002",
                    "transcriptId": "ENST000002",
                    "impact": "MODERATE",
                    "biotype": "protein_coding",
                    "consequenceScore": 0.8,
                }
            ],
        },
    ])


def test_direct_gene_and_transcript_edges_preserve_consequence_evidence() -> None:
    enhancers = pd.DataFrame(columns=["id", "chromosome", "start", "end"])
    edges, evidence, nodes, summary = build_edges_from_variants(_variant_table(), set(), enhancers)

    assert summary["edge_rows"]["mutation_in_gene"] == 2
    assert summary["edge_rows"]["mutation_affects_transcript"] == 2
    assert summary["edge_rows"]["mutation_overlaps_enhancer"] == 0
    assert set(edges["mutation_in_gene"]["y_id"]) == {"ENSG000001", "ENSG000002"}
    assert set(edges["mutation_affects_transcript"]["y_id"]) == {"ENST000001", "ENST000002"}
    assert len(nodes) == 2
    text_span = evidence["mutation_affects_transcript"].iloc[0]["text_span"]
    assert "SO_0001627" in text_span
    assert "1:g.100A>G" in text_span


def test_enhancer_overlap_requires_downstream_association_gate() -> None:
    enhancers = pd.DataFrame([
        {"id": "enh_supported", "chromosome": "1", "start": 90, "end": 110},
        {"id": "enh_ungated", "chromosome": "1", "start": 490, "end": 510},
    ])

    edges, evidence, _nodes, summary = build_edges_from_variants(
        _variant_table(), {"1_100_A_G"}, enhancers
    )

    assert summary["edge_rows"]["mutation_overlaps_enhancer"] == 1
    overlap = edges["mutation_overlaps_enhancer"].iloc[0]
    assert overlap["x_id"] == "1_100_A_G"
    assert overlap["y_id"] == "enh_supported"
    assert "downstream_association_gate" in evidence["mutation_overlaps_enhancer"].iloc[0]["text_span"]
