import importlib.util
import json
import sqlite3
import sys
import threading
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
            idempotency_key TEXT,
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
        INSERT INTO tasks (id, title, body, assignee, status, priority, workspace_path, result, idempotency_key, current_run_id, created_at)
        VALUES (?, ?, ?, ?, ?, 90, '/work/txgnn', '', NULL, ?, ?)
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


def test_dispatchable_linked_reviewer_is_still_healthy_without_comment() -> None:
    con = make_con()
    producer_id = "t_feedbeef"
    linked_id = "t_deadbeef"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: please review")
    insert_task(con, linked_id, "reviewer", "ready", title="Ready reviewer", created_at=2)
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


def test_incident_manual_revision_reviewer_suppresses_watchdog_duplicate() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    manual_id = "t_ec266263"
    duplicate_id = "t_0f87e931"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: PR #15", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 10)",
        (producer_id, f"Implementation handoff for PR #15 at immutable commit `{revision}`."),
    )
    insert_task(
        con,
        manual_id,
        "reviewer",
        "running",
        title="review: PRISM 20Q2 staged candidate PR #15",
        body=f"Independent review for producer `{producer_id}` at immutable commit `{revision}`.",
        created_at=11,
    )
    insert_task(
        con,
        duplicate_id,
        "reviewer",
        "done",
        title=f"REVIEW {producer_id}: generated duplicate",
        body=f"Parent producer: `{producer_id}`; duplicate/no-op.",
        created_at=12,
    )
    insert_task(
        con,
        "t_aaaaaaaa",
        "reviewer",
        "running",
        title="unrelated reviewer",
        body=f"Independent review for producer `t_bbbbbbbb` at immutable commit `{revision}`.",
        created_at=13,
    )
    insert_task(
        con,
        "t_cccccccc",
        "reviewer",
        "running",
        title="stale reviewer",
        body=f"Independent review for producer `{producer_id}` at immutable commit `1111111111111111111111111111111111111111`.",
        created_at=14,
    )

    routes = watchdog.classify(con)

    assert len(routes) == 1
    assert routes[0].reviewer_id == manual_id
    assert routes[0].routed_by == "producer-revision"


def test_revision_extraction_ignores_session_dates_and_task_ids() -> None:
    revision = "8a85542f2a948abc50203bfcff530383772c389d"

    assert watchdog.revisions_in(
        "session 20260719_150632_6a293b for t_1cdcf211; no revision yet"
    ) == []
    assert watchdog.revisions_in(f"review @ {revision[:8]}") == [revision[:8]]
    assert watchdog.revisions_in(f"immutable commit `{revision}`") == [revision]


def test_accepted_terminal_reviewer_for_same_revision_is_closeable() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    reviewer_id = "t_ec266263"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: PR #15", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 10)",
        (producer_id, f"review-required at immutable commit `{revision}`"),
    )
    insert_task(
        con,
        reviewer_id,
        "reviewer",
        "done",
        body=f"Review producer `{producer_id}` at immutable commit `{revision}`.",
        created_at=11,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, ?, 12, ?, ?)",
        (
            reviewer_id,
            "review accepted after independent validation",
            json.dumps({"approved": True}),
        ),
    )

    route = watchdog.classify(con)[0]

    assert route.reviewer_id == reviewer_id
    assert route.routed_by == "accepted-review"
    assert route.closeable is True


def test_changes_requested_for_prior_revision_does_not_cover_fresh_revision() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    old_revision = "1111111111111111111111111111111111111111"
    new_revision = "2222222222222222222222222222222222222222"
    insert_task(con, producer_id, "dev", "blocked", body="review-required: PR #15", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 20)",
        (producer_id, f"review-required fixed at immutable commit `{new_revision}`"),
    )
    insert_task(
        con,
        "t_ec266263",
        "reviewer",
        "done",
        body=f"Review producer `{producer_id}` at immutable commit `{old_revision}`.",
        created_at=10,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, 't_ec266263', 11, 'changes requested', ?)",
        (json.dumps({"approved": False, "producer_id": producer_id, "revision": old_revision}),),
    )

    route = watchdog.classify(con)[0]

    assert route.reviewer_id is None
    assert route.routed_by == "missing"
    assert watchdog.review_idempotency_key(route.producer, new_revision).endswith(new_revision)


def test_manual_changes_requested_comment_suppresses_same_stale_handoff() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 10)",
        (producer_id, f"review-required at immutable commit `{revision}`"),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'reviewer', ?, 20)",
        (producer_id, f"review-result: changes-requested for immutable revision `{revision}`"),
    )
    insert_task(
        con,
        "t_ec266263",
        "reviewer",
        "done",
        body=f"Review producer `{producer_id}` at immutable commit `{revision}`.",
        created_at=11,
    )
    con.execute(
        "INSERT INTO task_runs (id, task_id, started_at, summary, metadata) VALUES (1, 't_ec266263', 12, 'changes requested', ?)",
        (json.dumps({"approved": False, "verdict": "tofix"}),),
    )

    assert watchdog.classify(con) == []


def test_three_rejected_revisions_stop_even_after_fresh_handoff() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    insert_task(con, producer_id, "dev", "blocked", body="review-required", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'reviewer', ?, 20)",
        (
            producer_id,
            "review-result: changes-requested for revision `11111111`; review_fail_count: 3/3",
        ),
    )
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 30)",
        (producer_id, "review-required fixed at immutable commit `22222222`"),
    )

    assert watchdog.classify(con) == []


def test_tester_for_same_revision_is_not_canonical_reviewer_coverage() -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 2)",
        (producer_id, f"review-required commit `{revision}`"),
    )
    insert_task(
        con,
        "t_deadbeef",
        "tester",
        "running",
        body=f"Review producer `{producer_id}` at commit `{revision}`.",
        created_at=3,
    )

    route = watchdog.classify(con)[0]

    assert route.reviewer_id is None
    assert route.routed_by == "missing"


def test_concurrent_creates_share_one_deterministic_idempotency_key(monkeypatch) -> None:
    con = make_con()
    producer_id = "t_1cdcf211"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required", created_at=1)
    route = watchdog.Route(
        watchdog.fetch_tasks(con)[0], None, "missing", "create ungated reviewer"
    )
    created_by_key: dict[str, str] = {}
    lock = threading.Lock()

    def fake_run_hermes(args, board=None):
        if args[0] == "create":
            assert "--parent" not in args
            assert args[args.index("--assignee") + 1] == "reviewer"
            key = args[args.index("--idempotency-key") + 1]
            with lock:
                created_by_key.setdefault(key, "t_ec266263")
            return json.dumps({"task_id": created_by_key[key]})
        return "ok"

    monkeypatch.setattr(watchdog, "run_hermes", fake_run_hermes)
    results: list[str] = []

    def create() -> None:
        results.append(watchdog.apply_missing(route, "txgnn", revision=revision))

    threads = [threading.Thread(target=create), threading.Thread(target=create)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == ["t_ec266263", "t_ec266263"]
    assert list(created_by_key) == [watchdog.review_idempotency_key(route.producer, revision)]


def test_apply_rechecks_authoritative_board_before_mutation(tmp_path, monkeypatch) -> None:
    db = tmp_path / "board.db"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    fixture = make_con()
    fixture.backup(con)
    fixture.close()
    producer_id = "t_1cdcf211"
    revision = "8a85542f2a948abc50203bfcff530383772c389d"
    insert_task(con, producer_id, "dev", "blocked", body="review-required", created_at=1)
    con.execute(
        "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'dev', ?, 2)",
        (producer_id, f"review-required commit `{revision}`"),
    )
    con.commit()
    stale_route = watchdog.classify(con)[0]
    insert_task(
        con,
        "t_ec266263",
        "reviewer",
        "running",
        body=f"Review producer `{producer_id}` at commit `{revision}`.",
        created_at=3,
    )
    con.commit()
    con.close()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("mutation attempted despite authoritative reviewer coverage")

    monkeypatch.setattr(watchdog, "run_hermes", fail_if_called)

    assert watchdog.apply_missing_authoritative(stale_route, "txgnn", db) is None
