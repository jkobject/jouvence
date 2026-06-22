from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_parse_mirbase_dat_emits_precursor_and_mature_nodes(tmp_path: Path) -> None:
    from manage_db.prepare_real_mirna_sources import parse_mirbase_dat

    dat = tmp_path / "miRNA.dat"
    dat.write_text(
        """
ID   hsa-let-7a-1      standard; RNA; HSA; 80 BP.
XX
AC   MI0000060;
XX
DE   Homo sapiens let-7a-1 stem-loop
XX
DR   HGNC; 31476; MIRLET7A1.
DR   ENTREZGENE; 406881; MIRLET7A1.
XX
FT   miRNA           6..27
FT                   /accession="MIMAT0000062"
FT                   /product="hsa-let-7a-5p"
FT                   /evidence=experimental
FT   miRNA           57..77
FT                   /accession="MIMAT0004481"
FT                   /product="hsa-let-7a-3p"
XX
SQ   Sequence 80 BP; 21 A; 15 C; 19 G; 0 T; 25 other;
//
ID   mmu-let-7a-1      standard; RNA; MMU; 80 BP.
XX
AC   MI0000550;
XX
FT   miRNA           1..22
FT                   /accession="MIMAT0000521"
FT                   /product="mmu-let-7a-5p"
//
""".strip()
    )

    catalog, mature = parse_mirbase_dat(dat, source_release="test")

    assert set(catalog["id"]) == {"MI0000060", "MIMAT0000062", "MIMAT0004481"}
    assert set(catalog["mirna_product_type"]) == {"precursor_hairpin", "mature"}
    mature_5p = catalog[catalog["id"].eq("MIMAT0000062")].iloc[0]
    assert mature_5p["mirbase_precursor_accession"] == "MI0000060"
    assert mature_5p["arm"] == "5p"
    assert len(mature) == 2


def test_biomart_mapping_keeps_direct_mirbase_xrefs() -> None:
    from manage_db.prepare_real_mirna_sources import build_biomart_mirbase_mapping

    biomart = pd.DataFrame(
        [
            {
                "Gene stable ID": "ENSG1",
                "Transcript stable ID": "ENST1",
                "Gene name": "MIRTEST1",
                "Transcript name": "MIRTEST1-201",
                "miRBase ID": "hsa-mir-test-1",
                "miRBase accession": "MI0000001",
                "miRBase transcript name ID": "hsa-mir-test-1.1-201",
                "RNAcentral ID": "URS000001",
            },
            {
                "Gene stable ID": "ENSG2",
                "Transcript stable ID": "ENST2",
                "miRBase ID": "",
                "miRBase accession": "",
            },
        ]
    )

    mapping = build_biomart_mirbase_mapping(biomart, source_release="test")

    assert mapping.to_dict("records")[0] | {"notes_json": mapping.iloc[0]["notes_json"]} == {
        "ensembl_transcript_id": "ENST1",
        "ensembl_gene_id": "ENSG1",
        "mirbase_accession": "MI0000001",
        "mirbase_name": "hsa-mir-test-1",
        "mirbase_entity_type": "precursor_hairpin",
        "rnacentral_id": "URS000001",
        "mapping_method": "Ensembl_BioMart_xref",
        "mapping_confidence": "exact",
        "source_dataset": "Ensembl BioMart miRBase xref",
        "source_release": "test",
        "source_record_id": "ENST1|MI0000001",
        "species_id": "NCBITaxon:9606",
        "notes_json": mapping.iloc[0]["notes_json"],
        "is_same_entity_as_transcript": True,
    }
    assert len(mapping) == 1


def test_normalise_mirtarbase_accepts_only_resolved_human_gene_rows(tmp_path: Path) -> None:
    from manage_db.prepare_real_mirna_sources import normalise_mirtarbase

    xlsx = tmp_path / "mirtarbase.xlsx"
    pd.DataFrame(
        [
            {
                "miRTarBase ID": "MIRT1",
                "miRNA": "hsa-miR-test-5p",
                "Species (miRNA)": "Homo sapiens",
                "Target Gene": "GENE1",
                "Target Gene (Entrez ID)": "101",
                "Species (Target Gene)": "Homo sapiens",
                "Experiments": "Reporter assay//Western blot",
                "Support Type": "Functional MTI",
                "References (PMID)": "PMID:1",
            },
            {
                "miRTarBase ID": "MIRT2",
                "miRNA": "hsa-miR-missing-5p",
                "Species (miRNA)": "Homo sapiens",
                "Target Gene": "GENE1",
                "Target Gene (Entrez ID)": "101",
                "Species (Target Gene)": "Homo sapiens",
            },
            {
                "miRTarBase ID": "MIRT3",
                "miRNA": "hsa-miR-test-5p",
                "Species (miRNA)": "Mus musculus",
                "Target Gene": "GENE1",
                "Target Gene (Entrez ID)": "101",
                "Species (Target Gene)": "Homo sapiens",
            },
        ]
    ).to_excel(xlsx, index=False)
    catalog = pd.DataFrame(
        [
            {
                "id": "MIMAT1",
                "name": "hsa-miR-test-5p",
                "mirna_product_type": "mature",
                "mirbase_mature_accession": "MIMAT1",
                "mirbase_mature_name": "hsa-miR-test-5p",
                "mirbase_precursor_accession": "MI1",
            }
        ]
    )
    genes = pd.DataFrame(
        [
            {
                "Gene stable ID": "ENSG1",
                "Gene name": "GENE1",
                "NCBI gene (formerly Entrezgene) ID": "101",
            }
        ]
    )

    accepted, rejected = normalise_mirtarbase(xlsx, catalog, genes, source_release="test")

    assert len(accepted) == 1
    row = accepted.iloc[0]
    assert row["mirna_id"] == "MIMAT1"
    assert row["target_gene_id"] == "ENSG1"
    assert row["target_endpoint_level"] == "gene"
    assert row["target_mapping_method"] == "BioMart_entrez_gene_xref"
    assert row["assay"] == "Reporter assay//Western blot"
    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reasons"] == "unresolved_or_nonunique_mirbase_mature_name"
