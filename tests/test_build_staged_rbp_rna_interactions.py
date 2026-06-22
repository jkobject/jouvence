from pathlib import Path

import pandas as pd

from manage_db import build_staged_rbp_rna_interactions as rbp


def test_encori_rbp_rows_are_staged_as_rejected_candidates_without_projection(tmp_path: Path, monkeypatch) -> None:
    sample = """#please cite:\nRBP\tgeneID\tgeneName\tgeneType\tclusterNum\ttotalClipExpNum\ttotalClipSiteNum\tclusterID\tchromosome\tnarrowStart\tnarrowEnd\tbroadStart\tbroadEnd\tstrand\tclipExpNum\tHepG2(shRNA)\tK562(shRNA)\tHepG2(CRISPR)\tK562(CRISPR)\tpancancerNum\tcellline/tissue\nELAVL1\tENSG00000141510\tTP53\tprotein_coding\t14\t31\t130\tELAVL1:CH1\tchr17\t7668414\t7668566\t7668414\t7668566\t-\t12\tNA\tNA\tNA\tNA\t22\tHeLa\n"""

    monkeypatch.setattr(rbp, "_fetch_text", lambda url: sample)
    candidates, rejected, audit = rbp.build_candidates(
        [rbp.SourceRequest(gene_type="mRNA", target="TP53", clip_exp_num=5, cell_type="HeLa")],
        max_rows_per_request=10,
    )

    assert len(candidates) == 1
    assert candidates.loc[0, "rna_id"] == "ENSG00000141510"
    assert candidates.loc[0, "rna_id_namespace"] == "Ensembl gene (not transcript endpoint)"
    assert candidates.loc[0, "protein_id"] == ""
    assert candidates.loc[0, "protein_id_namespace"] == "RBP gene symbol only; no approved gene-to-protein projection"
    assert rejected.loc[0, "reject_reason"] == "rna_endpoint_is_gene_or_coordinate_not_source_native_transcript"
    assert audit["sources"]["encori_starbase"]["rbp_api_endpoint"] == rbp.ENCORI_RBP_API

    manifest = rbp.write_outputs(candidates, rejected, audit, tmp_path / "stage", node_root="/missing/kg")
    assert manifest["validation"]["edge_rows"] == 0
    assert manifest["validation"]["rejected_rows"] == 1
    assert manifest["validation"]["policy_checks"]["gene_to_protein_projection_used"] is False
    assert Path(manifest["outputs"]["candidate_clip_evidence"]).exists()
    assert len(pd.read_parquet(manifest["outputs"]["rejected_rows"])) == 1


def test_lncrna_candidates_are_feature_only_until_relation_and_node_schema_exist() -> None:
    candidate: dict[str, object] = {
        "candidate_relation": "lncrna_interacts_protein",
        "rna_id_namespace": "Ensembl gene (not transcript endpoint)",
        "protein_id": "",
    }
    assert rbp.classify_candidate(candidate) == "relation_not_in_schema_and_lncRNA_node_type_missing"
