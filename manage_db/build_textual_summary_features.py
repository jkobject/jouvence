"""Stage textual-summary feature tables for KG nodes.

The module writes only ``features/*_textual_summary.parquet`` plus reports.  It
never creates KG biological edges.  Source decisions are intentionally
conservative and are reported in ``reports/textual_summary_source_audit.csv``.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
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
    "cell_type": {
        "feature_table": "cell_type_textual_summary",
        "node_type": NodeType.CELL_TYPE.value,
        "summary_kind": "cell_type_definition",
        "source": "Cell Ontology",
        "source_dataset": "cl.obo def fields",
        "license": SOURCE_POLICY["Cell Ontology"]["license"],
        "citation": "Cell Ontology / OBO Foundry.",
    },
    "phenotype_hpo": {
        "feature_table": "phenotype_textual_summary",
        "node_type": NodeType.PHENOTYPE.value,
        "summary_kind": "phenotype_definition",
        "source": "HPO",
        "source_dataset": "hp.obo def fields",
        "license": SOURCE_POLICY["HPO"]["license"],
        "citation": "Human Phenotype Ontology.",
    },
}

GO_BASIC_URL = "https://purl.obolibrary.org/obo/go/go-basic.obo"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"
ACCEPTED_UNIPROT_COMMENT_TYPES = {"FUNCTION", "SUBCELLULAR LOCATION", "PTM", "CATALYTIC ACTIVITY", "PATHWAY"}


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
    max_text_chars: int = 5000,
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
            if ctype in ACCEPTED_UNIPROT_COMMENT_TYPES:
                text = _comment_text(comment)
                if text:
                    chunks.append(f"{ctype}: {text}")
        if not chunks:
            continue
        summary_text = _bounded_text(" ".join(chunks), max_text_chars)
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



def collect_uniprot_accessions(node_root: Path) -> list[str]:
    """Return deterministic distinct UniProt accessions from protein.uniprot_id."""

    try:
        proteins = _read_node_table(node_root, "protein", ["uniprot_id"])
    except FileNotFoundError:
        return []
    if "uniprot_id" not in proteins.columns:
        return []
    accessions: set[str] = set()
    for value in proteins["uniprot_id"].dropna().astype(str):
        for accession in value.split("|"):
            accession = accession.strip()
            if accession:
                accessions.add(accession)
    return sorted(accessions)


def uniprot_counts_from_entries(node_root: Path, entries_json_path: Path) -> dict[str, int]:
    accessions = set(collect_uniprot_accessions(node_root))
    payload = json.loads(entries_json_path.read_text())
    entries = payload.get("entries", payload if isinstance(payload, list) else [])
    accepted = 0
    for entry in entries:
        accession = entry.get("primaryAccession") or entry.get("accession")
        if not accession or accession not in accessions:
            continue
        comments = entry.get("comments", []) or []
        if any(_comment_text(c) for c in comments if c.get("commentType") in ACCEPTED_UNIPROT_COMMENT_TYPES):
            accepted += 1
    rows = rows_from_uniprot_entries(node_root, entries_json_path, release="", created_at="")
    return {
        "distinct_accessions_requested": len(accessions),
        "entries_returned": len(entries),
        "entries_with_accepted_comments": accepted,
        "protein_node_rows_emitted": len(rows),
    }


def fetch_uniprot_entries_json(
    node_root: Path,
    output_json: Path,
    raw_dir: Path,
    *,
    sleep_seconds: float = 0.25,
    max_attempts: int = 3,
) -> Path:
    """Fetch UniProtKB entries for mapped protein accessions with resume/backoff.

    This uses the UniProtKB JSON endpoint for already-mapped accessions from
    nodes/protein.parquet.  It is source-approved API retrieval, not page
    scraping.  Per-accession raw JSON files are kept so interrupted full builds
    can resume deterministically.
    """

    raw_dir.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for accession in collect_uniprot_accessions(node_root):
        raw_path = raw_dir / f"{accession}.json"
        if raw_path.exists():
            entries.append(json.loads(raw_path.read_text()))
            continue
        url = UNIPROT_ENTRY_URL.format(accession=accession)
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            try:
                request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "txgnn-textual-summary-builder/1.0"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read().decode("utf-8")
                raw_path.write_text(body, encoding="utf-8")
                entries.append(json.loads(body))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    last_error = exc
                    break
                last_error = exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt + 1 < max_attempts:
                time.sleep(sleep_seconds * (2**attempt))
        else:
            raise RuntimeError(f"Failed to fetch UniProt accession {accession}: {last_error}")
        if last_error is not None and not raw_path.exists():
            # Missing/deprecated accession: keep a tiny marker so resume is deterministic.
            raw_path.write_text(json.dumps({"primaryAccession": accession, "comments": [], "fetch_error": str(last_error)}), encoding="utf-8")
        time.sleep(sleep_seconds)
    output_json.write_text(json.dumps({"entries": entries}, indent=2, sort_keys=True), encoding="utf-8")
    return output_json


def _normalise_cellosaurus_license(header_lines: list[str]) -> str:
    """Return the accepted local Cellosaurus license label from OBO header comments."""

    header_text = " ".join(line.strip() for line in header_lines)
    if "Creative Commons" not in header_text or "CC BY 4.0" not in header_text:
        return SOURCE_POLICY["Cellosaurus"]["license"]
    url_match = re.search(r"https://creativecommons\.org/licenses/by/4\.0/?", header_text)
    url = url_match.group(0) if url_match else "https://creativecommons.org/licenses/by/4.0/"
    return f"Creative Commons Attribution 4.0 International (CC BY 4.0); {url}; attribution/link/change-notice required"


def _cellosaurus_release_label(header: dict[str, str], fallback_release: str) -> str:
    release = header.get("data-version") or fallback_release
    date = header.get("date")
    return f"{release}; date={date}" if date else release


def parse_cellosaurus_obo(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    records: list[dict[str, Any]] = []
    header: dict[str, str] = {}
    current: dict[str, Any] = {}
    in_term = False
    in_license_block = False
    license_lines: list[str] = []

    def flush() -> None:
        if current.get("id") and current.get("comments") and current.get("depmap_xrefs"):
            records.append(dict(current))

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not in_term and line.startswith("data-version: "):
                header["data-version"] = line.split(": ", 1)[1]
            elif not in_term and line.startswith("date: "):
                header["date"] = line.split(": ", 1)[1]
            elif not in_term and line.startswith("!"):
                comment = line[1:].strip()
                if comment.startswith("Licensing information:"):
                    in_license_block = True
                if in_license_block:
                    if comment:
                        license_lines.append(comment)
                    elif license_lines:
                        in_license_block = False
            if line == "[Term]":
                if in_term:
                    flush()
                current = {"comments": [], "depmap_xrefs": []}
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
            elif key == "xref" and value.startswith("DepMap:ACH-"):
                current.setdefault("depmap_xrefs", []).append(value.split()[0].replace("DepMap:", ""))
            elif key == "comment" and value.strip():
                current.setdefault("comments", []).append(value.strip())
        if in_term:
            flush()
    if license_lines:
        header["license"] = _normalise_cellosaurus_license(license_lines)
    return records, header


def _bounded_text(text: str, max_text_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_text_chars:
        return text
    suffix = " ... [truncated to max_text_chars]"
    return text[: max_text_chars - len(suffix)].rstrip() + suffix


def rows_from_cellosaurus_obo(
    node_root: Path,
    cellosaurus_obo: Path,
    *,
    release: str,
    created_at: str,
    max_rows: int | None = None,
    max_text_chars: int = 5000,
) -> pd.DataFrame:
    nodes = _read_node_table(node_root, "cell_line", ["id", "name"])
    endpoint = set(nodes["id"].fillna("").astype(str))
    records, header = parse_cellosaurus_obo(cellosaurus_obo)
    detected_release = _cellosaurus_release_label(header, release)
    detected_license = header.get("license") or SOURCE_POLICY["Cellosaurus"]["license"]
    header_provenance = "; ".join(
        part
        for part in [
            f"data-version={header.get('data-version')}" if header.get("data-version") else "",
            f"date={header.get('date')}" if header.get("date") else "",
            f"license={detected_license}" if detected_license else "",
        ]
        if part
    )
    rows: list[dict[str, str]] = []
    for record in records:
        if record.get("is_obsolete") == "true":
            continue
        comment = _bounded_text(" ".join(record.get("comments", [])), max_text_chars)
        if not comment:
            continue
        for depmap_id in record.get("depmap_xrefs", []):
            if depmap_id not in endpoint:
                continue
            rows.append(
                {
                    "feature_table": "cell_line_textual_summary",
                    "node_id": depmap_id,
                    "node_type": NodeType.CELL_LINE.value,
                    "summary_kind": "cell_line_comment",
                    "summary_text": comment,
                    "source": "Cellosaurus",
                    "source_dataset": "cellosaurus.obo comment fields via DepMap xrefs",
                    "source_record_id": str(record["id"]),
                    "provenance": f"{cellosaurus_obo}; {header_provenance}; xref=DepMap:{depmap_id}",
                    "license": detected_license,
                    "citation": "Cellosaurus cell line knowledge resource.",
                    "release": detected_release,
                    "created_at": created_at,
                }
            )
            if max_rows is not None and len(rows) >= max_rows:
                return pd.DataFrame(rows)
    return pd.DataFrame(rows)


def _reactome_description_records(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        entries = payload.get("entries", payload.get("results", payload if isinstance(payload, list) else [])) if isinstance(payload, dict) else payload
        records = []
        for entry in entries:
            stable_id = entry.get("stable_id") or entry.get("stId") or entry.get("identifier") or entry.get("id")
            description = entry.get("description") or entry.get("summation") or entry.get("summary")
            if isinstance(description, list):
                description = " ".join(str(x.get("text", x)) for x in description)
            if stable_id and description:
                records.append({"stable_id": str(stable_id), "description": str(description)})
        return records
    df = pd.read_csv(path, sep="\t")
    id_col = next((c for c in ["stable_id", "stId", "identifier", "id", "reactome_id"] if c in df.columns), None)
    desc_col = next((c for c in ["description", "summation", "summary", "text"] if c in df.columns), None)
    if not id_col or not desc_col:
        raise ValueError(f"Reactome TSV must contain an id column and description column: {path}")
    return [
        {"stable_id": str(row[id_col]), "description": str(row[desc_col])}
        for _, row in df.dropna(subset=[id_col, desc_col]).iterrows()
        if str(row[desc_col]).strip()
    ]


def rows_from_reactome_pathways(
    node_root: Path,
    reactome_pathways: Path,
    *,
    release: str,
    created_at: str,
    max_rows: int | None = None,
) -> pd.DataFrame:
    nodes = _read_node_table(node_root, "pathway", ["id", "reactome_id", "name"])
    id_to_node: dict[str, str] = {}
    for _, row in nodes.iterrows():
        node_id = str(row["id"])
        id_to_node[node_id] = node_id
        if "reactome_id" in nodes.columns and pd.notna(row.get("reactome_id")) and str(row.get("reactome_id")).strip():
            id_to_node[str(row["reactome_id"]).strip()] = node_id
    rows: list[dict[str, str]] = []
    for record in _reactome_description_records(reactome_pathways):
        stable_id = record["stable_id"].strip()
        node_id = id_to_node.get(stable_id)
        if not node_id:
            continue
        rows.append(
            {
                "feature_table": "pathway_textual_summary",
                "node_id": node_id,
                "node_type": NodeType.PATHWAY.value,
                "summary_kind": "reactome_pathway_description",
                "summary_text": record["description"].strip(),
                "source": "Reactome",
                "source_dataset": f"Reactome pathway descriptions ({reactome_pathways.name})",
                "source_record_id": stable_id,
                "provenance": str(reactome_pathways),
                "license": SOURCE_POLICY["Reactome"]["license"],
                "citation": "Reactome pathway knowledgebase.",
                "release": release,
                "created_at": created_at,
            }
        )
        if max_rows is not None and len(rows) >= max_rows:
            break
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
    cl_obo: str | None = None,
    hpo_obo: str | None = None,
    cellosaurus_obo: str | None = None,
    reactome_pathways_json: str | None = None,
    reactome_pathways_tsv: str | None = None,
    uniprot_entries_json: str | None = None,
    fetch_uniprot: bool = False,
    uniprot_raw_dir: str | None = None,
    uniprot_sleep_seconds: float = 0.25,
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
    source_counts: dict[str, dict[str, int]] = {}

    def add_rows(feature_table: str, rows: pd.DataFrame) -> None:
        if rows.empty:
            return
        if feature_table in tables_to_rows:
            tables_to_rows[feature_table] = pd.concat([tables_to_rows[feature_table], rows], ignore_index=True)
        else:
            tables_to_rows[feature_table] = rows

    for node_type in ["gene", "disease", "molecule"]:
        try:
            rows = rows_from_node_descriptions(
                node_root_path, node_type, release=release, created_at=created_at, max_rows=max_rows_per_table
            )
        except FileNotFoundError:
            continue
        add_rows(TEXT_SOURCE_DEFAULTS[node_type]["feature_table"], rows)

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
            add_rows("tissue_textual_summary", rows)

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
            add_rows("pathway_textual_summary", rows)

    if cl_obo:
        cl_path = Path(cl_obo)
        if cl_path.exists():
            rows = rows_from_obo_definitions(
                node_root_path,
                "cell_type",
                cl_path,
                release=release,
                created_at=created_at,
                source_key="cell_type",
                max_rows=max_rows_per_table,
            )
            add_rows("cell_type_textual_summary", rows)

    if hpo_obo:
        hpo_path = Path(hpo_obo)
        if hpo_path.exists():
            rows = rows_from_obo_definitions(
                node_root_path,
                "phenotype",
                hpo_path,
                release=release,
                created_at=created_at,
                source_key="phenotype_hpo",
                max_rows=max_rows_per_table,
            )
            add_rows("phenotype_textual_summary", rows)

    if cellosaurus_obo:
        cellosaurus_path = Path(cellosaurus_obo)
        if cellosaurus_path.exists():
            rows = rows_from_cellosaurus_obo(
                node_root_path,
                cellosaurus_path,
                release=release,
                created_at=created_at,
                max_rows=max_rows_per_table,
                max_text_chars=max_text_chars,
            )
            add_rows("cell_line_textual_summary", rows)

    reactome_path = Path(reactome_pathways_json) if reactome_pathways_json else Path(reactome_pathways_tsv) if reactome_pathways_tsv else None
    if reactome_path and reactome_path.exists():
        rows = rows_from_reactome_pathways(
            node_root_path, reactome_path, release=release, created_at=created_at, max_rows=max_rows_per_table
        )
        add_rows("pathway_textual_summary", rows)

    if fetch_uniprot and not uniprot_entries_json:
        raw_dir = Path(uniprot_raw_dir) if uniprot_raw_dir else output_root_path / "raw" / "uniprot"
        entries_path = fetch_uniprot_entries_json(
            node_root_path,
            raw_dir / "uniprot_entries.json",
            raw_dir / "entries",
            sleep_seconds=uniprot_sleep_seconds,
        )
        uniprot_entries_json = str(entries_path)

    if uniprot_entries_json:
        entries_path = Path(uniprot_entries_json)
        if entries_path.exists():
            rows = rows_from_uniprot_entries(
                node_root_path, entries_path, release=release, created_at=created_at, max_rows=max_rows_per_table, max_text_chars=max_text_chars
            )
            add_rows("protein_textual_summary", rows)
            counts = uniprot_counts_from_entries(node_root_path, entries_path)
            if max_rows_per_table is not None:
                counts["protein_node_rows_emitted"] = min(counts["protein_node_rows_emitted"], max_rows_per_table)
            source_counts["uniprot"] = counts

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
        "source_counts": source_counts,
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
    parser.add_argument("--cl-obo", help="Path to cl.obo for Cell Ontology cell type definitions")
    parser.add_argument("--hpo-obo", help="Path to hp.obo for HPO phenotype definitions")
    parser.add_argument("--cellosaurus-obo", help="Path to Cellosaurus OBO for DepMap-mapped cell line comments")
    parser.add_argument("--reactome-pathways-json", help="Reactome pathway descriptions JSON dump/API payload")
    parser.add_argument("--reactome-pathways-tsv", help="Reactome pathway descriptions TSV dump")
    parser.add_argument("--allow-download-go", action="store_true", help="Download go-basic.obo if --go-obo is missing")
    parser.add_argument("--uniprot-entries-json", help="Optional UniProt API JSON payload with entries")
    parser.add_argument("--fetch-uniprot", action="store_true", help="Fetch all mapped UniProt accessions to local raw JSON before staging")
    parser.add_argument("--uniprot-raw-dir", help="Raw UniProt JSON cache directory for --fetch-uniprot")
    parser.add_argument("--uniprot-sleep-seconds", type=float, default=0.25, help="Delay/backoff base between UniProt API calls")
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
        cl_obo=args.cl_obo,
        hpo_obo=args.hpo_obo,
        cellosaurus_obo=args.cellosaurus_obo,
        reactome_pathways_json=args.reactome_pathways_json,
        reactome_pathways_tsv=args.reactome_pathways_tsv,
        uniprot_entries_json=args.uniprot_entries_json,
        fetch_uniprot=args.fetch_uniprot,
        uniprot_raw_dir=args.uniprot_raw_dir,
        uniprot_sleep_seconds=args.uniprot_sleep_seconds,
        allow_download_go=args.allow_download_go,
        max_rows_per_table=args.max_rows_per_table,
        max_text_chars=args.max_text_chars,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
