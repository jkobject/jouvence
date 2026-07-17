import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = ROOT / "scripts" / "txgnn_kanban_watchdog.py"
_spec = importlib.util.spec_from_file_location("txgnn_kanban_watchdog", WATCHDOG_PATH)
assert _spec and _spec.loader
watchdog = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = watchdog
_spec.loader.exec_module(watchdog)


def make_con() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT,
            assignee TEXT,
            status TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            workspace_path TEXT,
            result TEXT,
            current_run_id INTEGER,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_links (parent_id TEXT NOT NULL, child_id TEXT NOT NULL);
        CREATE TABLE task_comments (
            id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_runs (
            id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            started_at INTEGER NOT NULL,
            summary TEXT,
            metadata TEXT
        );
        """
    )
    return con


def insert_task(con: sqlite3.Connection, task_id: str, assignee: str, status: str, *, title: str = "TxGNN task", body: str = "", current_run_id: int | None = None, created_at: int = 1) -> None:
    con.execute(
        """
        INSERT INTO tasks (id, title, body, assignee, status, priority, workspace_path, result, current_run_id, created_at)
        VALUES (?, ?, ?, ?, ?, 90, '/work/txgnn', '', ?, ?)
        """,
        (task_id, title, body, assignee, status, current_run_id, created_at),
    )


def test_deadlocked_linked_child_does_not_mask_ungated_reviewer_comment() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    ungated_id = "t_4b86e4e1"
    linked_id = "t_41046dec"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, linked_id, "reviewer", "todo", title="Linked reviewer", created_at=2)
    insert_task(con, ungated_id, "reviewer", "running", title="Ungated reviewer", created_at=3)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, linked_id))
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'reviewer', ?, 4)",
        (
            producer_id,
            "Orchestration: created ungated reviewer card t_4b86e4e1 for the real review. "
            "Existing child t_41046dec is parent-gated on the blocked producer and deadlocked.",
        ),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.producer.id == producer_id
    assert route.reviewer_id == ungated_id
    assert route.routed_by == "comment"
    assert "linked-child" not in route.routed_by


def test_accepted_ungated_reviewer_takes_priority_over_deadlocked_linked_child() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    ungated_id = "t_4b86e4e1"
    linked_id = "t_41046dec"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, linked_id, "reviewer", "todo", title="Linked reviewer", created_at=2)
    insert_task(con, ungated_id, "reviewer", "done", title="Ungated reviewer", created_at=3)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, linked_id))
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'reviewer', ?, 4)",
        (
            producer_id,
            "Orchestration: created ungated reviewer card t_4b86e4e1 for the real review. "
            "Existing child t_41046dec is parent-gated on the blocked producer and deadlocked.",
        ),
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, ?)",
        (
            ungated_id,
            "accept_close_t_caacd3d1 approved",
            json.dumps({"approved": True, "decision": "accept_close_t_caacd3d1"}),
        ),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.reviewer_id == ungated_id
    assert route.routed_by == "accepted-review"
    assert route.closeable is True


def test_negative_reviewer_metadata_does_not_reroute_without_new_handoff() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    reviewer_id = "t_4b86e4e1"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, reviewer_id, "reviewer", "done", title="Rejected reviewer", created_at=2)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, reviewer_id))
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, ?)",
        (
            reviewer_id,
            "needs_fix: instructions mention accept_close_t_caacd3d1 and approved true as the required future token",
            json.dumps(
                {
                    "approved": False,
                    "verdict": "tofix",
                    "decision": "needs_fix",
                    "required_fixes": [
                        "Later, only if fixed, emit accept_close_t_caacd3d1 with approved true."
                    ],
                }
            ),
        ),
    )

    assert watchdog.accepted_review_for(con, reviewer_id, producer_id) is False
    routes = watchdog.classify(con)

    assert routes == []


def test_rejected_review_with_active_tofix_is_healthy_not_missing() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    reviewer_id = "t_4b86e4e1"
    tofix_id = "t_a0109212"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, reviewer_id, "reviewer", "done", title="Rejected reviewer", created_at=2)
    insert_task(con, tofix_id, "dev", "ready", title="TOFIX watchdog bug", created_at=3)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, reviewer_id))
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, ?)",
        (
            reviewer_id,
            "needs_fix: created_tofix t_a0109212",
            json.dumps({"approved": False, "verdict": "tofix", "created_tofix": tofix_id}),
        ),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'reviewer', ?, 6)",
        (producer_id, "Review rejected; dev fix t_a0109212 is the active path."),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.reviewer_id == tofix_id
    assert route.routed_by == "tofix"
    assert route.closeable is False


def test_fresh_handoff_with_unrelated_active_tofix_report_is_missing() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    unrelated_tofix_id = "t_a0109212"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: fixed watchdog; ready for review")
    insert_task(con, unrelated_tofix_id, "dev", "ready", title="Unrelated active TOFIX", created_at=2)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 3)",
        (
            producer_id,
            "review-required handoff:\nDry-run routes reported:\n- t_4b1227b3 -> active tofix t_a0109212",
        ),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.producer.id == producer_id
    assert route.reviewer_id is None
    assert route.routed_by == "missing"


def test_ungated_reviewer_comment_takes_priority_over_unrelated_tofix_report() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    reviewer_id = "t_4b86e4e1"
    unrelated_tofix_id = "t_a0109212"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: fixed watchdog; ready for review")
    insert_task(con, reviewer_id, "reviewer", "running", title="Ungated reviewer", created_at=2)
    insert_task(con, unrelated_tofix_id, "dev", "ready", title="Unrelated active TOFIX", created_at=3)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 4)",
        (
            producer_id,
            "review-required handoff:\nOrchestration: created ungated reviewer card t_4b86e4e1.\n"
            "Dry-run routes reported:\n- t_4b1227b3 -> active tofix t_a0109212",
        ),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.producer.id == producer_id
    assert route.reviewer_id == reviewer_id
    assert route.routed_by == "comment"


def test_dispatchable_linked_child_is_still_healthy_without_comment() -> None:
    con = make_con()
    producer_id = "t_feedbeef"
    linked_id = "t_deadbeef"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, linked_id, "tester", "ready", title="Ready tester", created_at=2)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, linked_id))

    routes = watchdog.classify(con)

    assert len(routes) == 1
    route = routes[0]
    assert route.reviewer_id == linked_id
    assert route.routed_by == "linked-child"
    assert route.closeable is False


def test_run_in_progress_blocker_without_manifest_does_not_route() -> None:
    con = make_con()
    producer_id = "t_92a76037"
    insert_task(
        con,
        producer_id,
        "dev",
        "blocked",
        title="TxGNN transcript NT producer",
        body="run-in-progress: detached MPS job still producing parts; no manifest yet; not review-required",
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 3)",
        (
            producer_id,
            "progress monitor: still waiting on active duplicate; superseded until t_1234abcd finishes",
        ),
    )

    assert watchdog.classify(con) == []


def test_new_dev_review_required_handoff_after_rejection_routes_again() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    reviewer_id = "t_4b86e4e1"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: initial review")
    insert_task(con, reviewer_id, "reviewer", "done", title="Rejected reviewer", created_at=2)
    con.execute("INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)", (producer_id, reviewer_id))
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, ?)",
        (
            reviewer_id,
            "needs_fix: stale manifest",
            json.dumps({"approved": False, "verdict": "tofix"}),
        ),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 6)",
        (producer_id, "review-required: fixed manifest and tests are ready for a fresh review"),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    assert routes[0].producer.id == producer_id
    assert routes[0].reviewer_id is None
    assert routes[0].routed_by == "missing"


def test_superseded_duplicate_blocker_suppresses_body_review_required_acceptance_text() -> None:
    con = make_con()
    producer_id = "t_0ec8d8e7"
    insert_task(
        con,
        producer_id,
        "dev",
        "blocked",
        title="TxGNN duplicate Lamin tranche",
        body="Acceptance criteria: end review-required after producing artifacts.",
        current_run_id=1,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, ?)",
        (
            producer_id,
            "superseded-duplicate: active LaminDB continuation is already running as t_647bf8ae",
            json.dumps({"decision": "superseded_duplicate_closed", "superseded_by": "t_647bf8ae"}),
        ),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'worker', ?, 4)",
        (producer_id, "Orchestration cleanup: duplicate of active producer t_647bf8ae; keep blocked."),
    )

    assert watchdog.classify(con) == []


def test_not_reviewable_run_summary_suppresses_stale_body_review_required_text() -> None:
    con = make_con()
    producer_id = "t_9f460b29"
    insert_task(
        con,
        producer_id,
        "dev",
        "blocked",
        title="TxGNN non-reviewable producer",
        body="Acceptance criteria: end review-required after producing artifacts.",
        current_run_id=1,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, '')",
        (producer_id, "not-reviewable: no implementation handoff or artifacts"),
    )

    assert watchdog.classify(con) == []


def test_non_review_blocker_can_be_overridden_by_new_real_review_required_handoff() -> None:
    con = make_con()
    producer_id = "t_caacd3d1"
    insert_task(
        con,
        producer_id,
        "dev",
        "blocked",
        title="TxGNN resumed producer",
        body="Acceptance criteria: end review-required after producing artifacts.",
        current_run_id=1,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 5, ?, '')",
        (producer_id, "long-run-in-progress: detached job still running; not review-required"),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 6)",
        (producer_id, "review-required: artifacts and tests are now ready for reviewer validation"),
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    assert routes[0].producer.id == producer_id
    assert routes[0].reviewer_id is None
    assert routes[0].routed_by == "missing"


def test_run_hermes_places_board_before_subcommand(monkeypatch) -> None:
    calls = []

    def fake_run(cmd, text, capture_output, check):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)

    assert watchdog.run_hermes(["create", "hello"], board="txgnn") == "ok"
    assert calls == [["hermes", "kanban", "--board", "txgnn", "create", "hello"]]
