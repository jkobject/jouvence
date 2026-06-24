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
        {
            "variantId": "1_900_G_A",
            "chromosome": "1",
            "position": 900,
            "referenceAllele": "G",
            "alternateAllele": "A",
            "hgvsId": "1:g.900G>A",
            "rsIds": [],
            "transcriptConsequences": [
                {
                    "variantFunctionalConsequenceIds": ["SO_0001632"],
                    "isEnsemblCanonical": True,
                    "targetId": "ENSG000003",
                    "transcriptId": "ENST000003",
                    "impact": "MODIFIER",
                    "biotype": "protein_coding",
                    "distanceFromTss": 5000,
                }
            ],
        },
        {
            "variantId": "1_1100_T_C",
            "chromosome": "1",
            "position": 1100,
            "referenceAllele": "T",
            "alternateAllele": "C",
            "hgvsId": "1:g.1100T>C",
            "rsIds": [],
            "transcriptConsequences": [
                {
                    "variantFunctionalConsequenceIds": ["SO_0001630", "SO_0002169"],
                    "isEnsemblCanonical": True,
                    "targetId": "ENSG000004",
                    "transcriptId": "ENST000004",
                    "impact": "LOW",
                    "biotype": "protein_coding",
                    "consequenceScore": 0.2,
                }
            ],
        },
    ])


def _gene_intervals() -> pd.DataFrame:
    return pd.DataFrame([
        {"id": "ENSG000001", "chromosome": "1", "start": 50, "end": 150, "strand": 1},
        # VEP targetId for 1_500_C_T is ENSG000002, but the variant position is
        # outside this independent gene interval, so mutation_in_gene must reject it.
        {"id": "ENSG000002", "chromosome": "1", "start": 600, "end": 700, "strand": -1},
        {"id": "ENSG000003", "chromosome": "1", "start": 850, "end": 950, "strand": 1},
        {"id": "ENSG000004", "chromosome": "1", "start": 1050, "end": 1150, "strand": 1},
    ])


def test_policy_filters_direct_gene_and_transcript_edges() -> None:
    enhancers = pd.DataFrame(columns=["id", "chromosome", "start", "end"])
    edges, evidence, nodes, summary = build_edges_from_variants(_variant_table(), set(), enhancers, _gene_intervals())

    assert summary["exploded_transcript_consequence_rows"] == 4
    assert summary["rows_after_allowed_consequence_filter"] == 2
    assert summary["rows_after_canonical_transcript_filter"] == 1
    assert summary["excluded_upstream_downstream_intergenic_or_regulatory_rows"] == 1
    assert summary["rejected_non_allowlisted_consequence_rows"] == 2
    assert summary["gene_coordinate_containment_passes"] == 1
    assert summary["gene_coordinate_containment_rejects"] == 1
    assert summary["edge_rows"]["mutation_in_gene"] == 1
    assert summary["edge_rows"]["mutation_affects_transcript"] == 1
    assert summary["edge_rows"]["mutation_overlaps_enhancer"] == 0
    assert set(edges["mutation_in_gene"]["y_id"]) == {"ENSG000001"}
    assert set(edges["mutation_affects_transcript"]["y_id"]) == {"ENST000001"}
    assert "ENSG000002" not in set(edges["mutation_in_gene"]["y_id"])
    assert "ENSG000003" not in set(edges["mutation_in_gene"]["y_id"])
    assert "ENSG000004" not in set(edges["mutation_in_gene"]["y_id"])
    assert len(nodes) == 4
    text_span = evidence["mutation_affects_transcript"].iloc[0]["text_span"]
    assert "SO_0001627" in text_span
    assert "SO_0002169" not in "\n".join(evidence["mutation_affects_transcript"]["text_span"].astype(str))
    assert "1:g.100A>G" in text_span
    gene_text_span = evidence["mutation_in_gene"].iloc[0]["text_span"]
    assert "target.genomicLocation" in gene_text_span
    assert '"start": 50' in gene_text_span


def test_endpoint_filters_reject_noncanonical_ids() -> None:
    enhancers = pd.DataFrame(columns=["id", "chromosome", "start", "end"])
    edges, _evidence, _nodes, summary = build_edges_from_variants(
        _variant_table(),
        set(),
        enhancers,
        _gene_intervals(),
        canonical_mutations={"1_100_A_G", "1_500_C_T"},
        canonical_genes={"ENSG000001"},
        canonical_transcripts={"ENST000001"},
    )

    assert summary["canonical_mutation_matches"] == 2
    assert summary["gene_endpoint_rejects"] == 1
    assert summary["gene_coordinate_containment_passes"] == 1
    assert summary["transcript_endpoint_rejects"] == 0
    assert set(edges["mutation_in_gene"]["y_id"]) == {"ENSG000001"}
    assert set(edges["mutation_affects_transcript"]["y_id"]) == {"ENST000001"}


def test_enhancer_overlap_requires_downstream_association_gate() -> None:
    enhancers = pd.DataFrame([
        {"id": "enh_supported", "chromosome": "1", "start": 90, "end": 110},
        {"id": "enh_ungated", "chromosome": "1", "start": 490, "end": 510},
    ])

    edges, evidence, _nodes, summary = build_edges_from_variants(
        _variant_table(), {"1_100_A_G"}, enhancers, _gene_intervals()
    )

    assert summary["edge_rows"]["mutation_overlaps_enhancer"] == 1
    overlap = edges["mutation_overlaps_enhancer"].iloc[0]
    assert overlap["x_id"] == "1_100_A_G"
    assert overlap["y_id"] == "enh_supported"
    assert "downstream_association_gate" in evidence["mutation_overlaps_enhancer"].iloc[0]["text_span"]
