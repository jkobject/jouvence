from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _entry(accession: str, sequence: str = "MSSSSSSSSSSSSSS") -> dict:
    return {
        "primaryAccession": accession,
        "sequence": {"value": sequence},
        "comments": [
            {
                "commentType": "DISEASE",
                "disease": {"diseaseId": "MIM:123456", "diseaseAccession": "DI-00000", "diseaseDescription": "Generic protein disease comment"},
            }
        ],
        "features": [
            {
                "type": "Modified residue",
                "location": {"start": {"value": 3, "modifier": "EXACT"}, "end": {"value": 3, "modifier": "EXACT"}},
                "description": "Phosphoserine",
                "evidences": [
                    {"evidenceCode": "ECO:0007744", "source": "PubMed", "id": "12345"},
                    {"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "67890"},
                ],
            },
            {
                "type": "Glycosylation",
                "location": {"start": {"value": 5, "modifier": "EXACT"}, "end": {"value": 5, "modifier": "EXACT"}},
                "description": "N-linked (GlcNAc...) asparagine; phenotype HP:0000001 candidate text",
                "featureId": "CAR_0001",
                "evidences": [{"evidenceCode": "ECO:0000269"}],
            },
            {
                "type": "Natural variant",
                "location": {"start": {"value": 6, "modifier": "EXACT"}, "end": {"value": 6, "modifier": "EXACT"}},
                "description": "not a PTM feature",
            },
        ],
    }


def test_build_rows_preserves_site_evidence_and_disease_gate() -> None:
    from manage_db.build_uniprot_ptm_sites import build_ptm_rows_from_uniprot_results

    protein_nodes = pd.DataFrame(
        [
            {"id": "ENSP00000000001", "uniprot_id": "PTEST1"},
            {"id": "ENSP00000000002", "uniprot_id": "POTHER|PALIAS"},
        ]
    )
    sites, edges, evidence, candidates, counts = build_ptm_rows_from_uniprot_results(
        [_entry("PTEST1"), _entry("PNOMAP")], protein_nodes, release="2099_01", created_at="2099-01-01T00:00:00+00:00"
    )

    assert counts["entries_seen"] == 2
    assert counts["entries_with_ptm_features"] == 2
    assert counts["ptm_features_seen"] == 4
    assert counts["ptm_features_mapped_to_protein"] == 2
    assert counts["ptm_features_missing_protein_mapping"] == 2
    assert counts["entries_with_generic_disease_comments"] == 2
    assert counts["site_level_disease_candidate_rows"] == 1

    assert set(sites["feature_type"]) == {"Modified residue", "Glycosylation"}
    phospho = sites.loc[sites["modification_type"].eq("Phosphoserine")].iloc[0]
    assert phospho["id"].startswith("PTMSITE:PTEST1:modified_residue:3")
    assert phospho["protein_id"] == "ENSP00000000001"
    assert phospho["residue"] == "S"
    assert phospho["psi_mod_id"] == "MOD:00696"
    assert phospho["evidence_codes"] == "ECO:0000269|ECO:0007744"
    assert phospho["pmids"] == "PMID:12345|PMID:67890"
    assert phospho["sequence_context"] == "MSSSSSSSSS"

    assert len(edges) == 2
    assert set(edges["y_type"]) == {"ptm_site"}
    assert set(edges["relation"]) == {"protein_has_ptm_site"}
    assert len(evidence) == 4  # 2 database rows + 2 PMID rows for the phosphorylated site
    assert set(evidence["x_type"]) == {"protein"}
    assert set(evidence["y_type"]) == {"ptm_site"}

    # Only feature-local disease/phenotype-looking text becomes a manual-review
    # candidate. Generic protein DISEASE comments are counted but not joined to PTMs.
    assert candidates.iloc[0]["disease_or_phenotype_id"] == "HP:0000001"
    assert "candidate_only" in candidates.iloc[0]["decision"]


def test_cli_fixture_writes_staging_outputs(tmp_path: Path) -> None:
    from manage_db.build_uniprot_ptm_sites import build_uniprot_ptm_sites

    protein_nodes = tmp_path / "protein.parquet"
    pd.DataFrame([{"id": "ENSP00000000001", "uniprot_id": "PTEST1"}]).to_parquet(protein_nodes, index=False)
    entries_json = tmp_path / "entries.json"
    entries_json.write_text(json.dumps({"release": "2099_01", "entries": [_entry("PTEST1")]}))

    output_root = tmp_path / "staged"
    summary = build_uniprot_ptm_sites(
        output_root=str(output_root), protein_nodes_path=str(protein_nodes), entries_json_path=str(entries_json)
    )

    assert summary["staging_only"] is True
    assert summary["ptm_site_nodes"] == 2
    assert summary["protein_has_ptm_site_edges"] == 2
    assert summary["validation"]["disease_phenotype_edges_written"] == 0
    assert (output_root / "nodes" / "ptm_site.parquet").exists()
    assert (output_root / "edges" / "protein_has_ptm_site.parquet").exists()
    assert (output_root / "evidence" / "protein_has_ptm_site.parquet").exists()
    assert (output_root / "diagnostics" / "ptm_site_disease_link_candidates.parquet").exists()
    assert (output_root / "reports" / "uniprot_ptm_sites_summary.json").exists()
