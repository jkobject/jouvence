#!/usr/bin/env python3
"""Validate a causal-feature staged materialization manifest and its Parquets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from manage_db.materialize_causal_edge_features import validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-task-id", required=True)
    parser.add_argument("--expected-relation", action="append", required=True)
    args = parser.parse_args()
    errors = validate_manifest(
        args.manifest,
        expected_task_id=args.expected_task_id,
        expected_relations=set(args.expected_relation),
    )
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
