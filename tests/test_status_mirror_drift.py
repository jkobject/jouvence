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