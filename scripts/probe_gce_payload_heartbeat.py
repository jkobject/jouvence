#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--zone", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--heartbeat-path", required=True)
    args = parser.parse_args()
    remote = (
        f"for i in {{1..90}}; do if [[ -s {args.heartbeat_path} ]]; then "
        f"cat {args.heartbeat_path}; exit 0; fi; sleep 1; done; exit 1"
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
