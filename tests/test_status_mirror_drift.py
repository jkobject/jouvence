from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import check_status_mirror_drift


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_status_mirrors_match_current_snapshot_and_superseded_cards_are_historical() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_status_mirror_drift.py",
            "--expected-date",
            "2026-07-22",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status mirror drift check: PASS (2026-07-22)" in result.stdout


def test_status_drift_guard_covers_every_current_phase_and_routing_surface() -> None:
    assert check_status_mirror_drift.MIRRORS == (
        Path("TODO.md"),
        Path("todo.d/01_lamindb.md"),
        Path("todo.d/02_pyg_gnn.md"),
        Path("todo.d/03_embeddings.md"),
        Path("todo.d/04_relations.md"),
        Path("todo.d/05_remap.md"),
        Path("todo.d/06_process.md"),
    )
    assert set(check_status_mirror_drift.ROUTING_REQUIREMENTS) == {
        Path("todo.d/README.md"),
        Path("docs/current_state_20260623.md"),
        Path("docs/guides/agent-context.md"),
        Path("docs/README.md"),
        Path("CLAUDE.md"),
    }
    assert set(check_status_mirror_drift.LIVE_STATUS_REQUIREMENTS) == {
        Path("TODO.md"),
        Path("todo.d/04_relations.md"),
        Path("docs/relation_coverage_current.md"),
        Path("docs/kg_schema_overview.md"),
        Path("docs/relation_backlog_prioritized.md"),
    }


def test_status_drift_guard_rejects_forbidden_remap_and_wave_b_directives() -> None:
    path = Path("docs/relation_backlog_prioritized.md")
    requirements = check_status_mirror_drift.LIVE_STATUS_REQUIREMENTS[path]
    live_text = (REPO_ROOT / path).read_text(encoding="utf-8")

    forbidden_directives = (
        "New ReMap CRM/peak/motif work should follow",
        "user-approved direction is a new bounded staged `tf_binds_enhancer`",
        "prepare promotion candidates for `pathway_contains_protein`, `molecule_targets_protein`, and `disease_associated_protein`",
    )
    for directive in forbidden_directives:
        errors = check_status_mirror_drift.check_text_requirements(
            path,
            f"{live_text}\n{directive}\n",
            requirements,
            "accepted live status",
        )
        assert any(directive in error for error in errors), errors
