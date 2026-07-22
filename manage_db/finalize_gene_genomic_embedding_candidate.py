from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from manage_db.build_gene_genomic_sequence_embeddings import build_denominator_reason_rows

TASK_ID = "t_03bf9e27"
EXPECTED_DIM = 512
EXPECTED_MODEL = "InstaDeepAI/nucleotide-transformer-v2-50m-multi-species"
EXPECTED_REVISION = "81b29e5786726d891dbf929404ef20adca5b36f1"
MODEL_LICENSE = "CC-BY-NC-SA-4.0"
SOURCE_RELEASE = "Ensembl release 114 / GRCh38 primary assembly"
SOURCE_LICENSE = "EMBL-EBI open data / attribution"
SOURCE_CITATION = "Ensembl Project; GRCh38 reference assembly via Ensembl release resources."


def run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def replace_embedding_column(table: pa.Table, *, expected_dim: int = EXPECTED_DIM) -> pa.Table:
    matrix = np.asarray(table["embedding"].to_pylist(), dtype=np.float32)
    if matrix.shape != (table.num_rows, expected_dim):
        raise RuntimeError(f"unexpected embedding shape {matrix.shape}")
    fixed = pa.FixedSizeListArray.from_arrays(
        pa.array(matrix.reshape(-1), type=pa.float32()), expected_dim
    )
    table = table.set_column(table.schema.get_field_index("embedding"), "embedding", fixed)
    table = table.set_column(
        table.schema.get_field_index("embedding_dtype"),
        "embedding_dtype",
        pa.array(["float32"] * table.num_rows),
    )
    table = table.set_column(
        table.schema.get_field_index("embedding_format"),
        "embedding_format",
        pa.array(["fixed_size_list_float32"] * table.num_rows),
    )
    return table


def expected_embedding_type(expected_dim: int = EXPECTED_DIM) -> str:
    return str(pa.list_(pa.float32(), expected_dim))


def classify_gene_denominator(
    *,
    canonical_ids: set[str],
    interval_ids: set[str],
    sequence_ids: set[str],
    embedded_ids: set[str],
) -> dict[str, list[Any]]:
    eligible_ensg = sorted(
        node_id for node_id in canonical_ids if re.fullmatch(r"ENSG[0-9]+", node_id)
    )
    missing_rows = build_denominator_reason_rows(
        denominator_ids=set(eligible_ensg),
        interval_ids=interval_ids,
        sequence_ids=sequence_ids,
        embedded_ids=embedded_ids,
    )
    quarantine_rows = []
    for node_id in sorted(canonical_ids - set(eligible_ensg)):
        if node_id.startswith(("NCBI:", "NCBIGene:")):
            reason = "unmapped_ncbi_alias"
        elif node_id.startswith("ENS") and not node_id.startswith("ENSG"):
            reason = "non_human_ensembl_homologue"
        else:
            reason = "non_ensg_namespace"
        quarantine_rows.append({"node_id": node_id, "reason": reason})
    return {
        "eligible_ensg": eligible_ensg,
        "missing_rows": missing_rows,
        "quarantine_rows": quarantine_rows,
    }


def compact_embeddings(parts: list[Path], output: Path) -> dict[str, Any]:
    writer: pq.ParquetWriter | None = None
    node_ids: list[str] = []
    feature_keys: list[str] = []
    row_indices: list[int] = []
    windows = 0
    non_finite = 0
    all_zero = 0
    input_inventory = []
    output.parent.mkdir(parents=True, exist_ok=True)
    for part in parts:
        input_inventory.append(
            {"path": str(part), "bytes": part.stat().st_size, "sha256": sha256(part)}
        )
        parquet = pq.ParquetFile(part)
        for batch in parquet.iter_batches(batch_size=512):
            table = replace_embedding_column(pa.Table.from_batches([batch]))
            matrix = np.asarray(table["embedding"].to_pylist(), dtype=np.float32)
            non_finite += int((~np.isfinite(matrix)).any(axis=1).sum())
            all_zero += int((np.linalg.norm(matrix, axis=1) == 0).sum())
            node_ids.extend(str(value) for value in table["node_id"].to_pylist())
            feature_keys.extend(str(value) for value in table["source_feature_key"].to_pylist())
            row_indices.extend(int(value) for value in table["source_row_index"].to_pylist())
            windows += int(pc.sum(table["window_count"]).as_py())
            if writer is None:
                writer = pq.ParquetWriter(output, table.schema, compression="zstd", use_dictionary=True)
            elif table.schema != writer.schema:
                table = table.cast(writer.schema)
            writer.write_table(table)
    if writer is None:
        raise RuntimeError("no embedding part rows found")
    writer.close()
    return {
        "input_parts": len(parts),
        "input_part_inventory": input_inventory,
        "rows": len(node_ids),
        "windows": windows,
        "node_ids": node_ids,
        "source_feature_keys": feature_keys,
        "source_row_indices": row_indices,
        "duplicate_node_ids": len(node_ids) - len(set(node_ids)),
        "duplicate_source_feature_keys": len(feature_keys) - len(set(feature_keys)),
        "non_finite_vectors": non_finite,
        "all_zero_vectors": all_zero,
        "physical_embedding_type": str(pq.read_schema(output).field("embedding").type),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
    }


def gcs_description(uri: str) -> dict[str, Any]:
    value = json.loads(run(["gcloud", "storage", "objects", "describe", uri, "--format=json"], capture=True))
    return {
        key: value.get(key)
        for key in ("name", "bucket", "generation", "metageneration", "size", "md5Hash", "crc32c", "createTime", "updateTime")
    }


def create_only_upload(local: Path, uri: str) -> dict[str, Any]:
    exists = subprocess.run(
        ["gcloud", "storage", "objects", "describe", uri, "--format=json"],
        text=True,
        capture_output=True,
    )
    if exists.returncode == 0:
        raise RuntimeError(f"immutable candidate object already exists: {uri}")
    run(["gcloud", "storage", "cp", "--if-generation-match=0", str(local), uri])
    description = gcs_description(uri)
    if int(description["size"]) != local.stat().st_size:
        raise RuntimeError(f"uploaded size mismatch for {uri}")
    return description


def publish_candidate(candidate_dir: Path, gcs_root: str, readback_dir: Path) -> dict[str, Any]:
    gcs_root = gcs_root.rstrip("/") + "/"
    objects: dict[str, Any] = {}
    files = sorted(path for path in candidate_dir.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(candidate_dir).as_posix()
        objects[relative] = create_only_upload(path, gcs_root + relative)
    for path in files:
        relative = path.relative_to(candidate_dir).as_posix()
        target = readback_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["gcloud", "storage", "cp", gcs_root + relative, str(target)])
        if sha256(target) != sha256(path):
            raise RuntimeError(f"readback hash mismatch: {relative}")
    return objects


def parquet_rows(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows


def read_canonical_gene_ids(path: Path) -> set[str]:
    table = pq.read_table(path, columns=["id"])
    return {str(value) for value in table["id"].to_pylist()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--builder-output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--canonical-gene", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--gcs-root", required=True)
    parser.add_argument("--source-origin-root", required=True)
    parser.add_argument("--repository-commit", required=True)
    args = parser.parse_args()

    if platform.node() != "txgnn-worker":
        raise RuntimeError("production finalization must run on txgnn-worker")
    if os.environ.get("HERMES_KANBAN_TASK") != TASK_ID:
        raise RuntimeError("wrong or absent HERMES_KANBAN_TASK")
    if args.candidate_dir.exists():
        raise RuntimeError(f"candidate directory already exists: {args.candidate_dir}")

    builder_manifest = json.loads((args.builder_output / "manifest.json").read_text())
    if not builder_manifest["validation"]["passed"]:
        raise RuntimeError("builder validation did not pass")
    part_dir = args.builder_output / "features/embeddings/gene_genomic_sequence/gene/instadeepai__nucleotide-transformer-v2-50m-multi-species/policy_v1"
    parts = sorted(part_dir.glob("part-*.parquet"))
    if not parts:
        raise RuntimeError("builder emitted no embedding parts")

    sequence_path = args.source_root / "features/gene_genomic_sequence.parquet"
    interval_path = args.source_root / "features/gene_genomic_interval.parquet"
    sequence_table = pq.read_table(sequence_path, columns=["node_id", "feature_key"])
    interval_table = pq.read_table(interval_path, columns=["node_id"])

    args.candidate_dir.mkdir(parents=True)
    embedding_path = args.candidate_dir / "embeddings/gene_genomic_sequence_nt.parquet"
    compact = compact_embeddings(parts, embedding_path)
    embedded_ids = set(compact.pop("node_ids"))
    embedded_feature_keys = set(compact.pop("source_feature_keys"))
    source_row_indices = compact.pop("source_row_indices")
    sequence_ids = set(str(value) for value in sequence_table["node_id"].to_pylist())
    sequence_feature_keys = set(str(value) for value in sequence_table["feature_key"].to_pylist())
    interval_ids = set(str(value) for value in interval_table["node_id"].to_pylist())
    canonical_ids = read_canonical_gene_ids(args.canonical_gene)
    classification = classify_gene_denominator(
        canonical_ids=canonical_ids,
        interval_ids=interval_ids,
        sequence_ids=sequence_ids,
        embedded_ids=embedded_ids,
    )

    missing_path = args.candidate_dir / "coverage/missing_eligible_ensg.parquet"
    quarantine_path = args.candidate_dir / "coverage/quarantined_non_ensg.parquet"
    missing_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(classification["missing_rows"]), missing_path, compression="zstd")
    pq.write_table(pa.Table.from_pylist(classification["quarantine_rows"]), quarantine_path, compression="zstd")
    source_dir = args.candidate_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sequence_path, source_dir / sequence_path.name)
    shutil.copy2(interval_path, source_dir / interval_path.name)
    source_report = args.source_root / "reports/gene_genomic_sequence_feature_report.json"
    if source_report.exists():
        shutil.copy2(source_report, source_dir / source_report.name)

    eligible_ids = set(classification["eligible_ensg"])
    missing_ids = {row["node_id"] for row in classification["missing_rows"]}
    quarantine_ids = {row["node_id"] for row in classification["quarantine_rows"]}
    validation = {
        "passed": False,
        "canonical_gene_rows": len(canonical_ids),
        "eligible_ensg_rows": len(eligible_ids),
        "embedded_rows": len(embedded_ids),
        "missing_eligible_ensg_rows": len(missing_ids),
        "quarantined_non_ensg_rows": len(quarantine_ids),
        "interval_rows": len(interval_ids),
        "sequence_rows": len(sequence_ids),
        "coverage_union_exact": embedded_ids | missing_ids == eligible_ids,
        "coverage_disjoint": not (embedded_ids & missing_ids),
        "canonical_partition_exact": eligible_ids | quarantine_ids == canonical_ids,
        "source_sequence_subset_eligible": not (sequence_ids - eligible_ids),
        "embedded_matches_source_sequence": embedded_ids == sequence_ids,
        "embedded_feature_keys_match_source": embedded_feature_keys == sequence_feature_keys,
        "source_row_index_coverage_exact": source_row_indices == list(range(len(sequence_ids))),
        "embedding_antijoin_rows": len(embedded_ids - eligible_ids),
        "non_finite_vectors": compact["non_finite_vectors"],
        "all_zero_vectors": compact["all_zero_vectors"],
        "duplicate_node_ids": compact["duplicate_node_ids"],
        "duplicate_source_feature_keys": compact["duplicate_source_feature_keys"],
        "physical_embedding_type": compact["physical_embedding_type"],
        "windows": compact["windows"],
    }
    validation["passed"] = all(
        [
            validation["coverage_union_exact"],
            validation["coverage_disjoint"],
            validation["canonical_partition_exact"],
            validation["source_sequence_subset_eligible"],
            validation["embedded_matches_source_sequence"],
            validation["embedded_feature_keys_match_source"],
            validation["source_row_index_coverage_exact"],
            validation["embedding_antijoin_rows"] == 0,
            validation["non_finite_vectors"] == 0,
            validation["all_zero_vectors"] == 0,
            validation["duplicate_node_ids"] == 0,
            validation["duplicate_source_feature_keys"] == 0,
            validation["physical_embedding_type"] == expected_embedding_type(),
            validation["windows"] == len(embedded_ids),
        ]
    )
    if not validation["passed"]:
        raise RuntimeError(f"candidate validation failed: {json.dumps(validation, sort_keys=True)}")

    source_origin = args.source_origin_root.rstrip("/") + "/"
    source_objects = {
        name: gcs_description(source_origin + name)
        for name in (
            "features/gene_genomic_interval.parquet",
            "features/gene_genomic_sequence.parquet",
            "reports/gene_genomic_sequence_feature_report.json",
        )
    }
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_hashes = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in (interval_path, sequence_path, source_report)
        if path.exists()
    }
    manifest = {
        "task_id": TASK_ID,
        "created_at": created_at,
        "release_state": "immutable_staged_candidate_pending_independent_review",
        "staged_only": True,
        "canonical_promotion": False,
        "latest_pointer_advanced": False,
        "public_iam_changed": False,
        "node_type": "gene",
        "modality": "gene_genomic_sequence",
        "sequence_semantics": "gene-strand 5-prime genomic-locus sequence; full locus up to 1000 nt, otherwise first 1000 nt; not transcript/cDNA, promoter/TSS, or exon-only sequence",
        "model": {
            "id": EXPECTED_MODEL,
            "revision": EXPECTED_REVISION,
            "tokenizer_id": EXPECTED_MODEL,
            "tokenizer_revision": EXPECTED_REVISION,
            "license": MODEL_LICENSE,
            "embedding_dimension": EXPECTED_DIM,
        },
        "runtime": {
            "transformers": "4.55.4",
            "pin_reason": "Transformers 5.12.1 failed to load NT v2 checkpoint weights and produced random initialization; 4.55.4 loaded reproducibly",
            "device": "cpu",
            "batch_size": 16,
            "part_size": 4096,
        },
        "window_policy": {
            "max_nucleotides": 1000,
            "windows_per_gene": 1,
            "selection": "first 1000 nt in gene strand orientation (or full shorter locus)",
            "tokenizer_truncation": False,
            "pooling": "attention-mask mean of final hidden state followed by L2 normalization",
        },
        "leakage_policy": "No disease labels, drug-target edges, or downstream benchmark labels are inputs; only Ensembl reference genomic sequence is encoded.",
        "source": {
            "release": SOURCE_RELEASE,
            "license": SOURCE_LICENSE,
            "citation": SOURCE_CITATION,
            "origin_root": args.source_origin_root,
            "objects": source_objects,
            "local_hashes": source_hashes,
        },
        "builder": {
            "repository_commit": args.repository_commit,
            "builder_manifest_sha256": sha256(args.builder_output / "manifest.json"),
            "builder_files": {
                name: sha256(args.task_root / "repo/manage_db" / name)
                for name in (
                    "build_gene_genomic_sequence_embeddings.py",
                    "build_nucleotide_sequence_embeddings.py",
                    "resumable_embedding_parts.py",
                    "finalize_gene_genomic_embedding_candidate.py",
                )
            },
        },
        "coverage": validation,
        "compaction": compact,
        "effective_release_terms": "Derived embeddings inherit CC-BY-NC-SA-4.0 model terms and are not an unrestricted commercial artifact.",
        "gcs_candidate_root": args.gcs_root,
    }
    schema = pq.read_schema(embedding_path)
    write_json(
        args.candidate_dir / "schema.json",
        {
            "columns": [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in schema
            ],
            "embedding": {"dimension": EXPECTED_DIM, "dtype": "float32", "physical_type": str(schema.field("embedding").type)},
        },
    )
    write_json(args.candidate_dir / "validation.json", validation)
    write_json(args.candidate_dir / "manifest.json", manifest)
    (args.candidate_dir / "README.md").write_text(
        "# Human ENSG gene genomic-sequence embeddings\n\n"
        "Immutable staged candidate pending independent review. It covers the exact human ENSG denominator with one source-backed row or one explicit missing-reason row per eligible gene. "
        "Embeddings encode the gene-strand 5-prime 1,000-nt genomic-locus window with the pinned Nucleotide Transformer v2 50M checkpoint. No canonical pointer, IAM, or public release is changed.\n"
    )
    checksum_files = sorted(path for path in args.candidate_dir.rglob("*") if path.is_file())
    (args.candidate_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(args.candidate_dir).as_posix()}\n" for path in checksum_files)
    )

    local_inventory = [
        {
            "path": path.relative_to(args.candidate_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "rows": parquet_rows(path) if path.suffix == ".parquet" else None,
        }
        for path in sorted(path for path in args.candidate_dir.rglob("*") if path.is_file())
    ]
    write_json(args.candidate_dir / "object_inventory.json", local_inventory)
    objects = publish_candidate(args.candidate_dir, args.gcs_root, args.task_root / "readback")
    terminal_evidence = {
        "task_id": TASK_ID,
        "status": "success",
        "created_at": created_at,
        "hostname": platform.node(),
        "candidate_root": args.gcs_root,
        "objects": objects,
        "validation": validation,
        "local_inventory": local_inventory,
    }
    evidence_path = args.task_root / "evidence/terminal_evidence.json"
    write_json(evidence_path, terminal_evidence)
    marker_path = args.task_root / "evidence/_STAGED_CANDIDATE.json"
    write_json(
        marker_path,
        {
            "task_id": TASK_ID,
            "candidate_root": args.gcs_root,
            "release_state": "staged_candidate_pending_independent_review",
            "terminal_evidence_sha256": sha256(evidence_path),
            "validation_passed": True,
        },
    )
    marker_uri = args.gcs_root.rstrip("/") + "/_STAGED_CANDIDATE.json"
    marker_description = create_only_upload(marker_path, marker_uri)
    terminal_evidence["terminal_marker"] = {
        "uri": marker_uri,
        "description": marker_description,
        "sha256": sha256(marker_path),
    }
    write_json(evidence_path, terminal_evidence)
    print(json.dumps({"status": "success", "candidate_root": args.gcs_root, "validation": validation}, sort_keys=True))


if __name__ == "__main__":
    main()
