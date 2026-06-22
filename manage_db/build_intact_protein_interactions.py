"""Build staged IntAct source-native protein_interacts_protein artifacts.

This module intentionally writes only to a staging directory.  It reads IntAct
raw MITAB 2.7 evidence rows, keeps row-level PSI-MI/provenance fields, filters
for human-human protein-native positive interactions, maps UniProt accessions to
existing protein nodes when a KG node root is supplied, and materializes staged
edges/evidence plus validation reports.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Iterable, Iterator, Mapping, Sequence

import pandas as pd

from manage_db import kg_evidence
from manage_db.kg_schema import EDGE_PARQUET_COLUMNS
from manage_db.kg_storage import open_kg_root, read_nodes, write_edges

RELATION = "protein_interacts_protein"
DISPLAY_RELATION = "interacts with"
X_TYPE = "protein"
Y_TYPE = "protein"

INTACT_HUMAN_URL = "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/species/human.txt"
INTACT_HUMAN_NEGATIVE_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/species/human_negative.txt"
)
FEATURE_URLS = {
    "binding_regions": "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/bindings_regions.tsv",
    "mutations": "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/mutations.tsv",
    "ptms": "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/features/ptms.tsv",
}

MITAB_COLUMNS = [
    "ID(s) interactor A",
    "ID(s) interactor B",
    "Alt. ID(s) interactor A",
    "Alt. ID(s) interactor B",
    "Alias(es) interactor A",
    "Alias(es) interactor B",
    "Interaction detection method(s)",
    "Publication 1st author(s)",
    "Publication Identifier(s)",
    "Taxid interactor A",
    "Taxid interactor B",
    "Interaction type(s)",
    "Source database(s)",
    "Interaction identifier(s)",
    "Confidence value(s)",
    "Expansion method(s)",
    "Biological role(s) interactor A",
    "Biological role(s) interactor B",
    "Experimental role(s) interactor A",
    "Experimental role(s) interactor B",
    "Type(s) interactor A",
    "Type(s) interactor B",
    "Xref(s) interactor A",
    "Xref(s) interactor B",
    "Interaction Xref(s)",
    "Annotation(s) interactor A",
    "Annotation(s) interactor B",
    "Interaction annotation(s)",
    "Host organism(s)",
    "Interaction parameter(s)",
    "Creation date",
    "Update date",
    "Checksum(s) interactor A",
    "Checksum(s) interactor B",
    "Interaction Checksum(s)",
    "Negative",
    "Feature(s) interactor A",
    "Feature(s) interactor B",
    "Stoichiometry(s) interactor A",
    "Stoichiometry(s) interactor B",
    "Identification method participant A",
    "Identification method participant B",
]

FEATURE_COLUMNS = [
    "Feature AC",
    "Feature short label",
    "Feature range(s)",
    "Original sequence",
    "Resulting sequence",
    "Feature type",
    "Feature annotation(s)",
    "Affected molecule identifier",
    "Affected molecule symbol",
    "Affected molecule full name",
    "Affected molecule organism",
    "Interaction participants",
    "PubMed ID",
    "Figure legend(s)",
    "Interaction AC",
    "Xref ID(s)",
]

# Reviewed active allowlist from the A1 audit and R5 follow-up.  Keep predicates
# broad and save raw PSI-MI terms in evidence; do not mint one relation per MI
# term.  MI:0914 ``association`` is intentionally not active: it is too broad
# for graph materialization unless the same row also carries a narrower active
# physical/direct term.
INTERACTION_TYPE_PREDICATES = {
    "MI:0407": "direct_interaction",
    "MI:0915": "physical_association",
}
QUARANTINED_ASSOCIATION_MI = "MI:0914"
PROTEIN_TYPE_MI = "MI:0326"
HUMAN_TAXID = "taxid:9606"
UNIPROTKB = "uniprotkb"
PMID_RE = re.compile(r"(?:pubmed:|PMID:)?(\d{4,})", re.IGNORECASE)
MI_RE = re.compile(r'MI:\d+')
MISCORE_RE = re.compile(r"intact-miscore:([0-9]*\.?[0-9]+)")


def configure_csv_field_limit() -> None:
    """Allow current IntAct feature rows with very large annotation fields."""

    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


configure_csv_field_limit()


@dataclass(frozen=True)
class ParsedEndpoint:
    raw_id: str
    namespace: str
    identifier: str


@dataclass(frozen=True)
class BuildResult:
    edges: pd.DataFrame
    evidence: pd.DataFrame
    negative_evidence: pd.DataFrame
    rejected: pd.DataFrame
    validation: dict


def clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text == "-" else text


def split_pipe(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip() and part.strip() != "-"]


def parse_xref_token(token: str) -> tuple[str, str]:
    token = token.strip()
    if not token or ":" not in token:
        return "", token
    namespace, identifier = token.split(":", 1)
    # Strip MITAB db:id(description) tails only from the identifier; keep isoform
    # accessions such as O54918-3 intact.
    identifier = identifier.split("(", 1)[0].strip().strip('"')
    return namespace.lower().strip(), identifier


def parse_endpoint(raw: object) -> ParsedEndpoint:
    raw_id = clean(raw)
    if not raw_id:
        return ParsedEndpoint("", "", "")
    namespace, identifier = parse_xref_token(split_pipe(raw_id)[0] if "|" in raw_id else raw_id)
    return ParsedEndpoint(raw_id, namespace, identifier)


def endpoint_candidates(row: pd.Series, side: str) -> list[ParsedEndpoint]:
    """Return source-native protein endpoint candidates for interactor A/B.

    IntAct MITAB sometimes uses an IntAct molecule accession as the primary
    ``ID(s) interactor`` and puts UniProt/ENSP identifiers in alternate IDs or
    xrefs. This is still protein/isoform-native as long as we select only
    protein namespaces and never project through genes/RNA.
    """

    candidates: list[ParsedEndpoint] = []
    for col in [f"ID(s) interactor {side}", f"Alt. ID(s) interactor {side}", f"Xref(s) interactor {side}"]:
        for token in split_pipe(row.get(col)):
            endpoint = parse_endpoint(token)
            if endpoint.namespace and endpoint.identifier:
                candidates.append(endpoint)
    return candidates


def select_endpoint(row: pd.Series, side: str) -> ParsedEndpoint:
    candidates = endpoint_candidates(row, side)
    for namespace in ("uniprotkb", "ensembl"):
        for endpoint in candidates:
            if endpoint.namespace != namespace:
                continue
            if namespace == "ensembl" and not endpoint.identifier.startswith("ENSP"):
                continue
            return endpoint
    return parse_endpoint(row.get(f"ID(s) interactor {side}"))


def mi_terms(value: object) -> list[str]:
    return MI_RE.findall(clean(value))


def has_mi(value: object, term: str) -> bool:
    return term in mi_terms(value)


def has_taxid(value: object, taxid: str = HUMAN_TAXID) -> bool:
    return any(part.lower().startswith(taxid.lower()) for part in split_pipe(value) or [clean(value)])


def parse_negative(value: object) -> bool:
    return clean(value).lower() in {"true", "1", "yes", "negative"}


def parse_pmids(value: object) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in split_pipe(value):
        namespace, identifier = parse_xref_token(token)
        if namespace.lower() == "pubmed" and identifier.isdigit():
            pmids = [identifier]
        elif token.upper().startswith("PMID:"):
            pmids = [token.split(":", 1)[1].strip()]
        elif token.isdigit():
            pmids = [token]
        else:
            pmids = []
        for match in pmids:
            pmid = f"PMID:{match}"
            if pmid not in seen:
                seen.add(pmid)
                out.append(pmid)
    return out


def parse_intact_miscore(value: object) -> float | None:
    match = MISCORE_RE.search(clean(value))
    if not match:
        return None
    return float(match.group(1))


def predicate_from_interaction_type(value: object) -> str:
    terms = mi_terms(value)
    for term in terms:
        if term in INTERACTION_TYPE_PREDICATES:
            return INTERACTION_TYPE_PREDICATES[term]
    return ""


def has_quarantined_association_only(value: object) -> bool:
    terms = mi_terms(value)
    return QUARANTINED_ASSOCIATION_MI in terms and not any(
        term in INTERACTION_TYPE_PREDICATES for term in terms
    )


def interaction_accessions(value: object) -> list[str]:
    ids: list[str] = []
    for token in split_pipe(value):
        namespace, identifier = parse_xref_token(token)
        if namespace in {"intact", "imex", "mint"} and identifier:
            ids.append(identifier)
    return ids


def source_record_id(row: pd.Series, source_row_number: int) -> str:
    ids = interaction_accessions(row.get("Interaction identifier(s)"))
    prefix = ids[0] if ids else f"row-{source_row_number}"
    return f"IntAct:species/human.txt:{prefix}:{source_row_number}"


def iter_tsv_rows(path_or_url: str | Path, *, max_rows: int | None = None) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield 1-based data-row number and row dict from a local/HTTP TSV.

    Supports plain text, gzip, and zip files.  For HTTP sample mode with a plain
    .txt URL this streams until max_rows instead of downloading the full file.
    """

    path_text = str(path_or_url)
    if path_text.startswith(("http://", "https://")):
        with urllib.request.urlopen(path_text) as response:  # noqa: S310 - fixed source URLs / caller supplied source files
            yield from _iter_tsv_stream(response, path_text, max_rows=max_rows)
        return
    path = Path(path_or_url)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [name for name in zf.namelist() if not name.endswith("/")]
            if len(members) != 1:
                raise ValueError(f"expected one file in {path}, found {members[:5]}")
            with zf.open(members[0]) as fh:
                yield from _iter_tsv_stream(fh, members[0], max_rows=max_rows)
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:  # type: ignore[arg-type]
        yield from _iter_tsv_text(fh, max_rows=max_rows)


def _iter_tsv_stream(binary_fh, label: str, *, max_rows: int | None) -> Iterator[tuple[int, dict[str, str]]]:
    import io

    if label.endswith(".gz"):
        with gzip.open(binary_fh, "rt", encoding="utf-8", newline="") as text_fh:
            yield from _iter_tsv_text(text_fh, max_rows=max_rows)
        return
    with io.TextIOWrapper(binary_fh, encoding="utf-8", newline="") as text_fh:
        yield from _iter_tsv_text(text_fh, max_rows=max_rows)


def _iter_tsv_text(text_fh, *, max_rows: int | None) -> Iterator[tuple[int, dict[str, str]]]:
    reader = csv.DictReader(text_fh, delimiter="\t")
    if reader.fieldnames is None:
        return
    if len(reader.fieldnames) not in {16, 36, 42}:
        raise ValueError(f"unexpected MITAB/TSV column count: {len(reader.fieldnames)}")
    for source_row_number, row in enumerate(reader, start=1):
        if max_rows is not None and source_row_number > max_rows:
            break
        yield source_row_number, {key: value for key, value in row.items() if key is not None}


def load_feature_refs(paths_by_kind: Mapping[str, str | Path], *, max_rows: int | None = None) -> dict[str, dict[str, list[dict]]]:
    """Load IntAct feature side tables keyed by Interaction AC."""

    by_kind: dict[str, dict[str, list[dict]]] = {}
    for kind, path in paths_by_kind.items():
        per_interaction: dict[str, list[dict]] = defaultdict(list)
        for _, row in iter_tsv_rows(path, max_rows=max_rows):
            interaction_ac = clean(row.get("Interaction AC"))
            if not interaction_ac:
                continue
            payload = {col: clean(row.get(col)) for col in FEATURE_COLUMNS if col in row}
            payload["feature_kind"] = kind
            per_interaction[interaction_ac].append(payload)
        by_kind[kind] = dict(per_interaction)
    return by_kind


def refs_for_interaction(row: pd.Series, features: dict[str, dict[str, list[dict]]]) -> dict[str, list[dict]]:
    ids = interaction_accessions(row.get("Interaction identifier(s)"))
    out: dict[str, list[dict]] = {}
    for kind, records_by_interaction in features.items():
        records: list[dict] = []
        for interaction_id in ids:
            records.extend(records_by_interaction.get(interaction_id, []))
        out[kind] = records
    return out


def load_uniprot_to_protein_id(node_root: str | Path | None) -> dict[str, str]:
    """Return source protein accession/id -> canonical protein node id mapping."""

    if not node_root:
        return {}
    root = open_kg_root(str(node_root))
    proteins = read_nodes(root, "protein", columns=["id", "uniprot_id"])
    mapping: dict[str, str] = {}
    for _, row in proteins.iterrows():
        protein_id = clean(row.get("id"))
        if protein_id:
            mapping[protein_id] = protein_id
        for token in split_pipe(row.get("uniprot_id")):
            if token and protein_id:
                mapping[token] = protein_id
    return mapping


def accepted_source_endpoint(endpoint: ParsedEndpoint) -> bool:
    if "multiple parent" in endpoint.raw_id.lower():
        return False
    if endpoint.namespace == UNIPROTKB and endpoint.identifier:
        return True
    if endpoint.namespace == "ensembl" and endpoint.identifier.startswith("ENSP"):
        return True
    return False


def map_endpoint(endpoint: ParsedEndpoint, mapping: dict[str, str]) -> str:
    if not mapping:
        # Staging parser tests and offline dry-runs may use UniProt source IDs as
        # temporary protein IDs, but production validation should supply node_root
        # and anti-join against canonical protein nodes.
        return endpoint.identifier
    return mapping.get(endpoint.identifier, "")


def reject_reason(row: pd.Series, endpoint_a: ParsedEndpoint, endpoint_b: ParsedEndpoint, mapping: dict[str, str]) -> str:
    if parse_negative(row.get("Negative")):
        return "negative_evidence"
    if not has_mi(row.get("Type(s) interactor A"), PROTEIN_TYPE_MI) or not has_mi(
        row.get("Type(s) interactor B"), PROTEIN_TYPE_MI
    ):
        return "non_protein_interactor_type"
    if not has_taxid(row.get("Taxid interactor A")) or not has_taxid(row.get("Taxid interactor B")):
        return "non_human_or_cross_species"
    if not accepted_source_endpoint(endpoint_a) or not accepted_source_endpoint(endpoint_b):
        return "unsupported_endpoint_namespace"
    if has_quarantined_association_only(row.get("Interaction type(s)")):
        return "interaction_type_association_too_broad"
    if not predicate_from_interaction_type(row.get("Interaction type(s)")):
        return "interaction_type_not_allowlisted"
    if mapping and (not map_endpoint(endpoint_a, mapping) or not map_endpoint(endpoint_b, mapping)):
        return "protein_node_unmapped"
    return ""


def has_explicit_self_loop_support(row: pd.Series, feature_refs: dict[str, list[dict]]) -> bool:
    """Return whether a same-protein row has source-native homomer support."""

    keyword_fields = [
        "Interaction type(s)",
        "Interaction annotation(s)",
        "Interaction parameter(s)",
        "Feature(s) interactor A",
        "Feature(s) interactor B",
    ]
    keyword_blob = " | ".join(clean(row.get(field)).lower() for field in keyword_fields)
    if any(keyword in keyword_blob for keyword in ("homodimer", "homomer", "homo-dimer", "homo dimer")):
        return True

    for field in ("Stoichiometry(s) interactor A", "Stoichiometry(s) interactor B"):
        value = clean(row.get(field))
        if value and value not in {"1", "1.0"}:
            return True

    for records in feature_refs.values():
        for record in records:
            feature_blob = " | ".join(clean(value).lower() for value in record.values())
            if any(keyword in feature_blob for keyword in ("homodimer", "homomer", "homo-dimer", "homo dimer")):
                return True
    return False


def evidence_row(
    row: pd.Series,
    *,
    source_row_number: int,
    endpoint_a: ParsedEndpoint,
    endpoint_b: ParsedEndpoint,
    x_id: str,
    y_id: str,
    predicate: str,
    feature_refs: dict[str, list[dict]],
    source_dataset: str,
) -> dict:
    pmids = parse_pmids(row.get("Publication Identifier(s)"))
    text_span = {
        "source_file": "species/human.txt",
        "source_row_number": source_row_number,
        "source_interactor_a_id": clean(row.get("ID(s) interactor A")),
        "source_interactor_b_id": clean(row.get("ID(s) interactor B")),
        "selected_interactor_a_id": endpoint_a.raw_id,
        "selected_interactor_b_id": endpoint_b.raw_id,
        "selected_interactor_a_namespace": endpoint_a.namespace,
        "selected_interactor_b_namespace": endpoint_b.namespace,
        "source_interactor_a_alt_ids": clean(row.get("Alt. ID(s) interactor A")),
        "source_interactor_b_alt_ids": clean(row.get("Alt. ID(s) interactor B")),
        "source_interactor_a_aliases": clean(row.get("Alias(es) interactor A")),
        "source_interactor_b_aliases": clean(row.get("Alias(es) interactor B")),
        "source_interactor_a_type": clean(row.get("Type(s) interactor A")),
        "source_interactor_b_type": clean(row.get("Type(s) interactor B")),
        "taxid_interactor_a": clean(row.get("Taxid interactor A")),
        "taxid_interactor_b": clean(row.get("Taxid interactor B")),
        "interaction_type": clean(row.get("Interaction type(s)")),
        "interaction_type_mi_terms": mi_terms(row.get("Interaction type(s)")),
        "detection_method": clean(row.get("Interaction detection method(s)")),
        "detection_method_mi_terms": mi_terms(row.get("Interaction detection method(s)")),
        "participant_identification_method_a": clean(row.get("Identification method participant A")),
        "participant_identification_method_b": clean(row.get("Identification method participant B")),
        "biological_role_a": clean(row.get("Biological role(s) interactor A")),
        "biological_role_b": clean(row.get("Biological role(s) interactor B")),
        "experimental_role_a": clean(row.get("Experimental role(s) interactor A")),
        "experimental_role_b": clean(row.get("Experimental role(s) interactor B")),
        "host_organism": clean(row.get("Host organism(s)")),
        "publication_first_author": clean(row.get("Publication 1st author(s)")),
        "publication_ids": clean(row.get("Publication Identifier(s)")),
        "pmids": pmids,
        "source_database": clean(row.get("Source database(s)")),
        "interaction_identifiers": clean(row.get("Interaction identifier(s)")),
        "confidence_values": clean(row.get("Confidence value(s)")),
        "expansion_method": clean(row.get("Expansion method(s)")),
        "negative": parse_negative(row.get("Negative")),
        "features_a": clean(row.get("Feature(s) interactor A")),
        "features_b": clean(row.get("Feature(s) interactor B")),
        "stoichiometry_a": clean(row.get("Stoichiometry(s) interactor A")),
        "stoichiometry_b": clean(row.get("Stoichiometry(s) interactor B")),
        "feature_side_table_refs": {
            kind: [record.get("Feature AC", "") for record in records]
            for kind, records in feature_refs.items()
        },
        "binding_regions": feature_refs.get("binding_regions", []),
        "mutations": feature_refs.get("mutations", []),
        "ptms": feature_refs.get("ptms", []),
        "interaction_xrefs": clean(row.get("Interaction Xref(s)")),
        "interaction_annotations": clean(row.get("Interaction annotation(s)")),
        "parameters": clean(row.get("Interaction parameter(s)")),
        "creation_date": clean(row.get("Creation date")),
        "update_date": clean(row.get("Update date")),
        "checksums_a": clean(row.get("Checksum(s) interactor A")),
        "checksums_b": clean(row.get("Checksum(s) interactor B")),
        "interaction_checksums": clean(row.get("Interaction Checksum(s)")),
        "raw_mitab": {col: clean(row.get(col)) for col in MITAB_COLUMNS if col in row.index},
        "endpoint_policy": "UniProt protein/isoform source endpoint; mapped to canonical protein nodes when node_root supplied; no gene-to-protein projection",
    }
    if x_id == y_id:
        text_span["self_loop_policy"] = "accepted_explicit_homodimer_support"
    paper_id = pmids[0] if pmids else ""
    return {
        "relation": RELATION,
        "x_id": x_id,
        "x_type": X_TYPE,
        "y_id": y_id,
        "y_type": Y_TYPE,
        "evidence_type": "experiment",
        "source": "IntAct",
        "source_dataset": source_dataset,
        "source_record_id": source_record_id(row, source_row_number),
        "paper_id": paper_id,
        "dataset_id": "",
        "study_id": "",
        "evidence_score": parse_intact_miscore(row.get("Confidence value(s)")),
        "effect_size": None,
        "p_value": None,
        "direction": "undirected",
        "confidence_interval": "",
        "predicate": predicate,
        "text_span": json.dumps(text_span, sort_keys=True, separators=(",", ":")),
        "section": "",
        "extraction_method": "IntAct MITAB27 source-native parser",
        "license": "IntAct public FTP; check IntAct terms before canonical promotion",
        "release": "current",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def canonical_pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def rejected_row(
    row: pd.Series,
    *,
    source_row_number: int,
    reason: str,
    endpoint_a: ParsedEndpoint,
    endpoint_b: ParsedEndpoint,
    x_mapped: str,
    y_mapped: str,
    feature_refs: dict[str, list[dict]],
) -> dict:
    source_payload = {
        "source_row_number": source_row_number,
        "reject_reason": reason,
        "source_interactor_a_id": clean(row.get("ID(s) interactor A")),
        "source_interactor_b_id": clean(row.get("ID(s) interactor B")),
        "selected_interactor_a_id": endpoint_a.raw_id,
        "selected_interactor_b_id": endpoint_b.raw_id,
        "selected_interactor_a_namespace": endpoint_a.namespace,
        "selected_interactor_b_namespace": endpoint_b.namespace,
        "mapped_interactor_a_id": x_mapped,
        "mapped_interactor_b_id": y_mapped,
        "interaction_type": clean(row.get("Interaction type(s)")),
        "interaction_type_mi_terms": mi_terms(row.get("Interaction type(s)")),
        "detection_method": clean(row.get("Interaction detection method(s)")),
        "detection_method_mi_terms": mi_terms(row.get("Interaction detection method(s)")),
        "feature_side_table_refs": {
            kind: [record.get("Feature AC", "") for record in records]
            for kind, records in feature_refs.items()
        },
        "raw_mitab": {col: clean(row.get(col)) for col in MITAB_COLUMNS if col in row.index},
    }
    return {
        "source_row_number": source_row_number,
        "reason": reason,
        "source_interactor_a_id": endpoint_a.raw_id,
        "source_interactor_b_id": endpoint_b.raw_id,
        "taxid_interactor_a": clean(row.get("Taxid interactor A")),
        "taxid_interactor_b": clean(row.get("Taxid interactor B")),
        "type_interactor_a": clean(row.get("Type(s) interactor A")),
        "type_interactor_b": clean(row.get("Type(s) interactor B")),
        "interaction_type": clean(row.get("Interaction type(s)")),
        "interaction_identifiers": clean(row.get("Interaction identifier(s)")),
        "source_payload": json.dumps(source_payload, sort_keys=True, separators=(",", ":")),
    }


def build_from_mitab(
    rows: Iterable[tuple[int, dict[str, str]]],
    *,
    uniprot_to_protein: dict[str, str] | None = None,
    feature_refs_by_interaction: dict[str, dict[str, list[dict]]] | None = None,
    source_dataset: str = "intact_species_human_mitab27_current",
) -> BuildResult:
    mapping = uniprot_to_protein or {}
    feature_refs_by_interaction = feature_refs_by_interaction or {}
    evidence_rows: list[dict] = []
    negative_rows: list[dict] = []
    rejected_rows: list[dict] = []
    edge_records: dict[tuple[str, str], dict] = {}
    source_counts: dict[str, int] = defaultdict(int)

    for source_row_number, raw_row in rows:
        row = pd.Series(raw_row)
        source_counts["input_rows"] += 1
        endpoint_a = select_endpoint(row, "A")
        endpoint_b = select_endpoint(row, "B")
        reason = reject_reason(row, endpoint_a, endpoint_b, mapping)
        predicate = predicate_from_interaction_type(row.get("Interaction type(s)"))
        x_mapped = map_endpoint(endpoint_a, mapping)
        y_mapped = map_endpoint(endpoint_b, mapping)
        feature_refs = refs_for_interaction(row, feature_refs_by_interaction)

        if parse_negative(row.get("Negative")):
            source_counts["negative_rows"] += 1
            # Keep negative rows as side evidence only if they otherwise name
            # protein-ish endpoints; they never materialize positive graph edges.
            if x_mapped and y_mapped and predicate:
                x_id, y_id = canonical_pair(x_mapped, y_mapped)
                neg = evidence_row(
                    row,
                    source_row_number=source_row_number,
                    endpoint_a=endpoint_a,
                    endpoint_b=endpoint_b,
                    x_id=x_id,
                    y_id=y_id,
                    predicate=predicate,
                    feature_refs=feature_refs,
                    source_dataset=f"{source_dataset}_negative",
                )
                neg["text_span"] = json.dumps(
                    {**json.loads(neg["text_span"]), "negative": True},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                negative_rows.append(neg)
            continue

        if reason:
            source_counts[f"rejected_{reason}"] += 1
            rejected_rows.append(
                rejected_row(
                    row,
                    source_row_number=source_row_number,
                    reason=reason,
                    endpoint_a=endpoint_a,
                    endpoint_b=endpoint_b,
                    x_mapped=x_mapped,
                    y_mapped=y_mapped,
                    feature_refs=feature_refs,
                )
            )
            continue

        x_id, y_id = canonical_pair(x_mapped, y_mapped)
        if x_id == y_id and not has_explicit_self_loop_support(row, feature_refs):
            reason = "self_loop_requires_homodimer_support"
            source_counts[f"rejected_{reason}"] += 1
            rejected_rows.append(
                rejected_row(
                    row,
                    source_row_number=source_row_number,
                    reason=reason,
                    endpoint_a=endpoint_a,
                    endpoint_b=endpoint_b,
                    x_mapped=x_mapped,
                    y_mapped=y_mapped,
                    feature_refs=feature_refs,
                )
            )
            continue

        edge_key = (x_id, y_id)
        source_counts["accepted_evidence_rows"] += 1
        evidence_rows.append(
            evidence_row(
                row,
                source_row_number=source_row_number,
                endpoint_a=endpoint_a,
                endpoint_b=endpoint_b,
                x_id=x_id,
                y_id=y_id,
                predicate=predicate,
                feature_refs=feature_refs,
                source_dataset=source_dataset,
            )
        )
        edge_records[edge_key] = {
            "x_id": x_id,
            "x_type": X_TYPE,
            "y_id": y_id,
            "y_type": Y_TYPE,
            "relation": RELATION,
            "display_relation": DISPLAY_RELATION,
            "source": "IntAct/species_human_mitab27",
            "credibility": 3,
        }

    edges = pd.DataFrame(edge_records.values(), columns=[name for name, _ in EDGE_PARQUET_COLUMNS])
    evidence = pd.DataFrame(evidence_rows)
    negative_evidence = pd.DataFrame(negative_rows)
    rejected = pd.DataFrame(rejected_rows)
    validation = validate_outputs(edges, evidence, negative_evidence, rejected, source_counts, mapping_supplied=bool(mapping))
    return BuildResult(edges, evidence, negative_evidence, rejected, validation)


def validate_outputs(
    edges: pd.DataFrame,
    evidence: pd.DataFrame,
    negative_evidence: pd.DataFrame,
    rejected: pd.DataFrame,
    source_counts: dict[str, int],
    *,
    mapping_supplied: bool,
) -> dict:
    validation: dict = {
        "ok": True,
        "source_counts": dict(sorted(source_counts.items())),
        "edge_rows": int(len(edges)),
        "evidence_rows": int(len(evidence)),
        "negative_evidence_rows": int(len(negative_evidence)),
        "rejected_rows": int(len(rejected)),
        "mapping_supplied": mapping_supplied,
        "checks": {},
        "warnings": [],
    }

    checks = validation["checks"]
    if evidence.empty:
        checks["evidence_support"] = {"ok": len(edges) == 0, "unsupported_edges": []}
    else:
        edge_keys = set(edges["relation"] + "|" + edges["x_id"] + "|" + edges["y_id"])
        evidence_keys = set(evidence["relation"] + "|" + evidence["x_id"] + "|" + evidence["y_id"])
        unsupported = sorted(edge_keys - evidence_keys)
        checks["evidence_support"] = {"ok": not unsupported, "unsupported_edges": unsupported[:20]}
        validation["ok"] = validation["ok"] and not unsupported

    if not edges.empty:
        duplicate_count = int(edges.duplicated(subset=["x_id", "y_id", "relation"]).sum())
        self_loops = sorted(edges.loc[edges["x_id"] == edges["y_id"], "x_id"].astype(str).unique().tolist())
    else:
        duplicate_count = 0
        self_loops = []
    checks["duplicate_policy"] = {
        "ok": duplicate_count == 0,
        "policy": "undirected pairs sorted after endpoint mapping and deduplicated for edges; evidence remains row-level",
        "duplicate_edges": duplicate_count,
        "self_loops": self_loops[:20],
    }
    validation["ok"] = validation["ok"] and duplicate_count == 0

    if not evidence.empty:
        payloads = evidence["text_span"].map(json.loads)
        bad_negative = [p.get("source_row_number") for p in payloads if p.get("negative")]
        required_payload_fields = [
            "interaction_type",
            "detection_method",
            "source_database",
            "publication_ids",
            "confidence_values",
            "source_interactor_a_id",
            "source_interactor_b_id",
            "selected_interactor_a_namespace",
            "selected_interactor_b_namespace",
            "taxid_interactor_a",
            "taxid_interactor_b",
            "participant_identification_method_a",
            "participant_identification_method_b",
            "feature_side_table_refs",
        ]
        missing_by_field = {
            field: sum(1 for p in payloads if field not in p) for field in required_payload_fields
        }
    else:
        bad_negative = []
        missing_by_field = {}
    checks["evidence_fields"] = {
        "ok": not bad_negative and all(count == 0 for count in missing_by_field.values()),
        "positive_evidence_rows_marked_negative": bad_negative[:20],
        "missing_payload_fields": missing_by_field,
    }
    validation["ok"] = validation["ok"] and checks["evidence_fields"]["ok"]

    if not mapping_supplied:
        validation["warnings"].append(
            "No node_root supplied; endpoint anti-join was limited to UniProt namespace checks and staged IDs are UniProt accessions. Supply --node-root for canonical protein node validation."
        )
    else:
        unmapped = int(source_counts.get("rejected_protein_node_unmapped", 0))
        checks["node_endpoint_antijoin"] = {
            "ok": True,
            "rejected_unmapped_candidate_rows": unmapped,
            "note": "Mapped endpoints were required to exist in nodes/protein.parquet uniprot_id xrefs before edge materialization.",
        }
    return validation


def write_outputs(result: BuildResult, output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    root = open_kg_root(str(output))
    (output / "edges").mkdir(parents=True, exist_ok=True)
    (output / "evidence").mkdir(parents=True, exist_ok=True)
    (output / "reports").mkdir(parents=True, exist_ok=True)

    if result.edges.empty:
        pd.DataFrame(columns=[name for name, _ in EDGE_PARQUET_COLUMNS]).to_parquet(
            output / "edges" / f"{RELATION}.parquet", index=False
        )
    else:
        write_edges(root, RELATION, result.edges)

    if result.evidence.empty:
        pd.DataFrame(columns=[name for name, _ in kg_evidence.EVIDENCE_PARQUET_COLUMNS]).to_parquet(
            output / "evidence" / f"{RELATION}.parquet", index=False
        )
    else:
        kg_evidence.write_evidence(root, RELATION, result.evidence)

    negative_path = output / "evidence" / f"{RELATION}_negative.parquet"
    if result.negative_evidence.empty:
        pd.DataFrame(columns=[name for name, _ in kg_evidence.EVIDENCE_PARQUET_COLUMNS]).to_parquet(
            negative_path, index=False
        )
    else:
        result.negative_evidence.to_parquet(negative_path, index=False)

    rejected_path = output / "reports" / "rejected_rows.parquet"
    result.rejected.to_parquet(rejected_path, index=False)
    validation_path = output / "reports" / "validation.json"
    validation_path.write_text(json.dumps(result.validation, indent=2, sort_keys=True) + "\n")
    manifest_path = output / "MANIFEST.json"
    manifest = {
        "relation": RELATION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "staging_only": True,
        "canonical_promotion": False,
        "inputs": {
            "positive_mitab": INTACT_HUMAN_URL,
            "negative_mitab": INTACT_HUMAN_NEGATIVE_URL,
            "feature_tables": FEATURE_URLS,
        },
        "outputs": {
            "edges": str(output / "edges" / f"{RELATION}.parquet"),
            "evidence": str(output / "evidence" / f"{RELATION}.parquet"),
            "negative_evidence": str(negative_path),
            "rejected_rows": str(rejected_path),
            "validation": str(validation_path),
        },
        "validation": result.validation,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest["outputs"] | {"manifest": str(manifest_path)}


def copy_sample(path_or_url: str, output_path: Path, *, max_rows: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = iter_tsv_rows(path_or_url, max_rows=max_rows)
    try:
        first_no, first = next(rows)
    except StopIteration:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(first.keys()), delimiter="\t")
        writer.writeheader()
        writer.writerow(first)
        for _, row in rows:
            writer.writerow(row)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=INTACT_HUMAN_URL, help="MITAB27 positive input path/URL")
    parser.add_argument("--negative-input", default="", help="Optional MITAB27 negative input path/URL for side evidence")
    parser.add_argument("--node-root", default="", help="KG root containing nodes/protein.parquet for UniProt anti-join/mapping")
    parser.add_argument("--output-dir", default=".omoc/staging/intact-protein-interactions-current")
    parser.add_argument("--max-rows", type=int, default=None, help="Sample only first N positive MITAB rows")
    parser.add_argument("--negative-max-rows", type=int, default=None, help="Sample only first N negative rows")
    parser.add_argument("--feature", action="append", default=[], help="Feature kind=path_or_url; repeatable")
    parser.add_argument("--feature-max-rows", type=int, default=None)
    parser.add_argument("--source-dataset", default="intact_species_human_mitab27_current")
    parser.add_argument("--make-sample", type=int, default=0, help="Copy first N positive rows to output raw/sample_positive.tsv before building")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.make_sample:
        copy_sample(args.input, output / "raw" / "sample_positive.tsv", max_rows=args.make_sample)

    feature_paths: dict[str, str] = {}
    for item in args.feature:
        if "=" not in item:
            raise ValueError(f"--feature must be kind=path_or_url, got {item!r}")
        kind, path = item.split("=", 1)
        feature_paths[kind] = path
    feature_refs = load_feature_refs(feature_paths, max_rows=args.feature_max_rows) if feature_paths else {}
    mapping = load_uniprot_to_protein_id(args.node_root or None)

    positive_rows = list(iter_tsv_rows(args.input, max_rows=args.max_rows))
    if args.negative_input:
        # Build side negative evidence by appending rows with Negative forced true.
        negative_rows = []
        for n, row in iter_tsv_rows(args.negative_input, max_rows=args.negative_max_rows):
            row = dict(row)
            row["Negative"] = "true"
            negative_rows.append((n, row))
        rows = positive_rows + negative_rows
    else:
        rows = positive_rows

    result = build_from_mitab(
        rows,
        uniprot_to_protein=mapping,
        feature_refs_by_interaction=feature_refs,
        source_dataset=args.source_dataset,
    )
    outputs = write_outputs(result, output)
    print(json.dumps({"outputs": outputs, "validation": result.validation}, indent=2, sort_keys=True))
    return 0 if result.validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
