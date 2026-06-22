"""Stage ChEMBL source-native molecule→protein target mechanisms.

This builder starts from ChEMBL mechanism records and ChEMBL target
components. It intentionally does not consume existing molecule→gene target
edges and does not map gene endpoints to proteins. ChEMBL target component
UniProt accessions are protein-native endpoints; this pilot maps them to KG
``protein`` nodes only when the UniProt accession resolves unambiguously to a
single protein node via ``nodes/protein.parquet``.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from .backfill_edge_evidence import build_molecule_targets_protein_staged

CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
SOURCE = "ChEMBL"
SOURCE_DATASET = "mechanism"
RELATION = "molecule_targets_protein"
USER_AGENT = "hermes-agent/txgnn-chembl-molecule-targets-protein"


def _get_json(url: str, *, retries: int = 3, sleep_seconds: float = 1.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except Exception as exc:  # pragma: no cover - exercised only on network flake
            last_error = exc
            if attempt == retries:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def fetch_chembl_mechanisms(*, limit: int = 1000, max_records: int | None = None) -> list[dict[str, Any]]:
    """Fetch ChEMBL mechanism rows from the public API."""

    params = urllib.parse.urlencode({"limit": limit, "offset": 0})
    url = f"{CHEMBL_API_BASE}/mechanism.json?{params}"
    rows: list[dict[str, Any]] = []
    while url:
        data = _get_json(url)
        batch = data.get("mechanisms", [])
        rows.extend(batch)
        if max_records is not None and len(rows) >= max_records:
            return rows[:max_records]
        next_url = (data.get("page_meta") or {}).get("next")
        if next_url:
            url = urllib.parse.urljoin(CHEMBL_API_BASE + "/", next_url)
        else:
            url = ""
    return rows


def fetch_chembl_targets(target_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Fetch ChEMBL target metadata keyed by target_chembl_id."""

    out: dict[str, dict[str, Any]] = {}
    for target_id in sorted({x for x in target_ids if x}):
        out[target_id] = _get_json(f"{CHEMBL_API_BASE}/target/{target_id}.json")
    return out


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_or_fetch_sources(raw_dir: Path, *, max_records: int | None = None, refresh: bool = False) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    mechanisms_path = raw_dir / "chembl_mechanism.jsonl"
    targets_path = raw_dir / "chembl_targets.jsonl"
    if refresh or not mechanisms_path.exists():
        mechanisms = fetch_chembl_mechanisms(max_records=max_records)
        write_jsonl(mechanisms_path, mechanisms)
    else:
        mechanisms = read_jsonl(mechanisms_path)
        if max_records is not None:
            mechanisms = mechanisms[:max_records]
    target_ids = [str(row.get("target_chembl_id") or "") for row in mechanisms]
    if refresh or not targets_path.exists():
        targets = fetch_chembl_targets(target_ids)
        write_jsonl(targets_path, targets.values())
    else:
        target_rows = read_jsonl(targets_path)
        targets = {str(row.get("target_chembl_id") or ""): row for row in target_rows}
        missing = sorted({tid for tid in target_ids if tid and tid not in targets})
        if missing:
            fetched = fetch_chembl_targets(missing)
            targets.update(fetched)
            write_jsonl(targets_path, targets.values())
    return mechanisms, targets


def _pubmed_refs(refs: list[dict[str, Any]] | None) -> str:
    if not refs:
        return ""
    pmids = [str(r.get("ref_id")) for r in refs if str(r.get("ref_type") or "").lower() == "pubmed" and r.get("ref_id")]
    return ";".join(f"PMID:{p}" for p in pmids)


def _source_record_id(row: dict[str, Any], target: dict[str, Any], accession: str) -> str:
    mec_id = row.get("mec_id") or row.get("record_id") or "unknown"
    return f"ChEMBL:mechanism:{RELATION}:mec_id={mec_id}:target={target.get('target_chembl_id')}:uniprot={accession}"


def build_source_rows(
    mechanisms: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    protein_nodes: pd.DataFrame,
    molecule_nodes: pd.DataFrame,
    *,
    release: str,
    require_unambiguous_uniprot: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Transform ChEMBL mechanisms into strict molecule_targets_protein rows."""

    molecule_ids = set(molecule_nodes["id"].dropna().astype(str))
    protein_map = (
        protein_nodes[["id", "uniprot_id"]]
        .dropna(subset=["id", "uniprot_id"])
        .assign(id=lambda d: d["id"].astype(str), uniprot_id=lambda d: d["uniprot_id"].astype(str))
    )
    grouped = protein_map.groupby("uniprot_id")["id"].agg(lambda s: sorted(set(s))).to_dict()

    rows: list[dict[str, Any]] = []
    rejected: dict[str, int] = {
        "missing_molecule_node": 0,
        "missing_target": 0,
        "non_human_target": 0,
        "no_protein_component": 0,
        "uniprot_not_in_protein_nodes": 0,
        "ambiguous_uniprot_to_protein_nodes": 0,
    }
    target_type_counts: dict[str, int] = {}
    accessions_seen: set[str] = set()
    accessions_staged: set[str] = set()

    for mech in mechanisms:
        molecule_id = str(mech.get("molecule_chembl_id") or mech.get("parent_molecule_chembl_id") or "")
        if molecule_id not in molecule_ids:
            rejected["missing_molecule_node"] += 1
            continue
        target_id = str(mech.get("target_chembl_id") or "")
        target = targets.get(target_id)
        if not target:
            rejected["missing_target"] += 1
            continue
        if target.get("organism") != "Homo sapiens":
            rejected["non_human_target"] += 1
            continue
        target_type = str(target.get("target_type") or "")
        target_type_counts[target_type] = target_type_counts.get(target_type, 0) + 1
        components = [
            c for c in target.get("target_components") or []
            if str(c.get("component_type") or "").upper() == "PROTEIN" and c.get("accession")
        ]
        if not components:
            rejected["no_protein_component"] += 1
            continue
        for component in components:
            accession = str(component.get("accession") or "")
            accessions_seen.add(accession)
            protein_ids = grouped.get(accession, [])
            if not protein_ids:
                rejected["uniprot_not_in_protein_nodes"] += 1
                continue
            if require_unambiguous_uniprot and len(protein_ids) != 1:
                rejected["ambiguous_uniprot_to_protein_nodes"] += 1
                continue
            for protein_id in protein_ids:
                accessions_staged.add(accession)
                target_confidence = {
                    "direct_interaction": mech.get("direct_interaction"),
                    "molecular_mechanism": mech.get("molecular_mechanism"),
                    "disease_efficacy": mech.get("disease_efficacy"),
                    "max_phase": mech.get("max_phase"),
                }
                rows.append(
                    {
                        "x_id": molecule_id,
                        "x_type": "molecule",
                        "y_id": protein_id,
                        "y_type": "protein",
                        "source": SOURCE,
                        "source_dataset": SOURCE_DATASET,
                        "source_record_id": _source_record_id(mech, target, accession),
                        "action_type": mech.get("action_type") or "protein_target",
                        "predicate": mech.get("action_type") or "protein_target",
                        "mechanism": mech.get("mechanism_of_action") or target.get("pref_name") or "targets protein",
                        "display_relation": mech.get("mechanism_of_action") or mech.get("action_type") or "targets protein",
                        "target_class": target_type,
                        "score": mech.get("direct_interaction"),
                        "study_id": str(mech.get("record_id") or ""),
                        "paper_id": _pubmed_refs(mech.get("mechanism_refs")),
                        "release": release,
                        "target_chembl_id": target_id,
                        "target_uniprot_id": accession,
                        "target_component_id": component.get("component_id"),
                        "target_component_relationship": component.get("relationship"),
                        "target_component_description": component.get("component_description"),
                        "mechanism_comment": mech.get("mechanism_comment"),
                        "binding_site_comment": mech.get("binding_site_comment"),
                        "selectivity_comment": mech.get("selectivity_comment"),
                        "target_confidence": json.dumps(target_confidence, sort_keys=True, separators=(",", ":")),
                    }
                )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["x_id", "y_id", "source_record_id"]).reset_index(drop=True)
    report = {
        "source": SOURCE,
        "source_dataset": SOURCE_DATASET,
        "release": release,
        "input_mechanism_rows": len(mechanisms),
        "input_target_rows": len(targets),
        "staged_source_rows": int(len(df)),
        "distinct_molecules": int(df["x_id"].nunique()) if not df.empty else 0,
        "distinct_protein_nodes": int(df["y_id"].nunique()) if not df.empty else 0,
        "distinct_uniprot_seen": len(accessions_seen),
        "distinct_uniprot_staged": len(accessions_staged),
        "rejected": rejected,
        "target_type_counts_seen": target_type_counts,
        "endpoint_policy": "ChEMBL target_component UniProt protein endpoint mapped to KG protein node through nodes/protein.uniprot_id; no gene target rows consumed; ambiguous UniProt-to-multiple-protein-node mappings rejected by default.",
    }
    return df, report


def stage_chembl_molecule_targets_protein(
    *,
    kg_path: Path,
    raw_dir: Path,
    staging_root: Path,
    release: str,
    max_records: int | None = None,
    refresh: bool = False,
    allow_ambiguous_uniprot: bool = False,
) -> dict[str, Any]:
    mechanisms, targets = load_or_fetch_sources(raw_dir, max_records=max_records, refresh=refresh)
    protein_nodes = pd.read_parquet(kg_path / "nodes" / "protein.parquet")
    molecule_nodes = pd.read_parquet(kg_path / "nodes" / "molecule.parquet")
    source_rows, report = build_source_rows(
        mechanisms,
        targets,
        protein_nodes,
        molecule_nodes,
        release=release,
        require_unambiguous_uniprot=not allow_ambiguous_uniprot,
    )
    staging_root.mkdir(parents=True, exist_ok=True)
    source_rows_path = staging_root / "source_rows" / f"{RELATION}.parquet"
    source_rows_path.parent.mkdir(parents=True, exist_ok=True)
    source_rows.to_parquet(source_rows_path, index=False)
    counts = build_molecule_targets_protein_staged(staging_root, source_rows)
    report.update(
        {
            "kg_path": str(kg_path),
            "staging_root": str(staging_root),
            "source_rows_path": str(source_rows_path),
            "edges_path": str(staging_root / "edges" / f"{RELATION}.parquet"),
            "evidence_path": str(staging_root / "evidence" / f"{RELATION}.parquet"),
            "write_counts": counts,
        }
    )
    reports_dir = staging_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "build_summary.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-path", type=Path, required=True, help="KG root containing nodes/protein.parquet and nodes/molecule.parquet")
    parser.add_argument("--raw-dir", type=Path, default=Path(".omoc/raw/chembl/molecule_targets_protein"))
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--release", default="ChEMBL API 2026-06-22")
    parser.add_argument("--max-records", type=int, default=None, help="Optional bounded smoke limit")
    parser.add_argument("--refresh", action="store_true", help="Refetch ChEMBL API caches")
    parser.add_argument("--allow-ambiguous-uniprot", action="store_true", help="Expand UniProt accessions mapping to multiple KG protein nodes")
    args = parser.parse_args()
    report = stage_chembl_molecule_targets_protein(
        kg_path=args.kg_path,
        raw_dir=args.raw_dir,
        staging_root=args.staging_root,
        release=args.release,
        max_records=args.max_records,
        refresh=args.refresh,
        allow_ambiguous_uniprot=args.allow_ambiguous_uniprot,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
