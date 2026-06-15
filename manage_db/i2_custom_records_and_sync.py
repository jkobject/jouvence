#!/usr/bin/env python
"""I2 — custom records + TxGNN node sync orchestrator."""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

import bionty as bt
import lamindb as ln
import pandas as pd
import pertdb as pt
from django.core.exceptions import ObjectDoesNotExist

try:
    from django.db.utils import OperationalError as DjangoOperationalError
except Exception:  # pragma: no cover - django should be available in runtime
    DjangoOperationalError = Exception  # type: ignore[assignment]

from .sync_nodes_to_lamindb import sync_txgnn_nodes_to_lamin_entities


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent
_PATCHED_FROM_SOURCE = False

_DB_LOCK_KEYWORD = "database is locked"
_DB_LOCK_ERRORS: tuple[type[BaseException], ...] = (sqlite3.OperationalError, DjangoOperationalError)


def _is_db_locked_error(exc: BaseException) -> bool:
    return _DB_LOCK_KEYWORD in str(exc).lower()


def _retry_db_locked(label: str, func, retries: int = 3, delay: float = 5.0, max_delay: float = 60.0):
    wait = delay
    for attempt in range(1, retries + 1):
        try:
            return func()
        except _DB_LOCK_ERRORS as exc:
            if _is_db_locked_error(exc) and attempt < retries:
                logger.warning(
                    "    %s: database locked, retrying in %.1f s (attempt %d/%d)",
                    label,
                    wait,
                    attempt,
                    retries,
                )
                time.sleep(wait)
                wait = min(wait * 2, max_delay)
                continue
            raise


def configure_sqlite_busy_timeout(timeout_ms: int = 600_000) -> None:
    try:
        from django.db import connection
    except Exception as exc:  # pragma: no cover - django should exist in runtime
        logger.warning("    unable to import django.db connection: %s", exc)
        return

    try:
        if connection.vendor != "sqlite":
            return
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA busy_timeout = {int(timeout_ms)}")
        logger.info("    set sqlite busy_timeout=%d ms", timeout_ms)
    except Exception as exc:
        logger.warning("    failed to set sqlite busy_timeout: %s", exc)


def _ensure_safe_from_source() -> None:
    global _PATCHED_FROM_SOURCE
    if _PATCHED_FROM_SOURCE:
        return

    registries = [bt.Gene, bt.Tissue, bt.Disease, bt.Phenotype, bt.Pathway]

    for registry in registries:
        original = registry.from_source.__func__  # type: ignore[attr-defined]

        @classmethod
        def safe_from_source(cls, *args, __orig=original, **kwargs):
            try:
                return __orig(cls, *args, **kwargs)
            except ObjectDoesNotExist:
                return None

        registry.from_source = safe_from_source  # type: ignore[assignment]

    _PATCHED_FROM_SOURCE = True


def ensure_instance() -> str:
    slug = getattr(ln.setup.settings.instance, "slug", None)
    if not slug:
        raise RuntimeError("No LaminDB instance connected. Run ln.connect() first.")
    logger.info("Connected LaminDB instance: %s", slug)
    return slug


def step0_ensure_nodes_tab(data_dir: Path) -> Path:
    logger.info("Step 0 — ensure nodes.tab is available")
    txdata_dir = Path(data_dir) / "txdata"
    txdata_dir.mkdir(parents=True, exist_ok=True)
    nodes_tab = txdata_dir / "nodes.tab"
    node_csv = txdata_dir / "node.csv"
    if nodes_tab.exists():
        logger.info("    Found existing nodes.tab at %s", nodes_tab)
        return nodes_tab
    if node_csv.exists():
        df = _read_node_csv(node_csv)
        df.to_csv(nodes_tab, sep="\t", index=False)
        logger.info("    Converted node.csv → nodes.tab with %s rows", len(df))
        return nodes_tab
    logger.info("    Downloading TxGNN CSVs via download_txdata_csvs()")
    from txdata_download import download_txdata_csvs

    download_txdata_csvs(txdata_dir)
    if not node_csv.exists():
        raise FileNotFoundError("node.csv not found after download")
    df = _read_node_csv(node_csv)
    df.to_csv(nodes_tab, sep="\t", index=False)
    logger.info("    Downloaded and converted node.csv → nodes.tab with %s rows", len(df))
    return nodes_tab


def _read_node_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except pd.errors.ParserError:
        return pd.read_csv(path, sep="\t")


def step1_install_lnschema_txgnn_editable() -> str:
    if importlib.util.find_spec("lnschema_txgnn") is not None:
        logger.info("Step 1 — lnschema_txgnn already installed")
        return "already present"
    logger.info("Step 1 — installing lnschema_txgnn editable package")
    cmd = [
        "uv",
        "pip",
        "install",
        "-e",
        str(ROOT / "manage_db" / "lnschema_txgnn"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.stdout:
        logger.info(result.stdout.strip())
    if result.stderr:
        logger.warning(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"uv pip install failed with code {result.returncode}")
    importlib.invalidate_caches()
    importlib.import_module("lnschema_txgnn")

    logger.info("    Installed lnschema_txgnn editable package")
    return "installed"


def step2_apply_migrations(retries: int = 3, delay: float = 5.0) -> dict[str, Any]:
    logger.info("Step 2 — applying LaminDB migrations")
    cmd = ["lamin", "migrate", "deploy"]
    last_stdout = ""
    last_stderr = ""
    for attempt in range(1, retries + 1):
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            logger.info(stdout)
        if stderr:
            logger.warning(stderr)
        last_stdout = stdout
        last_stderr = stderr
        if result.returncode == 0:
            applied = re.findall(r"Applying\s+([^\s]+)", stdout)
            return {
                "exit_code": result.returncode,
                "applied_migrations": applied,
            }
        is_locked = "database is locked" in (stdout.lower() + stderr.lower())
        if is_locked and attempt < retries:
            logger.warning("    database locked, retrying in %.1f s (attempt %d/%d)", delay, attempt, retries)
            time.sleep(delay)
            delay *= 2
            continue
        raise RuntimeError(f"lamin migrate deploy failed with code {result.returncode}")
    raise RuntimeError(f"lamin migrate deploy failed: {last_stderr or last_stdout}")


def _custom_registries() -> list[tuple[str, Any]]:
    import lnschema_txgnn as lnt

    return [
        ("lnschema_txgnn.Gene", lnt.Gene),
        ("lnschema_txgnn.Molecule", lnt.Molecule),
        ("lnschema_txgnn.Pathway", lnt.Pathway),
        ("lnschema_txgnn.Tissue", lnt.Tissue),
        ("lnschema_txgnn.CellType", lnt.CellType),
        ("lnschema_txgnn.Paper", lnt.Paper),
        ("lnschema_txgnn.Transcript", lnt.Transcript),
        ("lnschema_txgnn.Disease", lnt.Disease),
        ("lnschema_txgnn.Enhancer", lnt.Enhancer),
        ("lnschema_txgnn.Dataset", lnt.Dataset),
        ("lnschema_txgnn.Mutation", lnt.Mutation),
    ]


def step3_audit_custom_records() -> dict[str, int | None]:
    logger.info("Step 3 — audit lnschema_txgnn registries")
    counts: dict[str, int | None] = {}
    for label, registry in _custom_registries():
        try:
            value = _retry_db_locked(label, registry.objects.count)
            logger.info("    %s: %s", label, value)
        except Exception as exc:
            logger.warning("    %s: error %s", label, exc)
            value = None
        counts[label] = value
    return counts


def _summarize_mapping(df: pd.DataFrame) -> dict[str, Any]:
    total = int(len(df))
    status_counts = {k: int(v) for k, v in df["status"].value_counts().sort_index().items()}
    pivot = (
        df.pivot_table(index="node_type", columns="status", values="node_index", aggfunc="size", fill_value=0)
        .sort_index()
    )
    node_types = {
        node_type: {status: int(pivot.loc[node_type, status]) for status in pivot.columns}
        for node_type in pivot.index
    }
    logger.info("    total nodes: %s", total)
    for status, value in status_counts.items():
        logger.info("        %s: %s", status, value)
    return {
        "total": total,
        "status_counts": status_counts,
        "per_node_type": node_types,
    }


def step4_sync_nodes_dry_run(nodes_path: Path) -> dict[str, Any]:
    logger.info("Step 4 — dry-run node sync")
    _ensure_safe_from_source()
    df = sync_txgnn_nodes_to_lamin_entities(
        nodes_path=nodes_path,
        mapping_output_path=None,
        dry_run=True,
    )
    dry_run_path = nodes_path.parent / "node_entity_mapping.dry_run.csv"
    df.to_csv(dry_run_path, index=False)
    summary = _summarize_mapping(df)
    summary["mapping_output_path"] = str(dry_run_path)
    return summary


def step5_sync_nodes_real(nodes_path: Path, mapping_output_path: Path) -> dict[str, Any]:
    logger.info("Step 5 — full node sync")
    _ensure_safe_from_source()
    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)
    configure_sqlite_busy_timeout()
    df = _retry_db_locked(
        "step5_sync_nodes_real",
        lambda: sync_txgnn_nodes_to_lamin_entities(
            nodes_path=nodes_path,
            mapping_output_path=mapping_output_path,
            dry_run=False,
        ),
        retries=8,
        delay=15.0,
        max_delay=120.0,
    )
    summary = _summarize_mapping(df)
    summary["mapping_output_path"] = str(mapping_output_path)
    return summary


def step6_final_audit() -> dict[str, int | None]:
    logger.info("Step 6 — final registry audit")
    registries: list[tuple[str, Any]] = [
        ("bionty.Gene", bt.Gene),
        ("bionty.Tissue", bt.Tissue),
        ("bionty.Disease", bt.Disease),
        ("bionty.Phenotype", bt.Phenotype),
        ("bionty.Pathway", bt.Pathway),
        ("pertdb.Compound", pt.Compound),
        ("pertdb.EnvironmentalPerturbation", pt.EnvironmentalPerturbation),
    ]
    registries.extend(_custom_registries())
    counts: dict[str, int | None] = {}
    for label, registry in registries:
        try:
            value = _retry_db_locked(label, registry.objects.count)
        except Exception as exc:
            logger.warning("    %s: error %s", label, exc)
            value = None
        counts[label] = value
    return counts


def main(*, dry_run: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    data_root = Path(data_dir or ROOT / "data").resolve()
    txdata_dir = data_root / "txdata"
    pre_nodes_tab = (txdata_dir / "nodes.tab").exists()
    pre_node_csv = (txdata_dir / "node.csv").exists()
    nodes_path = step0_ensure_nodes_tab(data_root)
    if pre_nodes_tab:
        step0_status = "already present"
    elif pre_node_csv:
        step0_status = "created from node.csv"
    else:
        step0_status = "downloaded"
    step1_status = step1_install_lnschema_txgnn_editable()
    migrations = step2_apply_migrations()
    instance_slug = ensure_instance()
    configure_sqlite_busy_timeout()
    audit_before = step3_audit_custom_records()
    dry_run_summary = step4_sync_nodes_dry_run(nodes_path)
    real_summary: dict[str, Any] | None = None
    if not dry_run:
        mapping_output_path = txdata_dir / "node_entity_mapping.csv"
        real_summary = step5_sync_nodes_real(nodes_path, mapping_output_path)
    final_audit = step6_final_audit()
    return {
        "instance": instance_slug,
        "step0": {
            "status": step0_status,
            "nodes_path": str(nodes_path),
        },
        "step1": step1_status,
        "step2": migrations,
        "step3": audit_before,
        "step4": dry_run_summary,
        "step5": real_summary,
        "step6": final_audit,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--data-dir", default="./data")
    args = parser.parse_args()
    results = main(dry_run=args.dry_run, data_dir=Path(args.data_dir))
    if args.json:
        print(json.dumps(results, indent=2, default=str))
