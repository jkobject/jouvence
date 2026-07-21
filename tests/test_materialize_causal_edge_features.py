from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from manage_db import materialize_causal_edge_features as causal
from manage_db.materialize_causal_edge_features import (
    CONTRACT_VERSION,
    materialize_relation,
    stage_relations,
    validate_manifest,
    validate_staged_relation,
)


def _edges(relation: str, rows: list[tuple[str, str]]) -> pd.DataFrame:
    endpoint_types = {
        "molecule_targets_protein": ("molecule", "protein"),
        "disease_associated_protein": ("protein", "disease"),
        "mutation_associated_disease": ("mutation", "disease"),
        "mutation_affects_molecule_response": ("mutation", "molecule"),
    }
    x_type, y_type = endpoint_types[relation]
    return pd.DataFrame(
        [
            {
                "x_id": x_id,
                "x_type": x_type,
                "y_id": y_id,
                "y_type": y_type,
                "relation": relation,
                "display_relation": "associated",
                "source": "fixture",
                "credibility": 3,
            }
            for x_id, y_id in rows
        ]
    )


def _evidence(relation: str, rows: list[dict[str, object]]) -> pd.DataFrame:
    endpoint_types = {
        "molecule_targets_protein": ("molecule", "protein"),
        "disease_associated_protein": ("protein", "disease"),
        "mutation_associated_disease": ("mutation", "disease"),
        "mutation_affects_molecule_response": ("mutation", "molecule"),
    }
    default_x_type, default_y_type = endpoint_types[relation]
    records = []
    for row in rows:
        record = {
            "edge_key": f"{relation}|{row['x_id']}|{row['y_id']}",
            "relation": relation,
            "x_id": row["x_id"],
            "x_type": row.get("x_type", default_x_type),
            "y_id": row["y_id"],
            "y_type": row.get("y_type", default_y_type),
            "source": "fixture",
            "source_dataset": row.get("source_dataset", "fixture"),
            "source_record_id": row.get("source_record_id", "record-1"),
            "predicate": row.get("predicate", ""),
            "direction": row.get("direction", ""),
            "text_span": row.get("text_span", ""),
        }
        record.update(row)
        records.append(record)
    return pd.DataFrame(records)


def test_action_features_are_evidence_derived_and_conflicts_fail_closed() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    edges["action_type"] = "AGONIST"  # Direct edge fields are never authoritative.
    evidence = _evidence(
        relation,
        [
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "a", "predicate": "INHIBITOR"},
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "b", "predicate": "AGONIST"},
        ],
    )

    enriched_edges, enriched_evidence, report = materialize_relation(edges, evidence, relation)

    assert json.loads(enriched_edges.loc[0, "action_types"]) == ["agonist", "inhibitor"]
    assert json.loads(enriched_edges.loc[0, "action_direction"]) == ["negative", "positive"]
    assert enriched_edges.loc[0, "action_status"] == "conflicting"
    assert enriched_edges.loc[0, "evidence_count"] == 2
    assert set(enriched_evidence["normalized_action_type"]) == {"agonist", "inhibitor"}
    assert report["status_counts"]["action_status"] == {"conflicting": 1}


def test_missing_action_stays_unknown_and_duplicate_records_do_not_inflate_support() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1"), ("CHEMBL2", "ENSP2")])
    evidence = _evidence(
        relation,
        [
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "same", "predicate": "INHIBITOR"},
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "same", "predicate": "INHIBITOR"},
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "unknown", "predicate": "OTHER"},
            {"x_id": "CHEMBL2", "y_id": "ENSP2", "source_record_id": "missing", "predicate": "OTHER"},
        ],
    )

    enriched_edges, _, report = materialize_relation(edges, evidence, relation)
    first = enriched_edges.set_index("x_id").loc["CHEMBL1"]
    second = enriched_edges.set_index("x_id").loc["CHEMBL2"]
    assert first["evidence_count"] == 1
    assert first["action_status"] == "single"
    assert second["action_types"] == "[]"
    assert second["action_direction"] == "[]"
    assert second["action_status"] == "unknown"
    assert report["source_summary"]["fixture"] == {"edge_rows": 2, "evidence_rows": 4}
    assert report["fields_still_unavailable"] == []


def test_disease_features_do_not_infer_gof_or_lof_from_variant_category_or_text() -> None:
    relation = "disease_associated_protein"
    edges = _edges(relation, [("ENSP1", "MONDO:1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "ENSP1",
                "x_type": "protein",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "source_dataset": "humsavar_missense_variants",
                "source_record_id": "VAR_1",
                "predicate": "UniProt humsavar disease variant",
                "variant_category": "LP/P",
                "text_span": "stop gained missense variant",
            }
        ],
    )

    enriched_edges, enriched_evidence, report = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "causal_mechanisms"] == "[]"
    assert enriched_edges.loc[0, "mechanism_status"] == "unknown"
    assert enriched_edges.loc[0, "effect_directions"] == "[]"
    assert enriched_edges.loc[0, "effect_direction_status"] == "unknown"
    assert enriched_evidence.loc[0, "normalized_clinical_significance"] == "likely_pathogenic_or_pathogenic"
    assert enriched_evidence.loc[0, "normalized_causal_mechanism"] == ""
    assert set(report["fields_still_unavailable"]) == {
        "normalized_causal_mechanism",
        "normalized_effect_direction",
        "normalized_inheritance_mode",
    }


def test_source_backed_disease_support_counts_without_signed_mechanism() -> None:
    relation = "disease_associated_protein"
    edges = _edges(relation, [("ENSP1", "MONDO:1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "ENSP1",
                "y_id": "MONDO:1",
                "source_dataset": "reviewed_human_disease_comments",
                "source_record_id": "comment-1",
                "predicate": "UniProt disease comment",
            }
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "mechanism_status"] == "unknown"
    assert enriched_edges.loc[0, "causal_support_level"] == "source_backed_disease_assertion"
    assert enriched_edges.loc[0, "evidence_count"] == 1


def test_response_category_separation_and_missing_disease_context_fail_closed() -> None:
    relation = "mutation_affects_molecule_response"
    edges = _edges(relation, [("var1", "CHEMBL1"), ("var2", "CHEMBL2")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "var1",
                "x_type": "mutation",
                "y_id": "CHEMBL1",
                "y_type": "molecule",
                "source_record_id": "tox",
                "predicate": "toxicity",
                "direction": "increased toxicity",
                "disease_id": "MONDO:1",
            },
            {
                "x_id": "var2",
                "x_type": "mutation",
                "y_id": "CHEMBL2",
                "y_type": "molecule",
                "source_record_id": "pk",
                "predicate": "metabolism/pk",
                "direction": "decreased exposure",
                "disease_id": "",
            },
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)
    by_id = enriched_edges.set_index("x_id")
    assert json.loads(by_id.loc["var1", "response_categories"]) == ["toxicity"]
    assert json.loads(by_id.loc["var2", "response_categories"]) == ["metabolism_pk"]
    assert by_id.loc["var1", "disease_context_status"] == "single"
    assert by_id.loc["var2", "disease_context_status"] == "unknown"
    assert "efficacy" not in enriched_edges["response_categories"].str.cat(sep="|")


def test_category_only_response_is_one_usable_assertion() -> None:
    relation = "mutation_affects_molecule_response"
    edges = _edges(relation, [("var1", "CHEMBL1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "var1",
                "x_type": "mutation",
                "y_id": "CHEMBL1",
                "y_type": "molecule",
                "source_record_id": "tox",
                "predicate": "toxicity",
            }
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "response_status"] == "single"


def test_distinct_disease_contexts_are_conflicting() -> None:
    relation = "mutation_affects_molecule_response"
    edges = _edges(relation, [("var1", "CHEMBL1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "var1",
                "y_id": "CHEMBL1",
                "source_record_id": "one",
                "predicate": "efficacy",
                "disease_id": "MONDO:1",
            },
            {
                "x_id": "var1",
                "y_id": "CHEMBL1",
                "source_record_id": "two",
                "predicate": "efficacy",
                "disease_id": "MONDO:2",
            },
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "disease_context_status"] == "conflicting"


def test_generated_assertion_ids_are_scoped_to_source_dataset() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source": "source-a",
                "source_dataset": "dataset-a",
                "source_record_id": "shared-id",
                "source_assertion_id": "shared-explicit-id",
                "predicate": "INHIBITOR",
            },
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source": "source-b",
                "source_dataset": "dataset-b",
                "source_record_id": "shared-id",
                "source_assertion_id": "shared-explicit-id",
                "predicate": "INHIBITOR",
            },
        ],
    )

    enriched_edges, enriched_evidence, _ = materialize_relation(edges, evidence, relation)

    assert enriched_evidence["source_assertion_id"].tolist() == ["shared-explicit-id", "shared-explicit-id"]
    assert enriched_evidence["materialization_assertion_id"].nunique() == 2
    assert enriched_edges.loc[0, "evidence_count"] == 2
    assert enriched_edges.loc[0, "action_status"] == "consensus"


def test_assertion_ids_are_scoped_to_relation_endpoints() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1"), ("CHEMBL2", "ENSP2")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "shared",
                "source_assertion_id": "shared",
                "predicate": "INHIBITOR",
            },
            {
                "x_id": "CHEMBL2",
                "y_id": "ENSP2",
                "source_record_id": "shared",
                "source_assertion_id": "shared",
                "predicate": "INHIBITOR",
            },
        ],
    )

    _, enriched_evidence, _ = materialize_relation(edges, evidence, relation)

    assert enriched_evidence["materialization_assertion_id"].nunique() == 2


def test_conflicting_duplicate_assertion_fails_closed_and_is_order_independent() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "same",
                "predicate": "INHIBITOR",
            },
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "same",
                "predicate": "AGONIST",
            },
        ],
    )

    forward, _, _ = materialize_relation(edges, evidence, relation)
    reverse, _, _ = materialize_relation(edges, evidence.iloc[::-1].reset_index(drop=True), relation)

    assert forward.loc[0, "evidence_count"] == 1
    assert forward.loc[0, "action_status"] == "conflicting"
    assert forward.loc[0, "action_types"] == reverse.loc[0, "action_types"]
    assert forward.loc[0, "action_status"] == reverse.loc[0, "action_status"]


def test_duplicate_assertion_with_known_and_unusable_semantics_fails_closed() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "same",
                "predicate": "INHIBITOR",
            },
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "same",
                "predicate": "UNREVIEWED ACTION",
            },
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "evidence_count"] == 1
    assert enriched_edges.loc[0, "action_status"] == "conflicting"


def test_unusable_assertions_do_not_inflate_evidence_count() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "known",
                "predicate": "INHIBITOR",
            },
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "unknown",
                "predicate": "UNREVIEWED ACTION",
            },
        ],
    )

    enriched_edges, _, _ = materialize_relation(edges, evidence, relation)

    assert enriched_edges.loc[0, "evidence_count"] == 1


def test_existing_edge_key_must_match_evidence_endpoints() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "one", "predicate": "INHIBITOR"}],
    )
    evidence.loc[0, "edge_key"] = f"{relation}|CHEMBL_WRONG|ENSP1"

    with pytest.raises(ValueError, match="edge_key does not match"):
        materialize_relation(edges, evidence, relation)


def test_rejects_already_materialized_contract_columns() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "predicate": "INHIBITOR"}],
    )
    evidence["causal_feature_contract_version"] = "older-contract"

    with pytest.raises(ValueError, match="already contains materialized columns"):
        materialize_relation(edges, evidence, relation)


def test_rejects_evidence_without_source_identity_columns() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "predicate": "INHIBITOR"}],
    ).drop(columns=["source_dataset"])

    with pytest.raises(ValueError, match="source_dataset"):
        materialize_relation(edges, evidence, relation)


@pytest.mark.parametrize("column", ["source", "source_dataset", "source_record_id"])
def test_rejects_blank_evidence_source_identity(column: str) -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "predicate": "INHIBITOR"}],
    )
    evidence.loc[0, column] = ""

    with pytest.raises(ValueError, match=column):
        materialize_relation(edges, evidence, relation)


def test_rejects_wrong_endpoint_types() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "predicate": "INHIBITOR"}],
    )
    evidence.loc[0, "y_type"] = "gene"

    with pytest.raises(ValueError, match="endpoint types"):
        materialize_relation(edges, evidence, relation)


def test_validator_recomputes_each_evidence_edge_key_and_requires_feature_columns() -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1"), ("CHEMBL2", "ENSP2")])
    evidence = _evidence(
        relation,
        [
            {"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "one", "predicate": "INHIBITOR"},
            {"x_id": "CHEMBL2", "y_id": "ENSP2", "source_record_id": "two", "predicate": "AGONIST"},
        ],
    )
    staged_edges, staged_evidence, _ = materialize_relation(edges, evidence, relation)
    staged_evidence["edge_key"] = staged_evidence["edge_key"].iloc[::-1].to_numpy()
    staged_edges = staged_edges.drop(columns=["action_types"])

    errors = validate_staged_relation(staged_edges, staged_evidence, relation)

    assert any("edge_key does not match" in error for error in errors)
    assert any("missing feature columns" in error for error in errors)


def test_rowwise_fallback_and_normalization_preserve_raw_evidence() -> None:
    relation = "mutation_affects_molecule_response"
    edges = _edges(relation, [("var1", "CHEMBL1"), ("var2", "CHEMBL2")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "var1",
                "y_id": "CHEMBL1",
                "source_record_id": "one",
                "predicate": "toxicity",
                "response_category": "",
                "response_direction": "Increased Toxicity",
            },
            {
                "x_id": "var2",
                "y_id": "CHEMBL2",
                "source_record_id": "two",
                "predicate": "ignored",
                "response_category": "efficacy",
                "response_direction": "Sensitive",
            },
        ],
    )

    enriched_edges, enriched_evidence, _ = materialize_relation(edges, evidence, relation)

    assert enriched_evidence[evidence.columns].equals(evidence)
    assert enriched_evidence["normalized_response_category"].tolist() == ["toxicity", "efficacy"]
    assert enriched_evidence["normalized_response_direction"].tolist() == ["increased_toxicity", "sensitive"]
    assert json.loads(enriched_edges.loc[0, "response_categories"]) == ["toxicity"]


def test_mutation_disease_ambiguous_effect_is_not_signed() -> None:
    relation = "mutation_associated_disease"
    edges = _edges(relation, [("var1", "MONDO:1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "var1",
                "x_type": "mutation",
                "y_id": "MONDO:1",
                "y_type": "disease",
                "source_record_id": "gwas-1",
                "predicate": "genetic_association",
                "beta": 0.4,
                "effect_allele": "A",
                "disease_id": "",
            }
        ],
    )

    enriched_edges, enriched_evidence, _ = materialize_relation(edges, evidence, relation)
    assert enriched_edges.loc[0, "effect_directions"] == "[]"
    assert enriched_edges.loc[0, "association_status"] == "unknown"
    assert enriched_evidence.loc[0, "beta"] == 0.4
    assert enriched_evidence.loc[0, "effect_allele"] == "A"


def test_output_root_must_be_task_scoped_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [{"x_id": "CHEMBL1", "y_id": "ENSP1", "source_record_id": "one", "predicate": "INHIBITOR"}],
    )
    edge_path = tmp_path / "input_edges.parquet"
    evidence_path = tmp_path / "input_evidence.parquet"
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)

    with pytest.raises(ValueError, match="artifacts/staged"):
        stage_relations(
            inputs={relation: {"edges": edge_path, "evidence": evidence_path}},
            output_root=tmp_path / "unsafe-output",
            source_revision="fixture-sha",
            task_id="t_fixture",
        )

    monkeypatch.setattr(causal, "STAGING_ROOT", tmp_path / "staged")
    with pytest.raises(ValueError, match="t_fixture"):
        stage_relations(
            inputs={relation: {"edges": edge_path, "evidence": evidence_path}},
            output_root=causal.STAGING_ROOT / "t_other",
            source_revision="fixture-sha",
            task_id="t_fixture",
        )


def test_staging_preserves_edge_identity_and_source_evidence_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relation = "molecule_targets_protein"
    edges = _edges(relation, [("CHEMBL1", "ENSP1")])
    evidence = _evidence(
        relation,
        [
            {
                "x_id": "CHEMBL1",
                "y_id": "ENSP1",
                "source_record_id": "record-1",
                "predicate": "INHIBITOR",
                "raw_context": "preserve me",
            }
        ],
    )
    edge_path = tmp_path / "input_edges.parquet"
    evidence_path = tmp_path / "input_evidence.parquet"
    edges.to_parquet(edge_path, index=False)
    evidence.to_parquet(evidence_path, index=False)

    monkeypatch.setattr(causal, "STAGING_ROOT", tmp_path)
    output = tmp_path / "t_fixture"
    manifest = stage_relations(
        inputs={relation: {"edges": edge_path, "evidence": evidence_path}},
        output_root=output,
        source_revision="fixture-sha",
        task_id="t_fixture",
    )

    staged_edges = pd.read_parquet(output / "edges" / f"{relation}.parquet")
    staged_evidence = pd.read_parquet(output / "evidence" / f"{relation}.parquet")
    assert staged_edges[["x_id", "y_id", "relation"]].equals(edges[["x_id", "y_id", "relation"]])
    assert staged_evidence.loc[0, "raw_context"] == "preserve me"
    assert manifest["contract_version"] == CONTRACT_VERSION
    assert manifest["relations"][relation]["validation"]["edge_identity_unchanged"] is True
    assert validate_staged_relation(staged_edges, staged_evidence, relation) == []
    manifest_path = output / "reports" / "materialization_manifest.json"
    assert validate_manifest(
        manifest_path,
        expected_task_id="t_fixture",
        expected_relations={relation},
    ) == []
    assert any(
        "expected task" in error
        for error in validate_manifest(
            manifest_path,
            expected_task_id="t_other",
            expected_relations={relation},
        )
    )
    assert any(
        "missing expected relations" in error
        for error in validate_manifest(
            manifest_path,
            expected_task_id="t_fixture",
            expected_relations={relation, "disease_associated_protein"},
        )
    )

    staged_edges.loc[0, "relation"] = "molecule_inhibits_protein"
    staged_edges.to_parquet(output / "edges" / f"{relation}.parquet", index=False)
    errors = validate_manifest(
        manifest_path,
        expected_task_id="t_fixture",
        expected_relations={relation},
    )
    assert any("sha256 mismatch" in error for error in errors)
    assert any("relation drift" in error for error in errors)

    staged_edges.loc[0, "relation"] = relation
    staged_edges.loc[0, "display_relation"] = "corrupted"
    staged_edges.loc[0, "action_types"] = "[]"
    staged_edges.to_parquet(output / "edges" / f"{relation}.parquet", index=False)
    staged_evidence.loc[0, "raw_context"] = "corrupted"
    staged_evidence.loc[0, "normalized_action_type"] = ""
    evidence_output = output / "evidence" / f"{relation}.parquet"
    staged_evidence.to_parquet(evidence_output, index=False)
    receipt = json.loads(manifest_path.read_text())
    edge_output = output / "edges" / f"{relation}.parquet"
    receipt["relations"][relation]["outputs"]["edge_sha256"] = hashlib.sha256(
        edge_output.read_bytes()
    ).hexdigest()
    receipt["relations"][relation]["outputs"]["evidence_sha256"] = hashlib.sha256(
        evidence_output.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(receipt))
    errors = validate_manifest(
        manifest_path,
        expected_task_id="t_fixture",
        expected_relations={relation},
    )
    assert any("source edge values changed" in error for error in errors)
    assert any("source evidence values changed" in error for error in errors)
    assert any("materialized edge values changed" in error for error in errors)
    assert any("normalized evidence values changed" in error for error in errors)
