#!/usr/bin/env python3
"""Build the approved staged Jouvence relation-composition allowlist v2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from manage_db.relation_composition_allowlist import (
    POLICY_REVISION,
    TEMPLATE_BY_ID,
    BuildConfig,
    build_composition_allowlist,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--staged-input-root", type=Path, action="append", default=[])
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--producer-revision", default=POLICY_REVISION)
    parser.add_argument("--template", action="append", choices=sorted(TEMPLATE_BY_ID))
    parser.add_argument("--max-rows-per-file", type=int, default=100_000)
    parser.add_argument("--max-paths-per-template", type=int, default=100_000)
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args(argv)
    report = build_composition_allowlist(
        BuildConfig(
            input_root=args.input_root,
            staged_input_roots=tuple(args.staged_input_root),
            output_root=args.output_root,
            snapshot_id=args.snapshot_id,
            producer_revision=args.producer_revision,
            template_ids=tuple(args.template or sorted(TEMPLATE_BY_ID)),
            max_rows_per_file=args.max_rows_per_file,
            max_paths_per_template=args.max_paths_per_template,
            sample_limit=args.sample_limit,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
