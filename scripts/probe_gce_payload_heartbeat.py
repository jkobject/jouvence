#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


def parse_last_json_object(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("SSH output contained no JSON object")


def validate_payload_process(
    heartbeat: dict[str, Any],
    *,
    expected_target: str,
    expected_phase: str,
    expected_command_substring: str,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Bind a heartbeat to the exact live remote payload process and target."""
    if heartbeat.get("target") != expected_target:
        raise ValueError("payload heartbeat target does not match exact target")
    if heartbeat.get("phase") != expected_phase:
        raise ValueError("payload heartbeat phase does not match exact phase")
    try:
        payload_pid = int(heartbeat["payload_pid"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("payload PID is malformed") from exc
    if payload_pid <= 0:
        raise ValueError("payload PID is malformed")
    try:
        raw_cmdline = (proc_root / str(payload_pid) / "cmdline").read_bytes()
    except OSError as exc:
        raise ValueError("payload PID is not live") from exc
    argv = [
        item.decode("utf-8", errors="replace")
        for item in raw_cmdline.split(b"\0")
        if item
    ]
    if not argv:
        raise ValueError("payload PID is not live")
    if expected_command_substring not in argv:
        raise ValueError("payload PID does not belong to exact payload command")
    proof = dict(heartbeat)
    proof["payload_pid_live"] = True
    proof["payload_argv"] = argv
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--zone", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--heartbeat-path", required=True)
    parser.add_argument("--lease-id", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--expected-target", required=True)
    parser.add_argument("--expected-phase", required=True)
    parser.add_argument("--expected-command-substring", required=True)
    args = parser.parse_args()
    code = """import json,sys,time
from pathlib import Path
path=Path(sys.argv[1]); lease=sys.argv[2]; generation=int(sys.argv[3])
target=sys.argv[4]; phase=sys.argv[5]; command=sys.argv[6]
for _ in range(90):
    try:
        value=json.loads(path.read_text())
    except (OSError,json.JSONDecodeError):
        value={}
    if value.get('kind') == 'payload' and value.get('lease_id') == lease and int(value.get('generation', -1)) == generation:
        if value.get('target') != target or value.get('phase') != phase:
            raise SystemExit(2)
        try:
            pid=int(value['payload_pid'])
            raw=(Path('/proc')/str(pid)/'cmdline').read_bytes()
        except (KeyError,TypeError,ValueError,OSError):
            raise SystemExit(2)
        argv=[part.decode('utf-8', errors='replace') for part in raw.split(b'\\0') if part]
        if pid <= 0 or not argv or command not in argv:
            raise SystemExit(2)
        value['payload_pid_live']=True; value['payload_argv']=argv
        print(json.dumps(value, sort_keys=True)); raise SystemExit(0)
    time.sleep(1)
raise SystemExit(1)
"""
    remote = " ".join(
        [
            "python3",
            "-c",
            shlex.quote(code),
            shlex.quote(args.heartbeat_path),
            shlex.quote(args.lease_id),
            shlex.quote(str(args.generation)),
            shlex.quote(args.expected_target),
            shlex.quote(args.expected_phase),
            shlex.quote(args.expected_command_substring),
        ]
    )
    result = subprocess.run(
        [
            "gcloud",
            "compute",
            "ssh",
            args.instance,
            "--zone",
            args.zone,
            "--project",
            args.project,
            "--command",
            remote,
        ],
        text=True,
        capture_output=True,
        timeout=110,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    print(json.dumps(parse_last_json_object(result.stdout), sort_keys=True))


if __name__ == "__main__":
    main()
