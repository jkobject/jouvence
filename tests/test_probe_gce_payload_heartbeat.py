from datetime import UTC, datetime

import pytest

from scripts.probe_gce_payload_heartbeat import (
    parse_last_json_object,
    validate_payload_process,
)
from scripts.write_gene_genomic_embedding_heartbeat import build_heartbeat


def test_parse_last_json_object_ignores_remote_shell_noise() -> None:
    output = "(anon):setopt:7: can't change option: monitor\n{\"kind\": \"payload\", \"generation\": 3}\n"

    assert parse_last_json_object(output) == {"kind": "payload", "generation": 3}


def test_heartbeat_preserves_last_progress_timestamp_when_counters_are_frozen() -> None:
    previous = {
        "durable_rows": 10,
        "durable_windows": 10,
        "last_progress_at": "2026-07-22T10:00:00+00:00",
    }
    heartbeat = build_heartbeat(
        previous=previous,
        now=datetime(2026, 7, 22, 10, 1, tzinfo=UTC),
        durable_rows=10,
        durable_windows=10,
    )

    assert heartbeat["at"] == "2026-07-22T10:01:00+00:00"
    assert heartbeat["last_progress_at"] == "2026-07-22T10:00:00+00:00"


def test_heartbeat_advances_last_progress_timestamp_only_on_counter_increase() -> None:
    previous = {
        "durable_rows": 10,
        "durable_windows": 10,
        "last_progress_at": "2026-07-22T10:00:00+00:00",
    }
    heartbeat = build_heartbeat(
        previous=previous,
        now=datetime(2026, 7, 22, 10, 1, tzinfo=UTC),
        durable_rows=11,
        durable_windows=11,
    )
    assert heartbeat["last_progress_at"] == "2026-07-22T10:01:00+00:00"


def test_heartbeat_rejects_counter_regression() -> None:
    with pytest.raises(ValueError, match="regressed"):
        build_heartbeat(
            previous={"durable_rows": 10, "durable_windows": 10},
            now=datetime.now(UTC),
            durable_rows=9,
            durable_windows=10,
        )


def test_probe_rejects_dead_payload_pid(tmp_path) -> None:
    heartbeat = {
        "target": "gs://bucket/immutable-root",
        "phase": "resume_validate_finalize_publish",
        "payload_pid": 1234,
    }

    with pytest.raises(ValueError, match="not live"):
        validate_payload_process(
            heartbeat,
            expected_target="gs://bucket/immutable-root",
            expected_phase="resume_validate_finalize_publish",
            expected_command_substring="run_gene_genomic_embedding_payload.sh",
            proc_root=tmp_path,
        )


def test_probe_rejects_unrelated_live_payload_pid(tmp_path) -> None:
    heartbeat = {
        "target": "gs://bucket/immutable-root",
        "phase": "resume_validate_finalize_publish",
        "payload_pid": 1234,
    }
    process = tmp_path / "1234"
    process.mkdir()
    (process / "cmdline").write_bytes(b"python3\0unrelated.py\0")

    with pytest.raises(ValueError, match="exact payload command"):
        validate_payload_process(
            heartbeat,
            expected_target="gs://bucket/immutable-root",
            expected_phase="resume_validate_finalize_publish",
            expected_command_substring="run_gene_genomic_embedding_payload.sh",
            proc_root=tmp_path,
        )


def test_probe_rejects_partial_payload_command_match(tmp_path) -> None:
    heartbeat = {
        "target": "gs://bucket/immutable-root",
        "phase": "resume_validate_finalize_publish",
        "payload_pid": 1234,
    }
    process = tmp_path / "1234"
    process.mkdir()
    (process / "cmdline").write_bytes(
        b"bash\0evil-run_gene_genomic_embedding_payload.sh-wrapper\0"
    )

    with pytest.raises(ValueError, match="exact payload command"):
        validate_payload_process(
            heartbeat,
            expected_target="gs://bucket/immutable-root",
            expected_phase="resume_validate_finalize_publish",
            expected_command_substring="run_gene_genomic_embedding_payload.sh",
            proc_root=tmp_path,
        )


def test_probe_returns_process_proof_for_exact_live_payload(tmp_path) -> None:
    heartbeat = {
        "target": "gs://bucket/immutable-root",
        "phase": "resume_validate_finalize_publish",
        "payload_pid": 1234,
    }
    process = tmp_path / "1234"
    process.mkdir()
    (process / "cmdline").write_bytes(
        b"bash\0run_gene_genomic_embedding_payload.sh\0lease\0"
    )

    proof = validate_payload_process(
        heartbeat,
        expected_target="gs://bucket/immutable-root",
        expected_phase="resume_validate_finalize_publish",
        expected_command_substring="run_gene_genomic_embedding_payload.sh",
        proc_root=tmp_path,
    )

    assert proof["payload_pid_live"] is True
    assert "run_gene_genomic_embedding_payload.sh" in proof["payload_argv"]
