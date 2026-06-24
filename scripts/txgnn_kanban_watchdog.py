#!/usr/bin/env python3
"""TxGNN Kanban watchdog for review-required routing hygiene.

Default behavior is read-only dry-run. It scans the active TxGNN board for blocked
producer cards that contain a `review-required` handoff and verifies that each has
one of:

1. a linked child assigned to `reviewer` or `tester`, or
2. a comment that explicitly says it was routed to an ungated reviewer/tester card.

The script intentionally does not mutate the board unless `--apply` is passed.
In apply mode it uses the Hermes CLI, not raw SQLite writes, so task creation,
comments, and links go through the normal board event machinery.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REVIEW_CARD_RE = re.compile(r"\bt_[0-9a-f]{8}\b")
ROUTED_RE = re.compile(
    r"\b(?:routed|created)\b.*?\b(?:ungated\s+)?(reviewer|tester|cto|validation|validate|review)\b.*?\b(t_[0-9a-f]{8})\b",
    re.IGNORECASE | re.DOTALL,
)
TOFIX_RE = re.compile(
    r"\b(?:created_tofix|tofix|dev\s+fix|fix)\b[^\n]*(t_[0-9a-f]{8})\b",
    re.IGNORECASE,
)

PRODUCER_ASSIGNEES = {"dev", "worker", "builder"}
REVIEW_ASSIGNEES = {"reviewer", "tester", "cto"}
TERMINAL_STATUSES = {"done", "archived"}
DISPATCHABLE_REVIEW_STATUSES = {"ready", "running"}


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    body: str
    assignee: str
    status: str
    priority: int
    workspace_path: str
    result: str
    current_run_id: int | None


@dataclass(frozen=True)
class Route:
    producer: Task
    reviewer_id: str | None
    routed_by: str
    action: str
    closeable: bool = False


def db_path_from_env() -> Path:
    raw = os.environ.get("HERMES_KANBAN_DB") or os.path.expanduser(
        "~/.hermes/kanban/boards/txgnn/kanban.db"
    )
    return Path(raw).expanduser()


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"Kanban DB not found: {path}")
    # Use a plain path connection rather than SQLite URI mode: some macOS
    # Python/SQLite builds fail with `unable to open database file` on later
    # SELECTs for absolute file:// read-only URIs even though the file exists.
    # The watchdog itself is read-only unless --apply is used, and --apply goes
    # through the Hermes CLI rather than this SQLite connection.
    con = sqlite3.connect(str(path.resolve()))
    con.row_factory = sqlite3.Row
    return con


def fetch_tasks(con: sqlite3.Connection) -> list[Task]:
    rows = con.execute(
        """
        SELECT id, title, COALESCE(body, '') AS body, COALESCE(assignee, '') AS assignee,
               status, COALESCE(priority, 0) AS priority,
               COALESCE(workspace_path, '') AS workspace_path,
               COALESCE(result, '') AS result, current_run_id
        FROM tasks
        WHERE status = 'blocked'
        ORDER BY created_at ASC
        """
    ).fetchall()
    return [Task(**dict(row)) for row in rows]


def comments_for(con: sqlite3.Connection, task_id: str) -> list[str]:
    rows = con.execute(
        "SELECT body FROM task_comments WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
    ).fetchall()
    return [row["body"] or "" for row in rows]


def current_run_summary(con: sqlite3.Connection, task: Task) -> str:
    if not task.current_run_id:
        return ""
    row = con.execute(
        "SELECT COALESCE(summary, '') AS summary, COALESCE(metadata, '') AS metadata "
        "FROM task_runs WHERE id = ?",
        (task.current_run_id,),
    ).fetchone()
    if not row:
        return ""
    return f"{row['summary']}\n{row['metadata']}"


def linked_review_children(con: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT c.id, c.title, c.assignee, c.status
        FROM task_links l
        JOIN tasks c ON c.id = l.child_id
        WHERE l.parent_id = ?
          AND c.assignee IN ('reviewer', 'tester', 'cto')
          AND c.status NOT IN ('archived')
        ORDER BY c.created_at ASC
        """,
        (task_id,),
    ).fetchall()


def accepted_review_for(con: sqlite3.Connection, reviewer_id: str, producer_id: str) -> bool:
    row = con.execute(
        """
        SELECT COALESCE(r.summary, '') AS summary, COALESCE(r.metadata, '') AS metadata,
               t.status AS status, t.assignee AS assignee
        FROM tasks t
        LEFT JOIN task_runs r ON r.task_id = t.id
        WHERE t.id = ?
        ORDER BY r.started_at DESC
        LIMIT 1
        """,
        (reviewer_id,),
    ).fetchone()
    if not row or row["assignee"] not in REVIEW_ASSIGNEES or row["status"] != "done":
        return False

    summary = row["summary"] or ""
    metadata_raw = row["metadata"] or ""
    try:
        metadata = json.loads(metadata_raw) if metadata_raw else {}
    except json.JSONDecodeError:
        metadata = {}

    if isinstance(metadata, dict):
        verdict = str(metadata.get("verdict", "")).strip().lower()
        decision = str(metadata.get("decision", "")).strip().lower()
        status_label = str(metadata.get("status_label", "")).strip().lower()
        if metadata.get("approved") is False:
            return False
        if verdict in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}:
            return False
        if decision in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}:
            return False
        if status_label in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}:
            return False

        key = f"orchestrator_should_mark_{producer_id}_done_without_rerun"
        if metadata.get(key) is True:
            return True
        if metadata.get("approved") is True:
            encoded = json.dumps(metadata).lower()
            if f"accept_close_{producer_id}" in encoded or producer_id in encoded:
                return True
            if decision in {"accept", "approved", f"accept_close_{producer_id}"}:
                return True

    # Text fallback is intentionally narrow: accept only an explicit positive
    # close token and only when no structured negative metadata was present.
    # Do not infer approval from arbitrary text containing both "approved" and
    # "true"; reviewer tofix instructions often quote those words.
    decision_text = f"{summary}\n{metadata_raw}".lower()
    negative_re = re.compile(r"\b(approved\s*[:=]?\s*false|verdict\s*[:=]?\s*tofix|decision\s*[:=]?\s*needs[_ -]?fix|needs[_ -]?fix|rejected|\btofix\b)\b")
    if negative_re.search(decision_text):
        return False
    return f"accept_close_{producer_id}" in decision_text


def routed_comment_target(con: sqlite3.Connection, comments: Iterable[str], producer_id: str) -> tuple[str, bool] | None:
    for body in comments:
        match = ROUTED_RE.search(body)
        if not match:
            continue
        card = match.group(2)
        row = con.execute(
            "SELECT id, assignee, status FROM tasks WHERE id = ?", (card,)
        ).fetchone()
        if not row or row["assignee"] not in REVIEW_ASSIGNEES:
            continue
        if row["status"] not in TERMINAL_STATUSES:
            return card, False
        if accepted_review_for(con, card, producer_id):
            return card, True
    return None


def routed_tofix_target(con: sqlite3.Connection, texts: Iterable[str]) -> str | None:
    """Return an active follow-up fix card mentioned by a rejected review/guard.

    A producer blocked after reviewer rejection is no longer missing a reviewer
    route if the rejection already spawned or named a dev tofix/fix card. The
    watchdog should not close the producer, but it also should not create
    duplicate reviewers while the fix is queued/running.
    """
    for text in texts:
        for match in TOFIX_RE.finditer(text):
            card = match.group(1)
            row = con.execute(
                "SELECT id, assignee, status FROM tasks WHERE id = ?", (card,)
            ).fetchone()
            if not row:
                continue
            if row["assignee"] in PRODUCER_ASSIGNEES and row["status"] not in {"archived"}:
                return card
    return None


def linked_child_route(con: sqlite3.Connection, task: Task, linked: Iterable[sqlite3.Row]) -> Route | None:
    """Return a healthy linked-review route, ignoring parent-gated/deadlocked children."""
    for child in linked:
        child_id = child["id"]
        child_status = child["status"]
        child_assignee = child["assignee"]
        if child_status in DISPATCHABLE_REVIEW_STATUSES:
            return Route(
                task,
                child_id,
                "linked-child",
                f"ok: linked {child_assignee} card {child_id} ({child_status})",
            )
        if child_status == "done" and accepted_review_for(con, child_id, task.id):
            return Route(
                task,
                child_id,
                "accepted-review",
                f"ok: reviewer {child_id} accepted; producer can be closed without rerun",
                closeable=True,
            )
    return None


def is_txgnn_task(task: Task) -> bool:
    haystack = f"{task.title}\n{task.body}\n{task.workspace_path}".lower()
    return "txgnn" in haystack or "jouvence" in haystack or "/work/txgnn" in haystack


def has_review_required(task: Task, comments: Iterable[str], run_text: str) -> bool:
    haystack = "\n".join([task.title, task.body, task.result, run_text, *comments]).lower()
    return "review-required" in haystack


def classify(con: sqlite3.Connection) -> list[Route]:
    routes: list[Route] = []
    for task in fetch_tasks(con):
        comments = comments_for(con, task.id)
        run_text = current_run_summary(con, task)
        if task.assignee not in PRODUCER_ASSIGNEES:
            continue
        if not is_txgnn_task(task):
            continue
        if not has_review_required(task, comments, run_text):
            continue

        routed = routed_comment_target(con, comments, task.id)
        if routed:
            reviewer_id, accepted = routed
            if accepted:
                routes.append(
                    Route(
                        task,
                        reviewer_id,
                        "accepted-review",
                        f"ok: reviewer {reviewer_id} accepted; producer can be closed without rerun",
                        closeable=True,
                    )
                )
            else:
                routes.append(Route(task, reviewer_id, "comment", f"ok: routed by comment to {reviewer_id}"))
            continue

        linked_route = linked_child_route(con, task, linked_review_children(con, task.id))
        if linked_route:
            routes.append(linked_route)
            continue

        tofix_id = routed_tofix_target(con, [run_text, *comments])
        if tofix_id:
            routes.append(
                Route(
                    task,
                    tofix_id,
                    "tofix",
                    f"ok: rejected review/guard already routed follow-up fix card {tofix_id}",
                )
            )
            continue

        routes.append(Route(task, None, "missing", "create ungated reviewer card and comment producer"))
    return routes


def run_hermes(args: list[str]) -> str:
    proc = subprocess.run(["hermes", "kanban", *args], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes kanban {' '.join(args)} failed with {proc.returncode}:\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
        )
    return proc.stdout.strip()


def apply_missing(route: Route, board: str | None) -> str:
    producer = route.producer
    title = f"REVIEW {producer.id}: {producer.title[:72]}"
    body = (
        "Automatic reviewer card created by scripts/txgnn_kanban_watchdog.py.\n\n"
        f"Parent producer: `{producer.id}` — {producer.title}\n"
        "Review the producer's `review-required` handoff, verify artifacts/tests, "
        "and complete with metadata containing `approved: true` or blocking findings.\n\n"
        "This card is intentionally not parent-linked when the producer is already blocked; "
        "linking a blocked parent can deadlock reviewer dispatch on this board."
    )
    cmd = ["create", title, "--assignee", "reviewer", "--body", body, "--priority", str(max(producer.priority, 80))]
    if board:
        cmd.extend(["--board", board])
    out = run_hermes(cmd)
    match = REVIEW_CARD_RE.search(out)
    if not match:
        raise RuntimeError(f"Could not parse created reviewer id from: {out}")
    reviewer_id = match.group(0)
    comment = (
        f"Orchestration: routed the `review-required` handoff to ungated reviewer card `{reviewer_id}` "
        "(no parent edge on blocked producer, to avoid deadlock)."
    )
    ccmd = ["comment", producer.id, comment]
    if board:
        ccmd.extend(["--board", board])
    run_hermes(ccmd)
    return reviewer_id


def apply_close(route: Route, board: str | None) -> None:
    summary = (
        f"Closed after reviewer `{route.reviewer_id}` accepted the `review-required` handoff; "
        "no rerun required. See reviewer metadata for validation evidence."
    )
    metadata = json.dumps(
        {
            "closed_by_watchdog": True,
            "reviewer_id": route.reviewer_id,
            "decision": f"accept_close_{route.producer.id}",
            "status_label": "validated",
        }
    )
    cmd = ["complete", route.producer.id, "--summary", summary, "--metadata", metadata]
    if board:
        cmd.extend(["--board", board])
    run_hermes(cmd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=db_path_from_env())
    parser.add_argument("--board", default=os.environ.get("HERMES_KANBAN_BOARD"))
    parser.add_argument("--apply", action="store_true", help="create missing reviewer cards via Hermes CLI")
    parser.add_argument("--silent", action="store_true", help="print nothing when all routes are healthy")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    con = connect(args.db)
    routes = classify(con)
    missing = [r for r in routes if r.reviewer_id is None]
    closeable = [r for r in routes if r.closeable]

    applied: list[dict[str, str]] = []
    if args.apply:
        for route in missing:
            reviewer_id = apply_missing(route, args.board)
            applied.append({"producer_id": route.producer.id, "reviewer_id": reviewer_id})
        for route in closeable:
            apply_close(route, args.board)
            applied.append({"producer_id": route.producer.id, "closed_after_review": route.reviewer_id or ""})

    payload = {
        "db": str(args.db),
        "healthy": not missing,
        "review_required_producers": len(routes),
        "missing_routes": len(missing),
        "accepted_reviews_pending_close": len(closeable),
        "routes": [
            {
                "producer_id": r.producer.id,
                "producer_title": r.producer.title,
                "reviewer_id": r.reviewer_id,
                "routed_by": r.routed_by,
                "action": r.action,
                "closeable": r.closeable,
            }
            for r in routes
        ],
        "applied": applied,
    }

    if args.silent and payload["healthy"] and not args.json:
        return 0
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"TxGNN review watchdog: {payload['review_required_producers']} review-required producers; "
            f"{payload['missing_routes']} missing routes; "
            f"{payload['accepted_reviews_pending_close']} accepted reviews pending producer close"
        )
        for route in routes:
            print(f"- {route.producer.id}: {route.action}")
        if args.apply and applied:
            for item in applied:
                print(f"applied {item}")
    return 2 if missing and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
