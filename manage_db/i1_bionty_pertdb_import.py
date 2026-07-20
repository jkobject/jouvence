#!/usr/bin/env python
"""I1 — bionty & pertdb import into jkobject/jouvencekb lamindb instance.

Reproduces reproduce/01_lamindb_instance_setup.ipynb end-to-end as a re-runnable
script. Idempotent: re-running skips already-imported records (use
ignore_conflicts=True).
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable

import bionty as bt
import lamindb as ln
import pandas as pd
import pertdb as pt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


REGISTRIES_AUDIT: list[tuple[str, Any]] = [
    ("bt.Organism", bt.Organism),
    ("bt.CellType", bt.CellType),
    ("bt.Disease", bt.Disease),
    ("bt.Tissue", bt.Tissue),
    ("bt.Phenotype", bt.Phenotype),
    ("bt.Pathway", bt.Pathway),
    ("bt.Gene", bt.Gene),
    ("bt.ExperimentalFactor", bt.ExperimentalFactor),
    ("bt.CellLine", bt.CellLine),
    ("pt.Compound", pt.Compound),
    ("pt.GeneticPerturbation", pt.GeneticPerturbation),
    ("pt.EnvironmentalPerturbation", pt.EnvironmentalPerturbation),
]

PUBLIC_PROBES: list[tuple[str, Any, str | None, str]] = [
    ("bt.CellType", bt.CellType, None, "cl"),
    ("bt.Disease", bt.Disease, None, "mondo"),
    ("bt.Tissue", bt.Tissue, None, "uberon"),
    ("bt.Phenotype (HP)", bt.Phenotype, "human", "hp"),
    ("bt.Pathway", bt.Pathway, None, "go"),
    ("bt.Gene (human)", bt.Gene, "human", "ensembl"),
    ("bt.ExperimentalFactor", bt.ExperimentalFactor, None, "efo"),
    ("bt.CellLine", bt.CellLine, None, "cellosaurus"),
]

BIONTY_IMPORT_TARGETS: list[tuple[str, Any, str | None, str]] = [
    ("bionty.CellType", bt.CellType, None, "bt.CellType"),
    ("bionty.Disease", bt.Disease, None, "bt.Disease"),
    ("bionty.Tissue", bt.Tissue, None, "bt.Tissue"),
    ("bionty.Phenotype", bt.Phenotype, None, "bt.Phenotype (HP)"),
    ("bionty.Pathway", bt.Pathway, None, "bt.Pathway"),
    ("bionty.Gene", bt.Gene, "human", "bt.Gene (human)"),
    ("bionty.ExperimentalFactor", bt.ExperimentalFactor, None, "bt.ExperimentalFactor"),
    ("bionty.CellLine", bt.CellLine, None, "bt.CellLine"),
]

COMPOUND_FIELDS: tuple[str, ...] = (
    "uid",
    "name",
    "ontology_id",
    "abbr",
    "synonyms",
    "description",
    "type",
    "chembl_id",
    "smiles",
    "canonical_smiles",
    "inchikey",
    "molweight",
    "molformula",
    "moa",
)

FETCH_CHUNK = 2000
SAVE_CHUNK = 500


def _entity_string(registry: Any) -> str:
    return f"{registry.__module__.split('.')[0]}.{registry.__name__}"


def ensure_instance() -> str:
    slug = getattr(ln.setup.settings.instance, "slug", None)
    if not slug:
        raise RuntimeError("No LaminDB instance connected. Run ln.connect() first.")
    logger.info("Connected LaminDB instance: %s", slug)
    return slug


def _format_count(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}"


def _collect_counts() -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for label, registry in REGISTRIES_AUDIT:
        try:
            count = registry.objects.count()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to count %s: %s", label, exc)
            count = None
        counts[label] = count
    return counts


def step1_audit() -> dict[str, int | None]:
    logger.info("Step 1 — initial audit")
    counts = _collect_counts()
    for label, count in counts.items():
        logger.info("    %s: %s", label, _format_count(count))
    return counts


def step2_inventory_sources() -> pd.DataFrame:
    logger.info("Step 2 — inventory bionty sources")
    df = pd.DataFrame(
        bt.Source.objects.values(
            "entity",
            "name",
            "version",
            "organism",
            "currently_used",
            "in_db",
        )
    ).sort_values(["entity", "currently_used"], ascending=[True, False])
    logger.info("    Sources dataframe shape: %s", df.shape)
    return df


def step3_probe_public_sizes() -> pd.DataFrame:
    logger.info("Step 3 — probe public source sizes")
    rows: list[dict[str, Any]] = []
    for label, registry, organism, source_name in PUBLIC_PROBES:
        entity = _entity_string(registry)
        source = bt.Source.objects.filter(entity=entity, name=source_name).first()
        if source is None:
            logger.warning("    %s: source '%s' not found", label, source_name)
            rows.append({"registry": label, "source": source_name, "public_records": None})
            continue
        try:
            kwargs = {"source": source}
            if organism:
                kwargs["organism"] = organism
            public_df = registry.public(**kwargs)
            count = len(public_df.to_dataframe())
            rows.append({"registry": label, "source": source_name, "public_records": count})
            logger.info("    %s: %s records", label, _format_count(count))
        except Exception as exc:  # noqa: BLE001
            logger.exception("    %s: error probing public source", label)
            rows.append({"registry": label, "source": source_name, "public_records": f"ERROR: {exc}"})
    return pd.DataFrame(rows)


def step4_import_bionty(public_counts: dict[str, int | None], *, ignore_conflicts: bool = True, dry_run: bool = False) -> dict[str, dict[str, int]]:
    logger.info("Step 4 — import bionty ontologies")
    results: dict[str, dict[str, int]] = {}
    for entity_name, registry, organism, probe_key in BIONTY_IMPORT_TARGETS:
        before = registry.objects.count()
        expected = public_counts.get(probe_key)
        if isinstance(expected, int) and abs(before - expected) <= 100:
            logger.info("    %s: skipped (already populated) — %s vs expected %s", entity_name, _format_count(before), _format_count(expected))
            results[entity_name] = {"before": before, "after": before, "created": 0}
            continue
        source = bt.Source.objects.filter(entity=entity_name, currently_used=True).first()
        if source is None:
            logger.warning("    %s: no currently_used source found, skipping", entity_name)
            results[entity_name] = {"before": before, "after": before, "created": 0}
            continue
        if dry_run:
            logger.info("    %s: dry-run, would import from %s", entity_name, source.name)
            results[entity_name] = {"before": before, "after": before, "created": 0}
            continue
        kwargs: dict[str, Any] = {"source": source, "ignore_conflicts": ignore_conflicts}
        if organism:
            kwargs["organism"] = organism
        logger.info("    %s: importing from source=%s", entity_name, source.name)
        registry.import_source(**kwargs)
        after = registry.objects.count()
        results[entity_name] = {"before": before, "after": after, "created": after - before}
        logger.info("    %s: %s → %s (+%s)", entity_name, _format_count(before), _format_count(after), _format_count(after - before))
    return results


def step5_swap_phenotype_to_hp(*, dry_run: bool = False) -> int | None:
    logger.info("Step 5 — switch Phenotype source to HP")
    pato_src = bt.Source.objects.filter(entity="bionty.Phenotype", name="pato").first()
    hp_src = bt.Source.objects.filter(entity="bionty.Phenotype", name="hp", organism="human").first()
    if hp_src is None:
        logger.error("    HP source not found; ensure register_ontology_sources() has been run")
        return None
    if dry_run:
        logger.info("    dry-run — would disable PATO and enable HP")
        return bt.Phenotype.objects.count()

    updated = False
    if pato_src and pato_src.currently_used:
        pato_src.currently_used = False
        pato_src.save()
        updated = True
        logger.info("    Disabled PATO source (uid=%s)", pato_src.uid)
    if not hp_src.currently_used:
        hp_src.currently_used = True
        hp_src.save()
        updated = True
        logger.info("    Enabled HP source (uid=%s)", hp_src.uid)

    if not updated:
        logger.info("    Sources already configured for HP")

    bt.Phenotype.import_source(source=hp_src, organism="human", ignore_conflicts=True)
    count = bt.Phenotype.objects.count()
    logger.info("    HP Phenotype count: %s", _format_count(count))
    return count


def step6_transfer_pertdb_compounds(*, dry_run: bool = False) -> dict[str, int]:
    logger.info("Step 6 — transfer pertdb.Compounds from laminlabs/pertdata")
    remote_db = ln.DB("laminlabs/pertdata")
    remote_total = remote_db.pertdb.Compound.filter().count()
    local_before = pt.Compound.objects.count()
    logger.info("    Remote compounds: %s", _format_count(remote_total))
    logger.info("    Local compounds before: %s", _format_count(local_before))

    if dry_run:
        logger.info("    dry-run — skipping fetch and bulk_create")
        return {
            "remote_total": remote_total,
            "local_before": local_before,
            "local_after": local_before,
            "created": 0,
            "skipped": 0,
        }

    all_compound_dicts: list[dict[str, Any]] = []
    for start in range(0, remote_total, FETCH_CHUNK):
        batch = list(
            remote_db.pertdb.Compound.filter().all()[start : start + FETCH_CHUNK].values(*COMPOUND_FIELDS)
        )
        all_compound_dicts.extend(batch)
        logger.info("    Fetched %s/%s", _format_count(len(all_compound_dicts)), _format_count(remote_total))

    existing_uids = set(pt.Compound.objects.values_list("uid", flat=True))
    buffer: list[pt.Compound] = []
    created_total = 0
    skipped_total = 0

    for record in all_compound_dicts:
        if record["uid"] in existing_uids:
            skipped_total += 1
            continue
        kwargs = {field: record[field] for field in COMPOUND_FIELDS if record.get(field) is not None}
        buffer.append(pt.Compound(**kwargs))
        if len(buffer) >= SAVE_CHUNK:
            pt.Compound.objects.bulk_create(buffer, ignore_conflicts=True)
            created_total += len(buffer)
            buffer.clear()

    if buffer:
        pt.Compound.objects.bulk_create(buffer, ignore_conflicts=True)
        created_total += len(buffer)

    local_after = pt.Compound.objects.count()
    logger.info(
        "    Compounds: %s → %s (+%s)",
        _format_count(local_before),
        _format_count(local_after),
        _format_count(local_after - local_before),
    )
    logger.info("    Created: %s | Skipped: %s", _format_count(created_total), _format_count(skipped_total))
    return {
        "remote_total": remote_total,
        "local_before": local_before,
        "local_after": local_after,
        "created": created_total,
        "skipped": skipped_total,
    }


def step7_final_counts() -> dict[str, int | None]:
    logger.info("Step 7 — final audit")
    counts = _collect_counts()
    for label, count in counts.items():
        logger.info("    %s: %s", label, _format_count(count))
    return counts


def step8_validate_hp_for_txgnn(nodes_path: str | Path = "../data/txdata/nodes.tab") -> pd.DataFrame:
    """Validate TxGNN phenotype nodes use HPO IDs.

    # I1-SKIPPED: data/txdata/nodes.tab not yet downloaded, will run in I2
    """
    path = Path(nodes_path)
    if not path.exists():
        raise FileNotFoundError(f"nodes file not found: {path}")
    nodes = pd.read_csv(path, sep="\t")
    pheno = nodes[nodes["node_type"] == "effect/phenotype"]
    pheno = pheno.assign(
        hp_id=pheno["node_id"].apply(lambda v: f"HP:{int(float(v)):07d}" if pd.notna(v) else None)
    )
    return pheno


def main(*, dry_run: bool = False) -> dict[str, int | None]:
    ensure_instance()
    initial_counts = step1_audit()
    sources_df = step2_inventory_sources()
    probes_df = step3_probe_public_sizes()
    public_counts: dict[str, int | None] = {}
    for _, row in probes_df.iterrows():
        public_counts[row["registry"]] = (
            row["public_records"] if isinstance(row["public_records"], (int, float)) else None
        )
    step4_import_bionty(public_counts, dry_run=dry_run)
    step5_swap_phenotype_to_hp(dry_run=dry_run)
    step6_transfer_pertdb_compounds(dry_run=dry_run)
    final_counts = step7_final_counts()

    # include summary metadata for logging purposes
    summary = {
        "initial_counts": initial_counts,
        "final_counts": final_counts,
        "sources_rows": len(sources_df),
        "probes": public_counts,
    }
    logger.info("Summary: %s", json.dumps(summary, default=str))
    return {k: v for k, v in final_counts.items() if v is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit results as JSON to stdout")
    args = parser.parse_args()
    results = main(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(results, indent=2, default=str))
