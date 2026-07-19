#!/usr/bin/env python3
"""Build bounded Jouvence v1 inferred-edge artifacts from an immutable snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from manage_db.inferred_relation_algebra import BuildConfig, RULES_BY_ID, build_inferred_edges


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--kg-snapshot-id", required=True)
    parser.add_argument("--kg-generations-json", default="{}")
    parser.add_argument("--producer-revision", required=True)
    parser.add_argument("--rule", action="append", choices=sorted(RULES_BY_ID), required=True)
    parser.add_argument("--max-anchors", type=int, default=1000)
    parser.add_argument("--max-input-rows", type=int, default=100_000)
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args(argv)

    generations = json.loads(args.kg_generations_json)
    if not isinstance(generations, dict):
        parser.error("--kg-generations-json must decode to an object")
    report = build_inferred_edges(
        BuildConfig(
            kg_root=args.kg_root,
            output_root=args.output_root,
            kg_snapshot_id=args.kg_snapshot_id,
            kg_generations={str(key): str(value) for key, value in generations.items()},
            producer_revision=args.producer_revision,
            rule_ids=tuple(args.rule),
            max_anchors=args.max_anchors,
            max_input_rows=args.max_input_rows,
            sample_limit=args.sample_limit,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
