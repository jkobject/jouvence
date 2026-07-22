#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def build_heartbeat(
    *,
    previous: dict[str, Any] | None,
    now: datetime,
    durable_rows: int,
    durable_windows: int,
) -> dict[str, Any]:
    previous = previous or {}
    previous_rows = int(previous.get("durable_rows", 0))
    previous_windows = int(previous.get("durable_windows", 0))
    if durable_rows < previous_rows or durable_windows < previous_windows:
        raise ValueError("durable progress counters regressed")
    timestamp = now.astimezone(UTC).isoformat()
    progressed = durable_rows > previous_rows or durable_windows > previous_windows
    last_progress_at = (
        timestamp
        if progressed or not previous.get("last_progress_at")
        else str(previous["last_progress_at"])
    )
    return {
        "at": timestamp,
        "last_progress_at": last_progress_at,
        "durable_rows": int(durable_rows),
        "durable_windows": int(durable_windows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--lease-id", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--canonical-gene", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--payload-pid", type=int, required=True)
    args = parser.parse_args()
    durable_rows = durable_windows = 0
    if args.manifest.is_file():
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        validation = manifest.get("validation", {})
        if validation.get("passed"):
            durable_rows = int(validation.get("source_rows_embedded", 0))
            durable_windows = int(
                manifest.get("outputs", {})
                .get("gene_genomic_sequence_nt_embeddings", {})
                .get("windows_embedded", durable_rows)
            )
    canonical_ids = pq.read_table(args.canonical_gene, columns=["id"])["id"].to_pylist()
    payload = {
        "kind": "payload",
        "gcp_project_id": "jkobject-1549353370965",
        "instance": "txgnn-worker",
        "instance_id": "4268456364292488510",
        "zone": "europe-west1-b",
        "task": "t_03bf9e27",
        "lease_id": args.lease_id,
        "generation": args.generation,
        "payload_pid": args.payload_pid,
        "target": args.target,
        "phase": "resume_validate_finalize_publish",
        "durable_rows": durable_rows,
        "durable_windows": durable_windows,
        "source_denominator": pq.ParquetFile(args.source).metadata.num_rows,
        "exact_ensg_denominator": sum(
            bool(re.fullmatch(r"ENSG[0-9]+", str(node_id))) for node_id in canonical_ids
        ),
    }
    previous: dict[str, Any] | None = None
    if args.path.exists():
        previous = json.loads(args.path.read_text(encoding="utf-8"))
    progress = build_heartbeat(
        previous=previous,
        now=datetime.now(UTC),
        durable_rows=durable_rows,
        durable_windows=durable_windows,
    )
    payload.update(progress)
    tmp = args.path.with_suffix(args.path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, args.path)


if __name__ == "__main__":
    main()
