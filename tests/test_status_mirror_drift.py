from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_status_mirrors_match_current_snapshot_and_superseded_cards_are_historical() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_status_mirror_drift.py",
            "--expected-date",
            "2026-07-19",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status mirror drift check: PASS (2026-07-19)" in result.stdout