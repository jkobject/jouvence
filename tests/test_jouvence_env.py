from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from manage_db.jouvence_env import get_jouvence_env


ROOT = Path(__file__).resolve().parents[1]


def test_jouvence_env_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOUVENCE_NOTEBOOK_SAMPLE_MODE", raising=False)
    monkeypatch.delenv("TXGNN_NOTEBOOK_SAMPLE_MODE", raising=False)

    assert get_jouvence_env("JOUVENCE_NOTEBOOK_SAMPLE_MODE", "1") == "1"


def test_jouvence_env_accepts_deprecated_txgnn_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOUVENCE_NOTEBOOK_SAMPLE_MODE", raising=False)
    monkeypatch.setenv("TXGNN_NOTEBOOK_SAMPLE_MODE", "0")

    with pytest.deprecated_call(match="TXGNN_NOTEBOOK_SAMPLE_MODE is deprecated"):
        assert get_jouvence_env("JOUVENCE_NOTEBOOK_SAMPLE_MODE", "1") == "0"


def test_jouvence_env_wins_over_legacy_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOUVENCE_NOTEBOOK_SAMPLE_MODE", "jouvence")
    monkeypatch.setenv("TXGNN_NOTEBOOK_SAMPLE_MODE", "legacy")

    assert get_jouvence_env("JOUVENCE_NOTEBOOK_SAMPLE_MODE") == "jouvence"


def test_jouvence_env_rejects_unscoped_name() -> None:
    with pytest.raises(ValueError, match="must start with 'JOUVENCE_'"):
        get_jouvence_env("NOTEBOOK_SAMPLE_MODE")


ACTIVE_NOTEBOOK_ENV_NAMES = {
    "3_access_and_cache_sources.ipynb": {
        "DATA_ROOT",
        "KG_ROOT",
        "LOCAL_CACHE_ROOT",
        "NOTEBOOK_ALLOW_NETWORK",
        "NOTEBOOK_ALLOW_WRITES",
        "NOTEBOOK_SAMPLE_MODE",
        "OT_ROOT",
        "VERIFIED_KG_ROOT",
    },
    "4_download_opentargets_and_source_snapshots.ipynb": {
        "DATA_ROOT",
        "KG_ROOT",
        "LOCAL_CACHE_ROOT",
        "NOTEBOOK_ALLOW_NETWORK",
        "NOTEBOOK_ALLOW_WRITES",
        "NOTEBOOK_MANIFEST_PATH",
        "NOTEBOOK_SAMPLE_MODE",
        "OT_DATASETS",
        "OT_DOWNLOAD_WORKERS",
        "OT_ROOT",
        "VERIFIED_KG_ROOT",
    },
    "5_create_core_nodes.ipynb": {
        "DATA_ROOT",
        "KG_ROOT",
        "LOCAL_CACHE_ROOT",
        "NOTEBOOK_ALLOW_NETWORK",
        "NOTEBOOK_ALLOW_WRITES",
        "NOTEBOOK_SAMPLE_MODE",
        "OT_ROOT",
        "VERIFIED_KG_ROOT",
    },
    "6_build_core_edges_and_evidence.ipynb": {
        "DATA_DIR",
        "KG_ROOT",
        "NOTEBOOK_FULL_VALIDATION",
        "NOTEBOOK_RUN_BUILD",
        "NOTEBOOK_SAMPLE_MODE",
    },
    "7_opentargets_edges_and_evidence.ipynb": {
        "DATA_DIR",
        "DOWNLOAD_WORKERS",
        "KG_ROOT",
        "LOCAL_SAMPLE_KG_ROOT",
        "NOTEBOOK_DOWNLOAD",
        "NOTEBOOK_FULL_VALIDATION",
        "NOTEBOOK_RUN_BUILD",
        "NOTEBOOK_SAMPLE_MODE",
        "VERIFIED_KG_ROOT",
    },
    "8_block1_relation_splitting_policy.ipynb": {
        "BLOCK1_STAGING_ROOT",
        "DATA_DIR",
        "KG_ROOT",
        "NOTEBOOK_FULL_VALIDATION",
        "NOTEBOOK_RUN_BLOCK1_SPLIT",
        "NOTEBOOK_RUN_BUILD",
        "NOTEBOOK_SAMPLE_MODE",
    },
    "11_lamin_kg_schema_explorer.ipynb": {
        "KG_ROOT",
        "LAMIN_INTROSPECT",
        "NOTEBOOK_AUDIT_RELATIONS",
        "NOTEBOOK_EVIDENCE_AUDIT",
        "SCHEMA_FULL_SCAN",
    },
}


def test_active_notebooks_prefer_jouvence_with_txgnn_aliases() -> None:
    for name, env_names in ACTIVE_NOTEBOOK_ENV_NAMES.items():
        notebook = json.loads((ROOT / "notebooks" / name).read_text())
        text = "\n".join(
            "".join(cell.get("source", ""))
            for cell in notebook["cells"]
        )
        for env_name in env_names:
            primary = f"JOUVENCE_{env_name}"
            legacy = f"TXGNN_{env_name}"
            assert primary in text, f"{name} must expose {primary}"
            assert legacy in text, f"{name} must retain the {legacy} alias"

        for line in text.splitlines():
            for legacy in re.findall(r"TXGNN_[A-Z0-9_]+", line):
                primary = legacy.replace("TXGNN_", "JOUVENCE_", 1)
                assert primary in line, (
                    f"{name} has a standalone legacy setting: {line.strip()}"
                )
                assert line.index(primary) < line.index(legacy), (
                    f"{name} must recommend/read {primary} before {legacy}: "
                    f"{line.strip()}"
                )


def test_project_metadata_uses_jouvence_and_records_upstream() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert metadata["name"] == "Jouvence"
    assert metadata["urls"]["Repository"] == "https://github.com/jkobject/jouvence-graph"
    assert metadata["urls"]["Upstream"] == "https://github.com/mims-harvard/TxGNN"
