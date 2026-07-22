#!/usr/bin/env python3
"""Fail when the maintained human status mirrors disagree on their snapshot date."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIRRORS = (
    Path("TODO.md"),
    Path("todo.d/01_lamindb.md"),
    Path("todo.d/02_pyg_gnn.md"),
    Path("todo.d/03_embeddings.md"),
    Path("todo.d/04_relations.md"),
    Path("todo.d/05_remap.md"),
    Path("todo.d/06_process.md"),
)
ROUTING_REQUIREMENTS = {
    Path("todo.d/README.md"): {
        "required": ("historical/superseded dated context", "`TODO.md` plus live Kanban"),
        "forbidden": ("short current-state anchor",),
    },
    Path("docs/current_state_20260623.md"): {
        "required": ("Historical snapshot — superseded", "`TODO.md`", "live Kanban"),
        "forbidden": ("This is the short current-state anchor",),
    },
    Path("docs/guides/agent-context.md"): {
        "required": (
            "/Users/jkobject/Documents/jouvence` is the canonical local checkout",
            "/Users/jkobject/Documents/jouvence/.worktrees/<branch-or-task-id>/",
        ),
        "forbidden": ("`work/txgnn` is the canonical local worktree",),
    },
    Path("docs/README.md"): {
        "required": ("[`viewer-install.html`](viewer-install.html)", "historical/superseded snapshot"),
        "forbidden": (),
    },
    Path("CLAUDE.md"): {
        "required": (
            "Legacy, non-authoritative context",
            "[`AGENTS.md`](AGENTS.md)",
            "[`TODO.md`](TODO.md)",
        ),
        "forbidden": (),
    },
}
SUPERSEDED_CARDS = ("t_ce839966", "t_075f5353")
HISTORICAL_TERMS = ("superseded", "historical", "inert", "must not", "do not")
SNAPSHOT_RE = re.compile(r"^_Status snapshot: (\d{4}-\d{2}-\d{2})(?: [^.]*)?\._$")


def check_mirrors(expected_date: str) -> list[str]:
    errors: list[str] = []
    for relative_path in MIRRORS:
        path = REPO_ROOT / relative_path
        lines = path.read_text(encoding="utf-8").splitlines()
        dates = [match.group(1) for line in lines if (match := SNAPSHOT_RE.match(line))]
        if dates != [expected_date]:
            errors.append(
                f"{relative_path}: expected exactly one status snapshot dated "
                f"{expected_date}, found {dates or 'none'}"
            )

        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            for card_id in SUPERSEDED_CARDS:
                if card_id in line and not any(term in lowered for term in HISTORICAL_TERMS):
                    errors.append(
                        f"{relative_path}:{line_number}: superseded card {card_id} "
                        "is not explicitly marked historical/inert"
                    )

    for relative_path, requirements in ROUTING_REQUIREMENTS.items():
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for required in requirements["required"]:
            if required not in text:
                errors.append(f"{relative_path}: missing required routing text {required!r}")
        for forbidden in requirements["forbidden"]:
            if forbidden in text:
                errors.append(f"{relative_path}: contains stale routing text {forbidden!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    args = parser.parse_args()

    errors = check_mirrors(args.expected_date)
    if errors:
        print("status mirror drift check: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"status mirror drift check: PASS ({args.expected_date})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())