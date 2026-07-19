#!/usr/bin/env python3
"""Jouvence Kanban watchdog for review-required routing hygiene.

Default behavior is read-only dry-run. It scans the active Jouvence board for blocked
producer cards that contain a `review-required` handoff and verifies that each has
one of:

1. a canonical `reviewer` card for the same producer and immutable revision,
2. a dispatchable linked `reviewer` child, or
3. a comment that explicitly says it was routed to an ungated reviewer card.

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
REVIEW_REQUIRED_RE = re.compile(r"\breview[- ]required\b", re.IGNORECASE)
REVISION_RE = re.compile(
    r"(?:\b(?:commit|revision|head|git[-_ ]sha)\b[^\n]{0,48}?|@\s*)"
    r"(?P<revision>(?<![0-9A-Za-z_])[0-9a-fA-F]{7,40}(?![0-9a-fA-F]))",
    re.IGNORECASE,
)
NON_REVIEW_HANDOFF_RE = re.compile(
    r"\b(?:run[- ]in[- ]progress|blocked\s+by\s+active\s+duplicate|"
    r"superseded[- ]duplicate|superseded\s+until|long[- ]run[- ]in[- ]progress|"
    r"routing\s+guard|capacity\s+gate|heartbeat|progress|monitor(?:ing)?|"
    r"not[- ]reviewable|"
    r"not\s+(?:an?\s+)?(?:review[- ]required|implementation\s+handoff)|"
    r"no\s+`?review[- ]required`?\s+implementation\s+handoff)\b",
    re.IGNORECASE,
)

PRODUCER_ASSIGNEES = {"dev", "worker", "builder"}
REVIEW_ASSIGNEES = {"reviewer"}
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
    created_at: int


@dataclass(frozen=True)
class Comment:
    body: str
    author: str
    created_at: int


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
               COALESCE(result, '') AS result, current_run_id, created_at
        FROM tasks
        WHERE status = 'blocked'
        ORDER BY created_at ASC
        """
    ).fetchall()
    return [Task(**dict(row)) for row in rows]


def comments_for(con: sqlite3.Connection, task_id: str) -> list[Comment]:
    rows = con.execute(
        """
        SELECT COALESCE(body, '') AS body, COALESCE(author, '') AS author, created_at
        FROM task_comments
        WHERE task_id = ?
        ORDER BY created_at ASC
        """,
        (task_id,),
    ).fetchall()
    return [Comment(**dict(row)) for row in rows]


def current_run_summary(con: sqlite3.Connection, task: Task) -> tuple[str, int]:
    if not task.current_run_id:
        return "", 0
    row = con.execute(
        "SELECT COALESCE(summary, '') AS summary, COALESCE(metadata, '') AS metadata, started_at "
        "FROM task_runs WHERE id = ?",
        (task.current_run_id,),
    ).fetchone()
    if not row:
        return "", 0
    return f"{row['summary']}\n{row['metadata']}", int(row["started_at"] or 0)


def linked_review_children(con: sqlite3.Connection, task_id: str) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT c.id, c.title, c.assignee, c.status
        FROM task_links l
        JOIN tasks c ON c.id = l.child_id
        WHERE l.parent_id = ?
          AND c.assignee = 'reviewer'
          AND c.status NOT IN ('archived')
        ORDER BY c.created_at ASC
        """,
        (task_id,),
    ).fetchall()


def accepted_review_for(
    con: sqlite3.Connection,
    reviewer_id: str,
    producer_id: str,
    *,
    identity_verified: bool = False,
) -> bool:
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
    if (
        not row
        or row["assignee"] not in REVIEW_ASSIGNEES
        or row["status"] not in TERMINAL_STATUSES
    ):
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
            if identity_verified:
                return True
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


def routed_comment_target(con: sqlite3.Connection, comments: Iterable[Comment], producer_id: str) -> tuple[str, bool] | None:
    for comment in comments:
        match = ROUTED_RE.search(comment.body)
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


def revisions_in(text: str) -> list[str]:
    """Return immutable git-style revisions without mistaking task ids for SHAs."""
    return [match.group("revision").lower() for match in REVISION_RE.finditer(text or "")]


def revisions_match(left: str, right: str) -> bool:
    """Treat an unambiguous short SHA and its full SHA as the same revision."""
    left = left.lower()
    right = right.lower()
    return len(left) >= 7 and len(right) >= 7 and (
        left.startswith(right) or right.startswith(left)
    )


def producer_revision_identity(
    con: sqlite3.Connection,
    task: Task,
    comments: Iterable[Comment] | None = None,
) -> str | None:
    """Return the newest immutable revision asserted by the producer handoff."""
    candidates: list[tuple[int, str]] = [
        (task.created_at, task.body),
        (task.created_at, task.result),
    ]
    run_text, run_started_at = current_run_summary(con, task)
    if run_text:
        candidates.append((run_started_at, run_text))
    for comment in comments if comments is not None else comments_for(con, task.id):
        if comment.author in PRODUCER_ASSIGNEES:
            candidates.append((comment.created_at, comment.body))

    found: list[tuple[int, int, str]] = []
    for created_at, text in candidates:
        for revision in revisions_in(text):
            found.append((created_at, len(revision), revision))
    if not found:
        return None
    return max(found)[2]


def references_producer(text: str, producer_id: str) -> bool:
    """Recognize explicit producer fields/phrases, independent of title prefix."""
    escaped = re.escape(producer_id)
    patterns = (
        rf'"(?:producer_id|parent_producer)"\s*:\s*"{escaped}"',
        rf"\b(?:parent\s+)?producer(?:_id)?\b[^\n]{{0,120}}\b{escaped}\b",
        rf"\breview(?:er)?\s+(?:for\s+)?`?{escaped}`?\b",
    )
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in patterns)


def reviewer_evidence_text(con: sqlite3.Connection, reviewer_id: str) -> str:
    row = con.execute(
        """
        SELECT COALESCE(t.title, '') AS title, COALESCE(t.body, '') AS body,
               COALESCE(t.result, '') AS result,
               COALESCE(r.summary, '') AS summary, COALESCE(r.metadata, '') AS metadata
        FROM tasks t
        LEFT JOIN task_runs r ON r.id = (
            SELECT id FROM task_runs WHERE task_id = t.id
            ORDER BY started_at DESC, id DESC LIMIT 1
        )
        WHERE t.id = ?
        """,
        (reviewer_id,),
    ).fetchone()
    if not row:
        return ""
    comment_rows = con.execute(
        "SELECT COALESCE(body, '') AS body FROM task_comments "
        "WHERE task_id = ? ORDER BY created_at ASC, id ASC",
        (reviewer_id,),
    ).fetchall()
    return "\n".join(
        [
            *(str(row[key] or "") for key in row.keys()),
            *(comment["body"] for comment in comment_rows),
        ]
    )


def producer_revision_route(
    con: sqlite3.Connection,
    task: Task,
    comments: Iterable[Comment],
) -> Route | None:
    """Find any canonical reviewer covering this exact producer revision."""
    revision = producer_revision_identity(con, task, comments)
    if not revision:
        return None
    rows = con.execute(
        """
        SELECT id, status FROM tasks
        WHERE assignee = 'reviewer'
          AND status IN ('ready', 'running', 'done', 'archived')
        ORDER BY created_at ASC
        """
    ).fetchall()
    for row in rows:
        text = reviewer_evidence_text(con, row["id"])
        if not references_producer(text, task.id):
            continue
        if not any(
            revisions_match(revision, candidate) for candidate in revisions_in(text)
        ):
            continue
        if row["status"] in DISPATCHABLE_REVIEW_STATUSES:
            return Route(
                task,
                row["id"],
                "producer-revision",
                f"ok: reviewer {row['id']} covers immutable revision {revision}",
            )
        if accepted_review_for(
            con,
            row["id"],
            task.id,
            identity_verified=True,
        ):
            return Route(
                task,
                row["id"],
                "accepted-review",
                f"ok: reviewer {row['id']} accepted immutable revision {revision}",
                closeable=True,
            )
    return None


def active_producer_fix_card(con: sqlite3.Connection, texts: Iterable[str], producer_id: str) -> str | None:
    """Return an active producer fix card mentioned in trusted rejection text."""
    for text in texts:
        for match in TOFIX_RE.finditer(text):
            card = match.group(1)
            if card == producer_id:
                continue
            row = con.execute(
                "SELECT id, assignee, status FROM tasks WHERE id = ?", (card,)
            ).fetchone()
            if not row:
                continue
            if row["assignee"] in PRODUCER_ASSIGNEES and row["status"] not in {"archived"}:
                return card
    return None


def reviewer_ids_for_producer(con: sqlite3.Connection, task: Task, comments: Iterable[Comment]) -> set[str]:
    reviewer_ids: set[str] = {child["id"] for child in linked_review_children(con, task.id)}
    for comment in comments:
        match = ROUTED_RE.search(comment.body)
        if not match:
            continue
        reviewer_id = match.group(2)
        row = con.execute(
            "SELECT id, assignee FROM tasks WHERE id = ?", (reviewer_id,)
        ).fetchone()
        if row and row["assignee"] in REVIEW_ASSIGNEES:
            reviewer_ids.add(reviewer_id)
    return reviewer_ids


def routed_tofix_target(con: sqlite3.Connection, task: Task, comments: Iterable[Comment]) -> str | None:
    """Return an active follow-up fix card from this producer's rejected-review context.

    A producer blocked after reviewer rejection is no longer missing a reviewer
    route if the rejection already spawned or named a dev tofix/fix card. The
    watchdog should not close the producer, but it also should not create
    duplicate reviewers while the fix is queued/running.

    This intentionally does not scan arbitrary producer comments: producer
    handoffs and dry-run reports often mention unrelated active tofix cards.
    Only same-producer reviewer run text, or reviewer-authored rejection
    comments on this producer, can suppress duplicate reviewer routing.
    """
    trusted_texts: list[str] = []
    for reviewer_id in reviewer_ids_for_producer(con, task, comments):
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
            continue
        if accepted_review_for(con, reviewer_id, task.id):
            continue
        trusted_texts.append(f"{row['summary']}\n{row['metadata']}")

    rejection_comment_re = re.compile(r"\b(reject(?:ed|ion)?|needs[_ -]?fix|tofix)\b", re.IGNORECASE)
    for comment in comments:
        if comment.author in REVIEW_ASSIGNEES and rejection_comment_re.search(comment.body):
            trusted_texts.append(comment.body)

    return active_producer_fix_card(con, trusted_texts, task.id)


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


def has_review_required_handoff(text: str) -> bool:
    return bool(REVIEW_REQUIRED_RE.search(text)) and not NON_REVIEW_HANDOFF_RE.search(text)


def latest_rejected_review_at(con: sqlite3.Connection, task: Task, comments: Iterable[Comment]) -> int:
    reviewer_ids: set[str] = set()
    latest = 0
    rejected_comment_re = re.compile(
        r"\b(?:review[-_ ]result\s*:\s*changes[-_ ]requested|"
        r"verdict\s*:\s*(?:tofix|needs[-_ ]fix|rejected)|needs[-_ ]fix)\b",
        re.IGNORECASE,
    )
    for comment in comments:
        if comment.author in REVIEW_ASSIGNEES and rejected_comment_re.search(comment.body):
            latest = max(latest, comment.created_at)
    for child in linked_review_children(con, task.id):
        reviewer_ids.add(child["id"])
    for comment in comments:
        match = ROUTED_RE.search(comment.body)
        if match:
            reviewer_ids.add(match.group(2))

    for reviewer_id in reviewer_ids:
        row = con.execute(
            """
            SELECT COALESCE(r.summary, '') AS summary, COALESCE(r.metadata, '') AS metadata,
                   COALESCE(r.started_at, 0) AS started_at, t.status AS status, t.assignee AS assignee
            FROM tasks t
            LEFT JOIN task_runs r ON r.task_id = t.id
            WHERE t.id = ?
            ORDER BY r.started_at DESC
            LIMIT 1
            """,
            (reviewer_id,),
        ).fetchone()
        if not row or row["assignee"] not in REVIEW_ASSIGNEES or row["status"] != "done":
            continue
        if accepted_review_for(con, reviewer_id, task.id):
            continue

        metadata_raw = row["metadata"] or ""
        try:
            metadata = json.loads(metadata_raw) if metadata_raw else {}
        except json.JSONDecodeError:
            metadata = {}
        if isinstance(metadata, dict):
            verdict = str(metadata.get("verdict", "")).strip().lower()
            decision = str(metadata.get("decision", "")).strip().lower()
            status_label = str(metadata.get("status_label", "")).strip().lower()
            if (
                metadata.get("approved") is False
                or verdict in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}
                or decision in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}
                or status_label in {"tofix", "needs_fix", "blocked", "reject", "rejected", "fail", "failed"}
            ):
                latest = max(latest, int(row["started_at"] or 0))
                continue

        decision_text = f"{row['summary']}\n{metadata_raw}".lower()
        negative_re = re.compile(r"\b(approved\s*[:=]?\s*false|verdict\s*[:=]?\s*tofix|decision\s*[:=]?\s*needs[_ -]?fix|needs[_ -]?fix|rejected|\btofix\b)\b")
        if negative_re.search(decision_text):
            latest = max(latest, int(row["started_at"] or 0))
    return latest


def has_fresh_review_required(
    task: Task,
    comments: Iterable[Comment],
    run_text: str,
    run_started_at: int,
    newer_than: int,
) -> bool:
    candidates: list[tuple[str, int]] = [
        (task.body, task.created_at),
        (task.result, task.created_at),
    ]
    if run_text:
        candidates.append((run_text, run_started_at))
    for comment in comments:
        # Reviewer/orchestration comments can mention the words "review-required"
        # while reporting routing/progress. They are not producer handoffs.
        if comment.author in PRODUCER_ASSIGNEES:
            candidates.append((comment.body, comment.created_at))

    return any(created_at > newer_than and has_review_required_handoff(text) for text, created_at in candidates)


def latest_non_review_blocker_at(
    task: Task,
    comments: Iterable[Comment],
    run_text: str,
    run_started_at: int,
) -> int:
    """Return the newest explicit non-review blocker timestamp for a producer.

    Producer task bodies often contain acceptance criteria telling the eventual
    worker to end with `review-required`. If a later run blocks as a duplicate,
    capacity gate, or long-running guard, that original body text is no longer a
    genuine review handoff and must not trigger reviewer routing. A newer dev
    `review-required` comment/run can still override this timestamp.
    """
    candidates: list[tuple[str, int]] = [(task.result, task.created_at)]
    if run_text:
        candidates.append((run_text, run_started_at))
    for comment in comments:
        candidates.append((comment.body, comment.created_at))

    latest = 0
    for text, created_at in candidates:
        if text and NON_REVIEW_HANDOFF_RE.search(text):
            latest = max(latest, created_at)
    return latest


def review_rejection_limit_reached(comments: Iterable[Comment]) -> bool:
    """Stop automatic routing after the explicit third rejected revision."""
    fail_count_re = re.compile(r"\breview_fail_count\s*:\s*(\d+)\s*/\s*3\b", re.IGNORECASE)
    for comment in comments:
        if comment.author not in REVIEW_ASSIGNEES:
            continue
        match = fail_count_re.search(comment.body)
        if match and int(match.group(1)) >= 3:
            return True
    return False


def classify(con: sqlite3.Connection) -> list[Route]:
    routes: list[Route] = []
    for task in fetch_tasks(con):
        comments = comments_for(con, task.id)
        run_text, run_started_at = current_run_summary(con, task)
        if task.assignee not in PRODUCER_ASSIGNEES:
            continue
        if not is_txgnn_task(task):
            continue
        if review_rejection_limit_reached(comments):
            continue

        rejected_at = max(
            latest_rejected_review_at(con, task, comments),
            latest_non_review_blocker_at(task, comments, run_text, run_started_at),
        )
        if not has_fresh_review_required(task, comments, run_text, run_started_at, rejected_at):
            # A rejected review with an active same-producer tofix/fix card is
            # already routed away from review. Keep reporting it as healthy, but
            # do not scan arbitrary producer report text for unrelated tofix ids.
            tofix_id = routed_tofix_target(con, task, comments)
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

        revision_route = producer_revision_route(con, task, comments)
        if revision_route:
            routes.append(revision_route)
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

        routes.append(Route(task, None, "missing", "create ungated reviewer card and comment producer"))
    return routes


def run_hermes(args: list[str], board: str | None = None) -> str:
    cmd = ["hermes", "kanban"]
    if board:
        # `--board` is a global option for `hermes kanban` and must appear
        # before the subcommand (`create`, `comment`, `complete`, ...).
        cmd.extend(["--board", board])
    cmd.extend(args)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} failed with {proc.returncode}:\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
        )
    return proc.stdout.strip()


def review_idempotency_key(producer: Task, revision: str | None) -> str:
    identity = revision or (
        f"run-{producer.current_run_id}" if producer.current_run_id else f"created-{producer.created_at}"
    )
    return f"jouvence:review:{producer.id}:revision:{identity.lower()}"


def apply_missing(
    route: Route,
    board: str | None,
    *,
    revision: str | None = None,
) -> str:
    producer = route.producer
    revision_label = revision or "unavailable"
    title = f"REVIEW {producer.id} @ {revision_label[:12]}: {producer.title[:58]}"
    body = (
        "Automatic reviewer card created by scripts/txgnn_kanban_watchdog.py.\n\n"
        f"Producer id: `{producer.id}`\n"
        f"Immutable revision: `{revision_label}`\n"
        f"Producer title: {producer.title}\n"
        "Review the producer's `review-required` handoff and verify artifacts/tests.\n\n"
        "Build→review→build policy:\n"
        "- If accepted, comment on the producer with `review-result: accepted`, evidence, "
        "and `operator may complete <producer_id> as resolved_by_reviewer_gate`; then complete this review with metadata containing `approved: true`.\n"
        "- If changes are needed, comment on the producer with `review-result: changes-requested`, exact fixes, and `review_fail_count: N/3`; unblock/requeue the same producer for rebuild when possible. Do not create a separate tofix unless the fix is separable/different owner.\n"
        "- After 3 failed review rounds, leave the producer blocked for human/orchestrator decision.\n\n"
        "This reviewer is intentionally not parent-linked when the producer is already blocked; "
        "linking a blocked parent can deadlock reviewer dispatch on this board."
    )
    cmd = [
        "create",
        title,
        "--assignee",
        "reviewer",
        "--body",
        body,
        "--priority",
        str(max(producer.priority, 80)),
        "--idempotency-key",
        review_idempotency_key(producer, revision),
    ]
    out = run_hermes(cmd, board=board)
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        parsed = {}
    reviewer_id = parsed.get("task_id") if isinstance(parsed, dict) else None
    if not reviewer_id:
        match = REVIEW_CARD_RE.search(out)
        if not match:
            raise RuntimeError(f"Could not parse created reviewer id from: {out}")
        reviewer_id = match.group(0)
    comment = (
        f"Orchestration: routed producer revision `{revision_label}` to ungated reviewer card "
        f"`{reviewer_id}` (no parent edge on blocked producer, to avoid deadlock)."
    )
    run_hermes(["comment", producer.id, comment], board=board)
    return reviewer_id


def apply_missing_authoritative(
    stale_route: Route,
    board: str | None,
    db_path: Path,
) -> str | None:
    """Re-read board state immediately before the idempotent create mutation."""
    con = connect(db_path)
    try:
        current = next(
            (route for route in classify(con) if route.producer.id == stale_route.producer.id),
            None,
        )
        if current is None or current.reviewer_id is not None:
            return None
        revision = producer_revision_identity(
            con,
            current.producer,
            comments_for(con, current.producer.id),
        )
    finally:
        con.close()
    return apply_missing(current, board, revision=revision)


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
    run_hermes(cmd, board=board)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=db_path_from_env())
    parser.add_argument("--board", default=os.environ.get("HERMES_KANBAN_BOARD"))
    parser.add_argument("--apply", action="store_true", help="create missing reviewer cards via Hermes CLI")
    parser.add_argument("--silent", action="store_true", help="print nothing when all routes are healthy")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    con = connect(args.db)
    try:
        routes = classify(con)
    finally:
        con.close()
    missing = [r for r in routes if r.reviewer_id is None]
    closeable = [r for r in routes if r.closeable]

    applied: list[dict[str, str]] = []
    if args.apply:
        for route in missing:
            reviewer_id = apply_missing_authoritative(route, args.board, args.db)
            if reviewer_id:
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
            f"Jouvence review watchdog: {payload['review_required_producers']} review-required producers; "
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
