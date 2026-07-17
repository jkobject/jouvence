from pathlib import Path


RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "pyg_export_runbook.md"


def _section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    end = text.index(next_heading, start + len(heading))
    return text[start:end]


def test_production_sidecar_gate_does_not_require_full_heterodata_pickle() -> None:
    text = RUNBOOK.read_text()
    workflow = _section(
        text,
        "## GCP / bucket-local production-scale export workflow",
        "## Metadata adjacency / provenance opt-in behavior",
    )
    remaining = _section(
        text,
        "## Remaining steps to reach production/full-KG",
        "## Pilot export produced",
    )

    required_sidecar_terms = [
        "sidecar_artifact.metadata.json",
        "edge_row_map.parquet",
        "reverse-edge sidecars",
        "sidecar fallback",
        "--artifact-mode sidecar",
    ]
    for term in required_sidecar_terms:
        assert term in workflow

    forbidden_required_pickle_phrases = [
        "`heterodata/full_graph.pt` exists and loads",
        "against the produced real HeteroData",
        "validation reports, and `heterodata/full_graph.pt`",
    ]
    for phrase in forbidden_required_pickle_phrases:
        assert phrase not in workflow
        assert phrase not in remaining

    assert "Do not require `heterodata/full_graph.pt`" in remaining
    assert "bounded pilots or explicit\n   `--artifact-mode heterodata|both`" in remaining
    assert "via its sidecar fallback when `heterodata/full_graph.pt` is absent" in workflow


def test_runbook_documents_manifest_embedding_and_missing_feature_policy() -> None:
    text = RUNBOOK.read_text()
    intro = _section(
        text,
        "Manifest feature policy update (`t_95eca063`)",
        "Graph policy update (`t_c07b8b57`)",
    )
    for term in [
        "`node_embeddings`",
        "`edge_embeddings`",
        "`missing_feature_policy`",
        "artifacts/reports/t_e4f08d5a/kg_embedding_sidecar_audit.md",
        "artifacts/reports/t_e4f08d5a/raw_audit.json",
        "`source_of_truth`, `materialization_policy`, `node_types`, and `edge_types`",
        "`embedding_status` (`available` or `absent`)",
        "`available_feature_values[]`",
        "`intentionally_deferred[]`",
        "available embedding sidecars",
        "absent embeddings",
        "intentionally deferred production modalities",
        "embedding.node_id == node_maps.id",
        "embedding.edge_key == edge_row_map.edge_key",
        "sidecar_node_id_mapping",
        "sidecar_edge_id_mapping",
        "model-side learned `torch.nn.Embedding` rows",
        "`gene` with available text\n  embeddings",
        "`disease` with no visible embedding\n  sidecar",
        "`molecule` with available `molecule_fingerprint` sidecar values",
        "`protein`/`transcript` sequence rows",
        "`disease_associated_gene` or\n  `molecule_targets_gene` with edge embeddings",
        "`gene__rev_molecule_targets_gene__molecule` preserving forward-edge mapping\n  through `forward_edge_pos`",
        "must\nnot require materializing a full no-cap `HeteroData` pickle or full 100M-edge\ntensors",
        "How to read these manifest fields:",
        "Empty lists mean no\n  manifest-visible source embedding exists",
        "Rows in the node map without a joined sidecar row\n  use the model-side learned fallback",
        "Reverse-edge stores reuse the forward row via `forward_edge_pos`; do not look\n  for a separately minted reverse edge embedding key",
        "`intentionally_deferred[]`\n  means the field/modality is known and deliberately not represented yet",
        "whether each usable sidecar/field is categorical, numeric, text/raw,\n  sequence/raw, sparse-vector, or mixed/raw",
        "metadata derived from the accepted audit output plus current\n  Parquet footer/schema scans",
        "Bounded fixture-style manifest excerpt",
        '"embedding_model": "unit-model"',
        '"embedding_model": "unit-encoder"',
        '"feature_table": "gene_textual_summary"',
        '"field": "chemical_encoder_embedding"',
        '"field": "credibility", "status": "available", "value_kind": "numeric"',
        '"field": "source", "status": "available", "value_kind": "categorical"',
    ]:
        assert term in intro
