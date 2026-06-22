"""Stage textual-summary feature tables for KG nodes.

The module writes only ``features/*_textual_summary.parquet`` plus reports.  It
never creates KG biological edges.  Source decisions are intentionally
conservative and are reported in ``reports/textual_summary_source_audit.csv``.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq

from .kg_schema import NodeType
from .kg_storage import open_kg_root
from .kg_textual_summary_features import (
    SOURCE_POLICY,
    allowed_textual_summary_tables,
    source_policy_audit,
    validate_textual_summaries,
    write_textual_summaries,
)

TEXT_SOURCE_DEFAULTS: dict[str, dict[str, str]] = {
    "gene": {
        "feature_table": "gene_textual_summary",
        "node_type": NodeType.GENE.value,
        "summary_kind": "gene_description",
        "source": "OpenTargets",
        "source_dataset": "target node descriptions / upstream Ensembl-NCBI-HGNC labels",
        "license": SOURCE_POLICY["OpenTargets"]["license"],
        "citation": "Open Targets Platform target metadata; preserve upstream source attribution where available.",
    },
    "disease": {
        "feature_table": "disease_textual_summary",
        "node_type": NodeType.DISEASE.value,
        "summary_kind": "disease_definition",
        "source": "OpenTargets",
        "source_dataset": "disease node descriptions / upstream EFO-MONDO-ontology labels",
        "license": SOURCE_POLICY["OpenTargets"]["license"],
        "citation": "Open Targets Platform disease metadata with upstream EFO/MONDO ontology attribution.",
    },
    "molecule": {
        "feature_table": "molecule_textual_summary",
        "node_type": NodeType.MOLECULE.value,
        "summary_kind": "drug_summary",
        "source": "ChEMBL",
        "source_dataset": "OpenTargets drug molecule metadata derived from ChEMBL fields",
        "license": SOURCE_POLICY["ChEMBL"]["license"],
        "citation": "ChEMBL / Open Targets drug molecule metadata.",
    },
}

OBO_SOURCE_DEFAULTS: dict[str, dict[str, str]] = {
    "tissue": {
        "feature_table": "tissue_textual_summary",
        "node_type": NodeType.TISSUE.value,
        "summary_kind": "anatomy_definition",
        "source": "UBERON",
        "source_dataset": "uberon-basic.obo def fields",
        "license": SOURCE_POLICY["UBERON"]["license"],
        "citation": "UBERON anatomy ontology / OBO Foundry.",
    },
    "pathway_go": {
        "feature_table": "pathway_textual_summary",
        "node_type": NodeType.PATHWAY.value,
        "summary_kind": "go_term_definition",
        "source": "GO",
        "source_dataset": "go-basic.obo def fields",
        "license": SOURCE_POLICY["GO"]["license"],
        "citation": "Gene Ontology Consortium.",
    },
}

GO_BASIC_URL = "https://purl.obolibrary.org/obo/go/go-basic.obo"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_node_table(node_root: Path, node_type: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = node_root / f"{node_type}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing node table: {path}")
    available = pq.ParquetFile(path).schema_arrow.names
    if columns is not None:
        columns = [col for col in columns if col in available]
    return pq.read_table(path, columns=columns).to_pandas()


def _endpoint_ids(node_root: Path, node_type: str) -> set[str]:
    df = _read_node_table(node_root, node_type, ["id"])
    return set(df["id"].fillna("").astype(str))


def rows_from_node_descriptions(
    node_root: Path,
    node_type: str,
    *,
    release: str,
    created_at: str,
    max_rows: int | None = None,
) -> pd.DataFrame:
    defaults = TEXT_SOURCE_DEFAULTS[node_type]
    df = _read_node_table(node_root, node_type, ["id", "description", "source", "name"])
    if "description" not in df.columns:
        return pd.DataFrame(columns=["feature_table"])
    description = df["description"].fillna("").astype(str).str.strip()
    filtered = df.loc[description.str.len().gt(0)].copy()
    if max_rows is not None:
        filtered = filtered.head(max_rows)
    source_tags = filtered.get("source", pd.Series([""] * len(filtered), index=filtered.index)).fillna("").astype(str)
    rows = pd.DataFrame(
        {
            "feature_table": defaults["feature_table"],
            "node_id": filtered["id"].astype(str),
            "node_type": defaults["node_type"],
            "summary_kind": defaults["summary_kind"],
            "summary_text": filtered["description"].fillna("").astype(str).str.strip(),
            "source": defaults["source"],
            "source_dataset": defaults["source_dataset"],
            "source_record_id": filtered["id"].astype(str),
            "provenance": "node.source=" + source_tags + "; node.description column",
            "license": defaults["license"],
            "citation": defaults["citation"],
            "release": release,
            "created_at": created_at,
        }
    )
    return rows


def parse_obo_definitions(path: Path) -> dict[str, dict[str, str]]:
    terms: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    in_term = False

    def flush() -> None:
        if current.get("id") and current.get("def") and current.get("is_obsolete") != "true":
            terms[current["id"]] = dict(current)

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line == "[Term]":
                if in_term:
                    flush()
                current = {}
                in_term = True
                continue
            if line.startswith("["):
                if in_term:
                    flush()
                current = {}
                in_term = False
                continue
            if not in_term or ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key in {"id", "name", "is_obsolete"}:
                current[key] = value
            elif key == "def":
                match = re.match(r'"(.*)"(?: \[.*\])?$', value)
                current["def"] = match.group(1) if match else value
        if in_term:
            flush()
    return terms


def rows_from_obo_definitions(
    node_root: Path,
    node_type: str,
    obo_path: Path,
    *,
    release: str,
    created_at: str,
    source_key: str,
    id_column: str = "id",
    max_rows: int | None = None,
) -> pd.DataFrame:
    defaults = OBO_SOURCE_DEFAULTS[source_key]
    node_cols = ["id", id_column, "name"] if id_column != "id" else ["id", "name"]
    nodes = _read_node_table(node_root, node_type, node_cols)
    terms = parse_obo_definitions(obo_path)
    node_term_ids = nodes[id_column].fillna("").astype(str) if id_column in nodes.columns else nodes["id"].astype(str)
    rows: list[dict[str, str]] = []
    for idx, term_id in node_term_ids.items():
        term = terms.get(term_id)
        if not term:
            continue
        rows.append(
            {
                "feature_table": defaults["feature_table"],
                "node_id": str(nodes.loc[idx, "id"]),
                "node_type": defaults["node_type"],
                "summary_kind": defaults["summary_kind"],
                "summary_text": term["def"].strip(),
                "source": defaults["source"],
                "source_dataset": defaults["source_dataset"],
                "source_record_id": term_id,
                "provenance": str(obo_path),
                "license": defaults["license"],
                "citation": defaults["citation"],
                "release": release,
                "created_at": created_at,
            }
        )
        if max_rows is not None and len(rows) >= max_rows:
            break
    return pd.DataFrame(rows)


def _comment_text(comment: dict[str, Any]) -> str:
    texts: list[str] = []
    if comment.get("texts"):
        texts.extend(str(t.get("value", "")).strip() for t in comment["texts"] if t.get("value"))
    if comment.get("text"):
        texts.append(str(comment["text"]).strip())
    if comment.get("locations") and comment.get("commentType") == "SUBCELLULAR LOCATION":
        locs = []
        for loc in comment.get("locations", []):
            value = loc.get("location", {}).get("value") if isinstance(loc, dict) else None
            if value:
                locs.append(str(value))
        if locs:
            texts.append("Subcellular location: " + "; ".join(locs))
    return " ".join(t for t in texts if t)


def rows_from_uniprot_entries(
    node_root: Path,
    entries_json_path: Path,
    *,
    release: str,
    created_at: str,
    max_rows: int | None = None,
) -> pd.DataFrame:
    proteins = _read_node_table(node_root, "protein", ["id", "uniprot_id"])
    mapping: dict[str, list[str]] = {}
    for _, row in proteins.dropna(subset=["uniprot_id"]).iterrows():
        for accession in str(row["uniprot_id"]).split("|"):
            accession = accession.strip()
            if accession:
                mapping.setdefault(accession, []).append(str(row["id"]))

    payload = json.loads(entries_json_path.read_text())
    entries = payload.get("entries", payload if isinstance(payload, list) else [])
    detected_release = str(payload.get("release") or release) if isinstance(payload, dict) else release
    rows: list[dict[str, str]] = []
    for entry in entries:
        accession = entry.get("primaryAccession") or entry.get("accession")
        if not accession or accession not in mapping:
            continue
        comments = entry.get("comments", []) or []
        chunks: list[str] = []
        for comment in comments:
            ctype = comment.get("commentType")
            if ctype in {"FUNCTION", "SUBCELLULAR LOCATION", "PTM", "CATALYTIC ACTIVITY", "PATHWAY"}:
                text = _comment_text(comment)
                if text:
                    chunks.append(f"{ctype}: {text}")
        if not chunks:
            continue
        summary_text = " ".join(chunks)
        for protein_id in mapping[accession]:
            rows.append(
                {
                    "feature_table": "protein_textual_summary",
                    "node_id": protein_id,
                    "node_type": NodeType.PROTEIN.value,
                    "summary_kind": "uniprot_function_location_ptm",
                    "summary_text": summary_text,
                    "source": "UniProtKB",
                    "source_dataset": "UniProtKB comments FUNCTION/SUBCELLULAR_LOCATION/PTM/PATHWAY",
                    "source_record_id": accession,
                    "provenance": f"https://rest.uniprot.org/uniprotkb/{accession}.json",
                    "license": SOURCE_POLICY["UniProtKB"]["license"],
                    "citation": "UniProt Consortium.",
                    "release": detected_release,
                    "created_at": created_at,
                }
            )
            if max_rows is not None and len(rows) >= max_rows:
                return pd.DataFrame(rows)
    return pd.DataFrame(rows)


def ensure_go_obo(path: Path, *, allow_download: bool) -> Path | None:
    if path.exists():
        return path
    if not allow_download:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(GO_BASIC_URL, path)
    return path


def stage_textual_summary_features(
    *,
    node_root: str,
    output_root: str,
    release: str,
    uberon_obo: str | None = None,
    go_obo: str | None = None,
    uniprot_entries_json: str | None = None,
    allow_download_go: bool = False,
    max_rows_per_table: int | None = None,
    max_text_chars: int = 5000,
) -> dict[str, Any]:
    node_root_path = Path(node_root)
    output_root_path = Path(output_root)
    created_at = _utc_now()
    root = open_kg_root(str(output_root_path))
    reports = output_root_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    audit = source_policy_audit()
    audit_path = reports / "textual_summary_source_audit.csv"
    audit.to_csv(audit_path, index=False)

    validations: dict[str, dict[str, Any]] = {}
    decisions: list[str] = [
        "GeneCards rejected: no scraping/redistribution without explicit acceptable terms.",
        "DrugBank textual scraping rejected/deferred: use ChEMBL/OpenTargets fields unless a separate DrugBank license is provided.",
        "Tables are staged under features/, not edges/ or evidence/.",
    ]

    tables_to_rows: dict[str, pd.DataFrame] = {}
    for node_type in ["gene", "disease", "molecule"]:
        try:
            rows = rows_from_node_descriptions(
                node_root_path, node_type, release=release, created_at=created_at, max_rows=max_rows_per_table
            )
        except FileNotFoundError:
            continue
        if not rows.empty:
            tables_to_rows[TEXT_SOURCE_DEFAULTS[node_type]["feature_table"]] = rows

    if uberon_obo:
        uberon_path = Path(uberon_obo)
        if uberon_path.exists():
            rows = rows_from_obo_definitions(
                node_root_path,
                "tissue",
                uberon_path,
                release=release,
                created_at=created_at,
                source_key="tissue",
                max_rows=max_rows_per_table,
            )
            if not rows.empty:
                tables_to_rows["tissue_textual_summary"] = rows

    if go_obo:
        go_path = ensure_go_obo(Path(go_obo), allow_download=allow_download_go)
        if go_path and go_path.exists():
            rows = rows_from_obo_definitions(
                node_root_path,
                "pathway",
                go_path,
                release=release,
                created_at=created_at,
                source_key="pathway_go",
                id_column="go_id",
                max_rows=max_rows_per_table,
            )
            if not rows.empty:
                tables_to_rows["pathway_textual_summary"] = rows

    if uniprot_entries_json:
        entries_path = Path(uniprot_entries_json)
        if entries_path.exists():
            rows = rows_from_uniprot_entries(
                node_root_path, entries_path, release=release, created_at=created_at, max_rows=max_rows_per_table
            )
            if not rows.empty:
                tables_to_rows["protein_textual_summary"] = rows

    allowed = allowed_textual_summary_tables()
    for feature_table, rows in sorted(tables_to_rows.items()):
        node_type = allowed[feature_table]
        endpoint = _endpoint_ids(node_root_path, node_type)
        validation = write_textual_summaries(
            root,
            feature_table,
            rows,
            endpoint_node_ids=endpoint,
            max_text_chars=max_text_chars,
        )
        validations[feature_table] = validation.to_dict()

    for feature_table in sorted(set(allowed) - set(validations)):
        validations[feature_table] = {
            "rows": 0,
            "reason": "No acceptable local source rows were available in this run; source decision is recorded in audit.",
        }

    summary = {
        "staging_only": True,
        "canonical_promotion": False,
        "node_root": str(node_root_path),
        "output_root": str(output_root_path),
        "release": release,
        "created_at": created_at,
        "source_audit": str(audit_path),
        "tables": validations,
        "source_decisions": decisions,
        "max_text_chars": max_text_chars,
    }
    summary_path = reports / "textual_summary_features_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-root", required=True, help="Directory containing nodes/*.parquet or the nodes directory itself")
    parser.add_argument("--output-root", required=True, help="Staging output root")
    parser.add_argument("--release", required=True, help="Source release/date label")
    parser.add_argument("--uberon-obo", help="Path to uberon-basic.obo for tissue definitions")
    parser.add_argument("--go-obo", help="Path to go-basic.obo for GO pathway/process definitions")
    parser.add_argument("--allow-download-go", action="store_true", help="Download go-basic.obo if --go-obo is missing")
    parser.add_argument("--uniprot-entries-json", help="Optional UniProt API JSON payload with entries")
    parser.add_argument("--max-rows-per-table", type=int, help="Optional cap for pilot builds/tests")
    parser.add_argument("--max-text-chars", type=int, default=5000)
    args = parser.parse_args(argv)

    node_root = Path(args.node_root)
    if (node_root / "nodes").exists():
        node_root = node_root / "nodes"
    summary = stage_textual_summary_features(
        node_root=str(node_root),
        output_root=args.output_root,
        release=args.release,
        uberon_obo=args.uberon_obo,
        go_obo=args.go_obo,
        uniprot_entries_json=args.uniprot_entries_json,
        allow_download_go=args.allow_download_go,
        max_rows_per_table=args.max_rows_per_table,
        max_text_chars=args.max_text_chars,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
