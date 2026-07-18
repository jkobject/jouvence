"""Phase 4 — OpenTargets Platform ingestion.

Downloads and processes OpenTargets Platform datasets into the Parquet edge/node
schema defined in ``kg_schema.py``.

Datasets handled
----------------
target       → nodes/gene.parquet             (Ensembl IDs + xrefs)
disease      → nodes/disease.parquet          (EFO IDs + xrefs)
drug         → nodes/molecule.parquet         (ChEMBL IDs + xrefs)
interaction  → edges/gene_interacts_gene.parquet / protein_interacts_protein.parquet by endpoint
evidence     → edges/disease_associated_gene.parquet
             → edges/molecule_treats_disease.parquet
             → edges/molecule_contraindicates_disease.parquet
             → edges/disease_involves_pathway.parquet
go           → nodes/pathway.parquet          (GO terms merged with Reactome)
             → edges/pathway_contains_gene.parquet
reactome     → nodes/pathway.parquet          (Reactome pathways)
             → edges/pathway_child_of_pathway.parquet
literature   → nodes/paper.parquet            (PubMed IDs)
indication   → edges/molecule_treats_disease.parquet
             → edges/molecule_contraindicates_disease.parquet

Usage
-----
    uv run python -m manage_db.ingest_opentargets \\
        --data-dir ./data \\
        --release latest \\
        [--datasets target disease drug interaction evidence go reactome literature indication]
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

try:
    from .kg_ids import normalize_disease_id, normalize_ontology_curie
    from .kg_schema import NODE_TYPES, Credibility, NodeType
except ImportError:
    from kg_ids import normalize_disease_id, normalize_ontology_curie  # type: ignore[no-redef]
    from kg_schema import NODE_TYPES, Credibility, NodeType  # type: ignore[no-redef]

from .credibility import EdgeEvidence, score_credibility

try:
    from . import kg_storage
except ImportError:  # pragma: no cover - script fallback
    import kg_storage  # type: ignore

try:
    from . import kg_evidence
except ImportError:  # pragma: no cover - script fallback
    import kg_evidence  # type: ignore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "OpenTargets"

# OpenTargets datatypeId → credibility score
DATATYPE_CREDIBILITY: dict[str, int] = {
    # Established / curated
    "known_drug":            Credibility.ESTABLISHED_FACT,
    "chembl":                Credibility.ESTABLISHED_FACT,
    "expression_atlas":      Credibility.ESTABLISHED_FACT,
    "eva":                   Credibility.ESTABLISHED_FACT,   # ClinVar via EVA
    "clingen":               Credibility.ESTABLISHED_FACT,
    "cancer_gene_census":    Credibility.ESTABLISHED_FACT,
    "orphanet":              Credibility.ESTABLISHED_FACT,
    "gene2phenotype":        Credibility.ESTABLISHED_FACT,
    "uniprot_variants":      Credibility.ESTABLISHED_FACT,
    "reactome":              Credibility.ESTABLISHED_FACT,
    # Multi-evidence / moderately supported
    "genetic_association":   Credibility.MULTI_EVIDENCE,
    "somatic_mutation":      Credibility.MULTI_EVIDENCE,
    "ot_genetics_portal":    Credibility.MULTI_EVIDENCE,
    "intogen":               Credibility.MULTI_EVIDENCE,
    "crispr_screen":         Credibility.MULTI_EVIDENCE,
    "l2g":                   Credibility.MULTI_EVIDENCE,
    "eva_somatic":           Credibility.MULTI_EVIDENCE,
    # Single / predicted evidence
    "europepmc":             Credibility.SINGLE_EVIDENCE,
    "phenodigm":             Credibility.SINGLE_EVIDENCE,
    "progeny":               Credibility.SINGLE_EVIDENCE,
    "slapenrich":            Credibility.SINGLE_EVIDENCE,
    "sysbio":                Credibility.SINGLE_EVIDENCE,
    "literature":            Credibility.SINGLE_EVIDENCE,
}

# Evidence datatypeId → canonical edge relation (gene-disease direction)
EVIDENCE_GENE_DISEASE_RELATIONS: set[str] = {
    "genetic_association",
    "somatic_mutation",
    "ot_genetics_portal",
    "intogen",
    "crispr_screen",
    "l2g",
    "eva",
    "eva_somatic",
    "clingen",
    "cancer_gene_census",
    "gene2phenotype",
    "orphanet",
    "uniprot_variants",
    "phenodigm",
    "literature",
    "europepmc",
    "sysbio",
    "expression_atlas",
}
EVIDENCE_DRUG_DISEASE_TYPES: set[str] = {"known_drug", "chembl", "cancer_biomarkers"}
EVIDENCE_PATHWAY_DISEASE_TYPES: set[str] = {"reactome", "progeny", "slapenrich", "affected_pathway"}

# Additional datatypeId credibility entries (discovered from real OT data)
DATATYPE_CREDIBILITY.update({
    "genetic_literature":  Credibility.SINGLE_EVIDENCE,
    "affected_pathway":    Credibility.MULTI_EVIDENCE,
    "animal_model":        Credibility.MULTI_EVIDENCE,
    "rna_expression":      Credibility.ESTABLISHED_FACT,
    "gene_burden":         Credibility.MULTI_EVIDENCE,
    "gwas_credible_sets":  Credibility.MULTI_EVIDENCE,
    "crispr":              Credibility.MULTI_EVIDENCE,
    "cancer_biomarkers":   Credibility.ESTABLISHED_FACT,
})

EVIDENCE_GENE_DISEASE_RELATIONS.update({
    "genetic_literature",
    "animal_model",
    "rna_expression",
    "gene_burden",
    "gwas_credible_sets",
    "crispr",
})

EVIDENCE_BACKED_VARIANT_DATATYPES: set[str] = {
    "genetic_association",
    "ot_genetics_portal",
    "gwas_credible_sets",
    "gene_burden",
    "eva",
    "eva_somatic",
    "clingen",
    "uniprot_variants",
    "somatic_mutation",
    "intogen",
}

VARIANT_EVIDENCE_ID_COLUMNS: tuple[str, ...] = (
    "variantId",
    "variantRsId",
    "variantRsIds",
    "rsId",
    "rsIds",
    "leadVariantId",
    "tagVariantId",
)

GWAS_CREDIBLE_SET_EVIDENCE_DIR = "evidence_gwas_credible_sets"
GWAS_EVIDENCE_COLUMNS: tuple[str, ...] = (
    "studyLocusId",
    "diseaseId",
    "datatypeId",
    "datasourceId",
    "score",
    "resourceScore",
    "targetId",
)
GWAS_CREDIBLE_SET_COLUMNS: tuple[str, ...] = (
    "studyLocusId",
    "variantId",
    "studyId",
    "studyType",
    "pValueMantissa",
    "pValueExponent",
    "beta",
    "standardError",
    "confidence",
    "finemappingMethod",
)
GWAS_L2G_COLUMNS: tuple[str, ...] = ("studyLocusId", "geneId", "score")


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _to_list(val) -> list:
    """Coerce a pandas/numpy array or None to a plain Python list."""
    if val is None:
        return []
    try:
        # numpy / pandas arrays: len() works but bool() raises on multi-element
        return list(val)
    except TypeError:
        return [val] if val else []


def _first_scalar(values) -> str | None:
    """Return the first non-empty scalar from a nested/list-like value."""
    if isinstance(values, str):
        text = values.strip()
        return text if text and text != "nan" else None
    for value in _to_list(values):
        if isinstance(value, dict):
            for key in ("variantId", "variantRsId", "rsId", "id"):
                nested = _first_scalar(value.get(key))
                if nested:
                    return nested
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text and text != "nan":
            return text
    return None


def _variant_id_from_evidence_row(row: pd.Series) -> str | None:
    """Extract a usable mutation ID from an OpenTargets evidence row."""
    for col in VARIANT_EVIDENCE_ID_COLUMNS:
        if col in row.index:
            variant_id = _first_scalar(row.get(col))
            if variant_id:
                return variant_id

    # Some OpenTargets genetics rows encode lead/tag variants inside nested
    # locus structs. Keep this intentionally conservative: only direct variant
    # identifiers are accepted, never target/gene IDs.
    for col in ("studyLocusId", "locus", "credibleSet", "credibleSets"):
        if col not in row.index:
            continue
        value = row.get(col)
        for entry in _to_list(value):
            if not isinstance(entry, dict):
                continue
            for key in VARIANT_EVIDENCE_ID_COLUMNS:
                variant_id = _first_scalar(entry.get(key))
                if variant_id:
                    return variant_id
    return None


# ---------------------------------------------------------------------------
# Parquet I/O helpers
# ---------------------------------------------------------------------------

def _read_parquet_dir(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read all .parquet files in *path* into one DataFrame."""
    files = sorted(path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
    frames: list[pd.DataFrame] = []
    for f in files:
        try:
            df = pd.read_parquet(f, columns=columns)
            frames.append(df)
        except Exception as exc:
            log.warning("Could not read %s: %s", f, exc)
    if not frames:
        raise RuntimeError(f"All parquet files in {path} failed to load")
    return pd.concat(frames, ignore_index=True)


def _read_parquet_dir_available(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read requested columns that are present in the dataset schema."""
    import pyarrow.parquet as pq

    files = sorted(path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
    schema_fields = {field.name for field in pq.read_schema(files[0])}
    available = [column for column in columns if column in schema_fields]
    return _read_parquet_dir(path, columns=available)


def _parquet_available_columns(path: Path, columns: list[str]) -> list[str]:
    """Return requested columns that are present in the first parquet schema."""
    import pyarrow.parquet as pq

    files = sorted(path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
    schema_fields = {field.name for field in pq.read_schema(files[0])}
    return [column for column in columns if column in schema_fields]


def _read_parquet_dir_chunked(
    path: Path,
    columns: list[str] | None = None,
    chunksize: int = 500_000,
) -> Iterator[pd.DataFrame]:
    """Yield chunks from all .parquet files in *path*."""
    import pyarrow.parquet as pq

    files = sorted(path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
    for f in files:
        try:
            pf = pq.ParquetFile(f)
            for batch in pf.iter_batches(batch_size=chunksize, columns=columns):
                yield batch.to_pandas()
        except Exception as exc:
            log.warning("Could not read %s: %s", f, exc)


def _save_edge_df(df: pd.DataFrame, root: kg_storage.KGRoot, relation: str) -> None:
    """Append edge DataFrame into the canonical Parquet store."""
    if df.empty:
        return
    kg_storage.write_edges(root, relation, df.reset_index(drop=True), mode="append")


def _save_node_df(df: pd.DataFrame, root: kg_storage.KGRoot, node_type: str) -> None:
    """Append node DataFrame into the canonical Parquet store."""
    if df.empty:
        return
    node_df = df.reset_index(drop=True).drop(columns=["node_type"], errors="ignore")
    info = NODE_TYPES[NodeType(node_type)]
    for col in info.xref_columns:
        if col not in node_df.columns:
            node_df[col] = None
    kg_storage.write_nodes(
        root,
        node_type,
        node_df,
        mode="append",
    )


def _normalize_uberon_id(value: str) -> str:
    if value.startswith("UBERON_"):
        return "UBERON:" + value.removeprefix("UBERON_")
    return value


def _normalize_mondo_id(value: str) -> str:
    return normalize_ontology_curie(value) or value


def _normalize_hp_id(value: str) -> str:
    return normalize_ontology_curie(value) or value


def _build_gene_to_protein_map(root: kg_storage.KGRoot) -> dict[str, list[str]]:
    """Return Ensembl gene ID → ENSP protein node IDs from registered proteins."""
    try:
        proteins = kg_storage.read_nodes(
            root,
            NodeType.PROTEIN.value,
            columns=["id", "ensembl_gene_id"],
        )
    except Exception as exc:
        log.info("No protein nodes available for gene→protein projection: %s", exc)
        return {}

    required = {"id", "ensembl_gene_id"}
    if proteins.empty or not required <= set(proteins.columns):
        return {}

    proteins = proteins[list(required)].dropna()
    proteins = proteins[
        proteins["id"].astype(str).str.startswith("ENSP")
        & proteins["ensembl_gene_id"].astype(str).str.startswith("ENSG")
    ]
    mapping: dict[str, list[str]] = {}
    for gene_id, protein_id in proteins[["ensembl_gene_id", "id"]].drop_duplicates().itertuples(index=False):
        mapping.setdefault(str(gene_id), []).append(str(protein_id))
    return mapping


def _write_chunk(df: pd.DataFrame, chunk_dir: Path) -> None:
    """Append *df* as a new numbered parquet file in *chunk_dir* (no read-back)."""
    if df.empty:
        return
    chunk_dir.mkdir(parents=True, exist_ok=True)
    n = len(list(chunk_dir.glob("*.parquet")))
    df.to_parquet(chunk_dir / f"{n:06d}.parquet", index=False)


def _finalize_chunks(
    chunk_dir: Path,
    write_fn,
    dedup_cols: list[str],
) -> int:
    """Concat chunk files, deduplicate, write via *write_fn*, then clean up."""
    import shutil

    files = sorted(chunk_dir.glob("*.parquet"))
    if not files:
        return 0
    combined = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    combined = combined.drop_duplicates(subset=dedup_cols, keep="first")
    write_fn(combined.reset_index(drop=True))
    shutil.rmtree(chunk_dir)
    return len(combined)


def _finalize_edge_chunks_streaming(
    chunk_dir: Path,
    root: kg_storage.KGRoot,
    relation: str,
    dedup_cols: list[str],
) -> int:
    """Stream chunked edge Parquets into one edge file without concat OOM."""
    import shutil
    import pyarrow as pa
    import pyarrow.parquet as pq

    files = sorted(chunk_dir.glob("*.parquet"))
    if not files:
        return 0

    root._ensure_dir("edges")
    out_path = root._edge_internal(relation)
    tmp_path = f"{out_path}.tmp"
    seen_hashes: set[int] = set()
    n_written = 0
    writer = None

    try:
        with root.fs.open(tmp_path, "wb") as fh:
            for file in files:
                df = pd.read_parquet(file)
                if df.empty:
                    continue
                df = df.drop_duplicates(subset=dedup_cols, keep="first")
                row_hashes = pd.util.hash_pandas_object(
                    df[dedup_cols],
                    index=False,
                ).astype("uint64")
                keep = []
                for row_hash in row_hashes:
                    key = int(row_hash)
                    if key in seen_hashes:
                        keep.append(False)
                    else:
                        seen_hashes.add(key)
                        keep.append(True)
                df = df.loc[keep].reset_index(drop=True)
                if df.empty:
                    continue

                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(fh, table.schema)
                table = table.cast(writer.schema, safe=False)
                writer.write_table(table)
                n_written += len(df)
            if writer is not None:
                writer.close()
                writer = None

        if n_written:
            if root.fs.exists(out_path):
                root.fs.rm(out_path)
            root.fs.mv(tmp_path, out_path)
        else:
            root.fs.rm(tmp_path)
    finally:
        if writer is not None:
            writer.close()
        if root.fs.exists(tmp_path):
            root.fs.rm(tmp_path)

    shutil.rmtree(chunk_dir)
    return n_written



def _finalize_node_chunks_streaming(
    chunk_dir: Path,
    root: kg_storage.KGRoot,
    node_type: str,
    dedup_cols: list[str],
) -> int:
    """Stream chunked node Parquets into one node file without concat OOM."""
    import shutil
    import pyarrow as pa
    import pyarrow.parquet as pq

    files = sorted(chunk_dir.glob("*.parquet"))
    if not files:
        return 0

    root._ensure_dir("nodes")
    out_path = root._node_internal(node_type)
    tmp_path = f"{out_path}.tmp"
    seen_hashes: set[int] = set()
    n_written = 0
    writer = None

    try:
        with root.fs.open(tmp_path, "wb") as fh:
            for file in files:
                df = pd.read_parquet(file)
                if df.empty:
                    continue
                df = df.drop_duplicates(subset=dedup_cols, keep="first")
                row_hashes = pd.util.hash_pandas_object(
                    df[dedup_cols],
                    index=False,
                ).astype("uint64")
                keep = []
                for row_hash in row_hashes:
                    key = int(row_hash)
                    if key in seen_hashes:
                        keep.append(False)
                    else:
                        seen_hashes.add(key)
                        keep.append(True)
                df = df.loc[keep].reset_index(drop=True)
                if df.empty:
                    continue
                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(fh, table.schema)
                table = table.cast(writer.schema, safe=False)
                writer.write_table(table)
                n_written += len(df)
            if writer is not None:
                writer.close()
                writer = None

        if n_written:
            if root.fs.exists(out_path):
                root.fs.rm(out_path)
            root.fs.mv(tmp_path, out_path)
        else:
            root.fs.rm(tmp_path)
    finally:
        if writer is not None:
            writer.close()
        if root.fs.exists(tmp_path):
            root.fs.rm(tmp_path)

    shutil.rmtree(chunk_dir)
    return n_written


# ---------------------------------------------------------------------------
# Edge construction helpers
# ---------------------------------------------------------------------------

def _make_edge(
    x_id: str,
    x_type: str,
    y_id: str,
    y_type: str,
    relation: str,
    display_relation: str,
    source: str,
    credibility: int,
    **extra,
) -> dict:
    row = {
        "x_id": x_id,
        "x_type": x_type,
        "y_id": y_id,
        "y_type": y_type,
        "relation": relation,
        "display_relation": display_relation,
        "source": source,
        "credibility": credibility,
    }
    row.update(extra)
    return row


def _credibility_from_score(score: float, datatype: str) -> int:
    """Combine OT score with datatype-based credibility."""
    return score_credibility([
        EdgeEvidence(
            source=f"opentargets:{datatype}",
            paper_id=None,
            author_group_key=None,
            raw_score=float(score) if score is not None else None,
            datatype=datatype,
        )
    ])


def _existing_node_ids(root: kg_storage.KGRoot, node_type: NodeType) -> set[str]:
    """Read existing node IDs for endpoint stub avoidance."""
    try:
        return set(
            kg_storage.read_nodes(root, node_type.value, columns=["id"])["id"].astype(str)
        )
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# 1. Target ingestion → gene nodes
# ---------------------------------------------------------------------------

def ingest_targets(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest OT target dataset → gene nodes.

    Returns number of gene nodes written.
    """
    target_path = ot_dir / "target"
    log.info("Loading target dataset from %s", target_path)

    df = _read_parquet_dir_available(
        target_path,
        columns=["id", "approvedSymbol", "approvedName", "biotype",
                 "proteinIds", "dbXrefs", "transcripts"],
    )
    log.info("  %d target rows", len(df))

    rows = []
    transcript_rows_by_id: dict[str, dict] = {}
    protein_rows_by_id: dict[str, dict] = {}
    gene_transcript_edges: list[dict] = []
    transcript_protein_edges: list[dict] = []
    for _, row in df.iterrows():
        gene_id = str(row["id"]).strip()
        if not gene_id.startswith("ENSG"):
            continue

        # Extract UniProt (prefer Swiss-Prot / reviewed; OT source = 'uniprot_swissprot')
        uniprot_id = None
        protein_ids = _to_list(row.get("proteinIds"))
        for p in protein_ids:
            if isinstance(p, dict):
                src = p.get("source", "")
                pid = p.get("id", "")
                if src == "uniprot_swissprot" and pid:
                    uniprot_id = pid
                    break
        if uniprot_id is None:
            for p in protein_ids:
                if isinstance(p, dict) and p.get("source", "").startswith("uniprot") and p.get("id"):
                    uniprot_id = p["id"]
                    break

        # Extract HGNC and NCBI gene IDs from dbXrefs list-of-structs
        hgnc_id = ncbi_gene_id = None
        db_xrefs = _to_list(row.get("dbXrefs"))
        for xref in db_xrefs:
                if not isinstance(xref, dict):
                    continue
                src = xref.get("source", "")
                xid = str(xref.get("id", "")).strip()
                if src == "HGNC" and not hgnc_id:
                    hgnc_id = xid
                elif src in ("NCBIGene", "EntrezGene") and not ncbi_gene_id:
                    ncbi_gene_id = xid

        rows.append({
            "id":            gene_id,
            "name":          str(row.get("approvedSymbol") or "").strip(),
            "description":   str(row.get("approvedName") or "").strip(),
            "biotype":       str(row.get("biotype") or "").strip(),
            "ncbi_gene_id":  ncbi_gene_id,
            "hgnc_id":       hgnc_id,
            "uniprot_id":    uniprot_id,
            "gene_name":     str(row.get("approvedSymbol") or "").strip(),
            "source":        SOURCE_NAME,
        })

        for transcript in _to_list(row.get("transcripts")):
            if not isinstance(transcript, dict):
                continue
            transcript_id = str(transcript.get("transcriptId") or "").strip()
            protein_id = str(transcript.get("translationId") or "").strip()
            if transcript_id.startswith("ENST"):
                transcript_rows_by_id[transcript_id] = {
                    "id": transcript_id,
                    "name": transcript_id,
                    "ensembl_gene_id": gene_id,
                    "protein_id": protein_id if protein_id.startswith("ENSP") else None,
                    "refseq_mrna": None,
                    "ccds_id": None,
                    "source": SOURCE_NAME,
                }
                gene_transcript_edges.append(_make_edge(
                    x_id=gene_id,
                    x_type=NodeType.GENE.value,
                    y_id=transcript_id,
                    y_type=NodeType.TRANSCRIPT.value,
                    relation="gene_has_transcript",
                    display_relation="has transcript",
                    source="OpenTargets/target",
                    credibility=Credibility.ESTABLISHED_FACT,
                    transcript_biotype=str(transcript.get("biotype") or "").strip(),
                ))
            if not protein_id.startswith("ENSP"):
                continue
            protein_rows_by_id[protein_id] = {
                "id": protein_id,
                "name": protein_id,
                "ensembl_gene_id": gene_id,
                "uniprot_id": str(transcript.get("uniprotId") or uniprot_id or "").strip() or None,
                "refseq_protein": None,
                "pdb_ids": None,
                "source": SOURCE_NAME,
            }
            if transcript_id.startswith("ENST"):
                transcript_protein_edges.append(_make_edge(
                    x_id=transcript_id,
                    x_type=NodeType.TRANSCRIPT.value,
                    y_id=protein_id,
                    y_type=NodeType.PROTEIN.value,
                    relation="transcript_encodes_protein",
                    display_relation="encodes protein",
                    source="OpenTargets/target",
                    credibility=Credibility.ESTABLISHED_FACT,
                ))

    gene_df = pd.DataFrame(rows)
    _save_node_df(gene_df, root, NodeType.GENE.value)
    if transcript_rows_by_id:
        transcript_df = pd.DataFrame(transcript_rows_by_id.values())
        _save_node_df(transcript_df, root, NodeType.TRANSCRIPT.value)
        log.info("  %d transcript nodes saved", len(transcript_df))
    if protein_rows_by_id:
        protein_df = pd.DataFrame(protein_rows_by_id.values())
        _save_node_df(protein_df, root, NodeType.PROTEIN.value)
        log.info("  %d protein nodes saved", len(protein_df))
    if gene_transcript_edges:
        _save_edge_df(pd.DataFrame(gene_transcript_edges), root, "gene_has_transcript")
        log.info("  %d gene→transcript edges saved", len(gene_transcript_edges))
    if transcript_protein_edges:
        _save_edge_df(pd.DataFrame(transcript_protein_edges), root, "transcript_encodes_protein")
        log.info("  %d transcript→protein edges saved", len(transcript_protein_edges))
    log.info("  %d gene nodes saved", len(gene_df))
    return len(gene_df)


def ingest_orthology(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest exact OpenTargets target homologues as gene→gene orthology edges.

    Source mapping is intentionally narrow and auditable:

    * input dataset: ``target``
    * input field: ``homologues`` (OpenTargets target records)
    * accepted rows: human query genes (``ENSG``) with homologue entries whose
      ``homologyType`` starts with ``ortholog_`` and ``isHighConfidence`` is
      true/``"1"``
    * rejected rows: within-human paralogues, other paralogues, missing target
      gene IDs, self edges, and non-Ensembl-gene targets

    The exporter also writes minimal endpoint gene stubs for accepted Ensembl
    gene IDs so temp-root validation can anti-join edges exactly.  It is
    not included in ``ALL_DATASETS``; run explicitly with ``--datasets orthology``
    after reviewing the source policy for a canonical promotion.
    """
    target_path = ot_dir / "target"
    log.info("Loading target homologues from %s", target_path)

    df = _read_parquet_dir_available(
        target_path,
        columns=["id", "approvedSymbol", "homologues"],
    )
    if "homologues" not in df.columns:
        raise ValueError("OpenTargets target dataset does not expose a 'homologues' column")

    endpoint_gene_rows: dict[str, dict] = {}
    edge_rows: list[dict] = []

    def _is_high_confidence(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        return text in {"1", "true", "t", "yes"}

    for _, row in df.iterrows():
        query_gene_id = str(row.get("id") or "").strip()
        if not query_gene_id.startswith("ENSG"):
            continue
        query_symbol = str(row.get("approvedSymbol") or "").strip()
        for homologue in _to_list(row.get("homologues")):
            if not isinstance(homologue, dict):
                continue
            homology_type = str(homologue.get("homologyType") or "").strip()
            if not homology_type.startswith("ortholog_"):
                continue
            if not _is_high_confidence(homologue.get("isHighConfidence")):
                continue
            target_gene_id = str(homologue.get("targetGeneId") or "").strip()
            if not target_gene_id.startswith("ENS") or target_gene_id == query_gene_id:
                continue

            target_symbol = str(homologue.get("targetGeneSymbol") or "").strip()
            species_id = str(homologue.get("speciesId") or "").strip()
            species_name = str(homologue.get("speciesName") or "").strip()
            endpoint_gene_rows[query_gene_id] = {
                "id": query_gene_id,
                "name": query_symbol or query_gene_id,
                "description": None,
                "biotype": None,
                "ncbi_gene_id": None,
                "hgnc_id": None,
                "uniprot_id": None,
                "gene_name": query_symbol or None,
                "source": "OpenTargets/target.homologues",
            }
            endpoint_gene_rows[target_gene_id] = {
                "id": target_gene_id,
                "name": target_symbol or target_gene_id,
                "description": f"{species_name} ortholog of {query_symbol or query_gene_id}" if species_name else None,
                "biotype": None,
                "ncbi_gene_id": None,
                "hgnc_id": None,
                "uniprot_id": None,
                "gene_name": target_symbol or None,
                "source": "OpenTargets/target.homologues",
            }
            edge_rows.append(_make_edge(
                x_id=query_gene_id,
                x_type=NodeType.GENE.value,
                y_id=target_gene_id,
                y_type=NodeType.GENE.value,
                relation="gene_ortholog_gene",
                display_relation="ortholog of",
                source="OpenTargets/target.homologues",
                credibility=Credibility.ESTABLISHED_FACT,
                homology_type=homology_type,
                species_id=species_id or None,
                species_name=species_name or None,
                is_high_confidence=True,
                query_percentage_identity=homologue.get("queryPercentageIdentity"),
                target_percentage_identity=homologue.get("targetPercentageIdentity"),
            ))

    if endpoint_gene_rows:
        _save_node_df(pd.DataFrame(endpoint_gene_rows.values()), root, NodeType.GENE.value)
    if edge_rows:
        edge_df = pd.DataFrame(edge_rows).drop_duplicates(
            subset=["x_id", "y_id", "relation"],
            keep="first",
        )
        _save_edge_df(edge_df, root, "gene_ortholog_gene")
    else:
        edge_df = pd.DataFrame()

    log.info("  %d orthology endpoint gene stubs saved", len(endpoint_gene_rows))
    log.info("  %d gene orthology edges saved", len(edge_df))
    return {"gene": len(endpoint_gene_rows), "gene_ortholog_gene": len(edge_df)}


# ---------------------------------------------------------------------------
# 2. Disease ingestion → disease nodes
# ---------------------------------------------------------------------------

def ingest_diseases(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest OT disease dataset → disease nodes.

    Returns number of disease nodes written.
    """
    disease_path = ot_dir / "disease"
    log.info("Loading disease dataset from %s", disease_path)

    df = _read_parquet_dir(
        disease_path,
        columns=["id", "name", "description", "dbXRefs", "parents",
                 "therapeuticAreas"],
    )
    log.info("  %d disease rows", len(df))

    rows = []
    for _, row in df.iterrows():
        efo_id = normalize_disease_id(row["id"]) or str(row["id"]).strip()

        # Cross-references (dbXRefs is a list of plain strings like 'MONDO:0000510')
        mondo_id = omim_id = doid_id = icd10_code = mesh_id = hp_id = None
        db_xrefs = _to_list(row.get("dbXRefs"))
        for xref in db_xrefs:
                xref_str = str(xref).strip()
                if xref_str.startswith("MONDO:"):
                    mondo_id = mondo_id or xref_str
                elif xref_str.startswith("OMIM:"):
                    omim_id = omim_id or xref_str.replace("OMIM:", "")
                elif xref_str.startswith("DOID:"):
                    doid_id = doid_id or xref_str
                elif xref_str.startswith("ICD10:"):
                    icd10_code = icd10_code or xref_str.replace("ICD10:", "")
                elif xref_str.startswith("MeSH:") or xref_str.startswith("MESH:"):
                    mesh_id = mesh_id or xref_str
                elif xref_str.startswith("HP:"):
                    hp_id = hp_id or xref_str

        rows.append({
            "id":           efo_id,
            "name":         str(row.get("name") or "").strip(),
            "description":  str(row.get("description") or "").strip(),
            "mondo_id":     mondo_id,
            "omim_id":      omim_id,
            "doid_id":      doid_id,
            "icd10_code":   icd10_code,
            "mesh_id":      mesh_id,
            "hp_id":        hp_id,
            "source":       SOURCE_NAME,
        })

    disease_df = pd.DataFrame(rows)
    _save_node_df(disease_df, root, NodeType.DISEASE.value)

    # Also save disease hierarchy edges (parents)
    hier_rows = []
    for _, row in df.iterrows():
        child_id = normalize_disease_id(row["id"]) or str(row["id"]).strip()
        for parent_id in _to_list(row.get("parents")):
                parent_id = normalize_disease_id(parent_id) or str(parent_id).strip()
                if parent_id and parent_id != child_id:
                    hier_rows.append(_make_edge(
                        x_id=child_id, x_type=NodeType.DISEASE.value,
                        y_id=parent_id, y_type=NodeType.DISEASE.value,
                        relation="disease_subtype_of_disease",
                        display_relation="subtype of",
                        source=SOURCE_NAME,
                        credibility=Credibility.ESTABLISHED_FACT,
                    ))

    if hier_rows:
        _save_edge_df(pd.DataFrame(hier_rows), root, "disease_subtype_of_disease")

    log.info("  %d disease nodes, %d hierarchy edges saved", len(disease_df), len(hier_rows))
    return len(disease_df)


# ---------------------------------------------------------------------------
# 3. Drug / molecule ingestion → molecule nodes
# ---------------------------------------------------------------------------

def ingest_drugs(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest OT drug/molecule dataset → molecule nodes.

    Returns number of molecule nodes written.
    """
    # OT 24.x+ uses 'drug_molecule'; older releases used 'molecule' or 'drug'
    for _candidate in ("drug_molecule", "molecule", "drug"):
        drug_path = ot_dir / _candidate
        if drug_path.exists():
            break
    else:
        log.warning("No molecule/drug dataset found in %s", ot_dir)
        return 0

    log.info("Loading drug dataset from %s", drug_path)

    df = _read_parquet_dir_available(
        drug_path,
        columns=[
            "id",
            "name",
            "description",
            "inchiKey",
            "canonicalSmiles",
            "drugType",
            "isApproved",
            "maximumClinicalTrialPhase",
            "maximumClinicalStage",
            "hasBeenWithdrawn",
            "blackBoxWarning",
            "crossReferences",
        ],
    )
    log.info("  %d molecule rows", len(df))

    rows = []
    for _, row in df.iterrows():
        chembl_id = str(row["id"]).strip()
        if not chembl_id.startswith("CHEMBL"):
            continue

        # crossReferences is a list of {source, ids} structs (not a dict)
        drugbank_id = pubchem_cid = cas_rn = None
        for xref in _to_list(row.get("crossReferences")):
            if not isinstance(xref, dict):
                continue
            src = str(xref.get("source") or "").lower()
            ids = _to_list(xref.get("ids"))
            first_id = str(ids[0]) if ids else None
            if src == "drugbank" and not drugbank_id:
                drugbank_id = first_id
            elif src in ("pubchem", "pubchemcid", "pubchem_cid") and not pubchem_cid:
                pubchem_cid = first_id
            elif src in ("cas", "cas_rn") and not cas_rn:
                cas_rn = first_id

        rows.append({
            "id":                          chembl_id,
            "name":                        str(row.get("name") or "").strip(),
            "description":                 str(row.get("description") or "").strip(),
            "drug_type":                   str(row.get("drugType") or "").strip(),
            "is_approved":                 bool(row.get("isApproved") or False),
            "max_clinical_trial_phase":    row.get("maximumClinicalTrialPhase")
                                            if row.get("maximumClinicalTrialPhase") is not None
                                            else row.get("maximumClinicalStage"),
            "has_been_withdrawn":          bool(row.get("hasBeenWithdrawn") or False),
            "black_box_warning":           bool(row.get("blackBoxWarning") or False),
            "inchikey":                    str(row.get("inchiKey") or "").strip() or None,
            "drugbank_id":                 drugbank_id,
            "pubchem_cid":                 pubchem_cid,
            "cas_rn":                      cas_rn,
            "smiles":                      str(row.get("canonicalSmiles") or "").strip() or None,
            "source":                      SOURCE_NAME,
        })

    mol_df = pd.DataFrame(rows)
    _save_node_df(mol_df, root, NodeType.MOLECULE.value)
    log.info("  %d molecule nodes saved", len(mol_df))
    return len(mol_df)


# ---------------------------------------------------------------------------
# 4. Interaction ingestion → protein_interacts_protein edges
# ---------------------------------------------------------------------------

def ingest_interactions(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest OT interaction dataset → protein_interacts_protein edges.

    Returns number of edges written.
    """
    int_path = ot_dir / "interaction"
    if not int_path.exists():
        log.warning("'interaction' dataset not found in %s", ot_dir)
        return 0

    log.info("Loading interaction dataset from %s", int_path)

    chunk_dir = out_dir / ".chunks" / "protein_interacts_protein"
    n_chunks = 0

    for chunk in _read_parquet_dir_chunked(
        int_path,
        columns=["targetA", "targetB", "intA", "intB", "scoring", "sourceDatabase"],
        chunksize=500_000,
    ):
        rows = []
        for _, row in chunk.iterrows():
            # intA/intB are UniProt accessions; targetA/B are Ensembl IDs
            prot_a = str(row.get("intA") or "").strip()
            prot_b = str(row.get("intB") or "").strip()
            if not prot_a or not prot_b:
                continue
            # Skip self-loops
            if prot_a == prot_b:
                continue
            # Canonical ordering to deduplicate A-B vs B-A
            if prot_a > prot_b:
                prot_a, prot_b = prot_b, prot_a

            # 'scoring' is the field name in OT interaction dataset (not 'score')
            score = float(row.get("scoring") or 0.0)
            source_db = str(row.get("sourceDatabase") or SOURCE_NAME).strip()
            cred = _credibility_from_score(score, "genetic_association")

            rows.append(_make_edge(
                x_id=prot_a, x_type=NodeType.PROTEIN.value,
                y_id=prot_b, y_type=NodeType.PROTEIN.value,
                relation="protein_interacts_protein",
                display_relation="interacts with",
                source=f"OpenTargets/{source_db}",
                credibility=cred,
                score=round(score, 4),
            ))
        if rows:
            _write_chunk(pd.DataFrame(rows), chunk_dir)
            n_chunks += len(rows)

    n_written = _finalize_chunks(
        chunk_dir,
        lambda df: kg_storage.write_edges(
            root,
            "protein_interacts_protein",
            df,
            mode="overwrite",
        ),
        dedup_cols=["x_id", "y_id", "relation", "source"],
    )
    log.info("  %d PPI edges saved", n_written)
    return n_written


# ---------------------------------------------------------------------------
# 5. Evidence ingestion → disease_associated_gene + drug edges
# ---------------------------------------------------------------------------

def ingest_evidence(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest OT evidence datasets (evidence_*) into multiple edge Parquets.

    OT splits evidence into ~20 separate directories named evidence_<source>.
    Returns dict of {relation: count}.
    """
    import pyarrow.parquet as _pq

    ev_dirs = sorted(ot_dir.glob("evidence_*"))
    if not ev_dirs:
        log.warning("No 'evidence_*' datasets found in %s", ot_dir)
        return {}

    log.info("Found %d evidence directories", len(ev_dirs))

    chunks_base = out_dir / ".chunks"
    gd_chunks  = chunks_base / "disease_associated_gene"
    dd_chunks  = chunks_base / "molecule_treats_disease"
    pd_chunks  = chunks_base / "disease_involves_pathway"
    gd_evidence_chunks = chunks_base / "evidence_disease_associated_gene"
    pd_evidence_chunks = chunks_base / "evidence_disease_involves_pathway"
    seen_genes: set[str] = set()
    seen_pathways: dict[str, str | None] = {}

    BASE_COLS = ["targetId", "diseaseId", "datatypeId", "datasourceId", "score"]

    for ev_path in ev_dirs:
        # Determine if this directory has a drugId column
        parquet_files = list(ev_path.glob("*.parquet"))
        if not parquet_files:
            continue
        try:
            schema_fields = {f.name for f in _pq.read_schema(parquet_files[0])}
        except Exception:
            schema_fields = set()

        optional_cols = [
            col
            for col in ("drugId", "pathways", "reactionId", "reactionName")
            if col in schema_fields
        ]
        cols = BASE_COLS + optional_cols

        log.info("  Processing %s (%d files)", ev_path.name, len(parquet_files))
        for chunk in _read_parquet_dir_chunked(ev_path, columns=cols, chunksize=500_000):
            gene_disease_rows: list[dict] = []
            drug_disease_rows: list[dict] = []
            pathway_disease_rows: list[dict] = []
            gene_disease_evidence_rows: list[dict] = []
            pathway_disease_evidence_rows: list[dict] = []

            for _, row in chunk.iterrows():
                target_id  = str(row.get("targetId") or "").strip()
                disease_id = normalize_disease_id(row.get("diseaseId")) or ""
                dtype      = str(row.get("datatypeId") or "").strip()
                dsource    = str(row.get("datasourceId") or dtype).strip()
                score      = float(row.get("score") or 0.0)
                cred       = _credibility_from_score(score, dtype)

                def _evidence_row(relation: str, x_id: str, x_type: str, y_id: str, y_type: str, *, suffix: str = "") -> dict:
                    base = f"{dsource}:{disease_id}:{target_id}:{dtype}"
                    if suffix:
                        base = f"{base}:{suffix}"
                    return {
                        "relation": relation,
                        "x_id": x_id,
                        "x_type": x_type,
                        "y_id": y_id,
                        "y_type": y_type,
                        "evidence_type": "database_record",
                        "source": "OpenTargets",
                        "source_dataset": ev_path.name,
                        "source_record_id": base,
                        "paper_id": "",
                        "dataset_id": "",
                        "study_id": "",
                        "evidence_score": round(score, 4),
                        "direction": "",
                        "predicate": dtype,
                        "release": "26.03",
                    }

                if not target_id or not disease_id:
                    continue

                # ── Drug-disease evidence ────────────────────────────────────
                if dtype in EVIDENCE_DRUG_DISEASE_TYPES:
                    # OT uses top-level drugId field (not nested drug.id)
                    drug_id = str(row.get("drugId") or "").strip()
                    if not drug_id:
                        # fallback: some cancer_biomarkers rows have targetId as drug
                        drug_id = target_id if target_id.startswith("CHEMBL") else ""
                    if not drug_id:
                        continue

                    drug_disease_rows.append(_make_edge(
                        x_id=drug_id,
                        x_type=NodeType.MOLECULE.value,
                        y_id=disease_id,
                        y_type=NodeType.DISEASE.value,
                        relation="molecule_treats_disease",
                        display_relation="indication",
                        source=f"OpenTargets/{dsource}",
                        credibility=cred,
                        score=round(score, 4),
                    ))

                # ── Pathway-disease evidence ─────────────────────────────────
                elif dtype in EVIDENCE_PATHWAY_DISEASE_TYPES:
                    pathway_ids: list[tuple[str, str | None]] = []
                    for pathway in _to_list(row.get("pathways")):
                        if isinstance(pathway, dict):
                            pathway_id = str(pathway.get("id") or "").strip()
                            pathway_name = str(pathway.get("name") or "").strip() or None
                        else:
                            pathway_id = str(pathway or "").strip()
                            pathway_name = None
                        if pathway_id.startswith("R-HSA-"):
                            pathway_ids.append((pathway_id, pathway_name))

                    reaction_id = str(row.get("reactionId") or "").strip()
                    if reaction_id.startswith("R-HSA-"):
                        reaction_name = str(row.get("reactionName") or "").strip() or None
                        pathway_ids.append((reaction_id, reaction_name))

                    pathway_id = target_id
                    if not pathway_ids and pathway_id.startswith("R-HSA-"):
                        pathway_ids.append((pathway_id, None))

                    for pathway_id, pathway_name in pathway_ids:
                        seen_pathways.setdefault(pathway_id, pathway_name)
                        pathway_disease_rows.append(_make_edge(
                            x_id=pathway_id, x_type=NodeType.PATHWAY.value,
                            y_id=disease_id, y_type=NodeType.DISEASE.value,
                            relation="disease_involves_pathway",
                            display_relation="involved in disease",
                            source=f"OpenTargets/{dsource}",
                            credibility=cred,
                            score=round(score, 4),
                            pathway_name=pathway_name,
                        ))
                        pathway_disease_evidence_rows.append(_evidence_row(
                            "disease_involves_pathway",
                            pathway_id,
                            NodeType.PATHWAY.value,
                            disease_id,
                            NodeType.DISEASE.value,
                            suffix=pathway_id,
                        ))
                    if target_id.startswith("ENSG"):
                        seen_genes.add(target_id)
                        gene_disease_rows.append(_make_edge(
                            x_id=target_id, x_type=NodeType.GENE.value,
                            y_id=disease_id, y_type=NodeType.DISEASE.value,
                            relation="disease_associated_gene",
                            display_relation="associated disease",
                            source=f"OpenTargets/{dsource}",
                            credibility=cred,
                            score=round(score, 4),
                        ))
                        gene_disease_evidence_rows.append(_evidence_row(
                            "disease_associated_gene",
                            target_id,
                            NodeType.GENE.value,
                            disease_id,
                            NodeType.DISEASE.value,
                        ))

                # ── Gene-disease evidence ────────────────────────────────────
                elif dtype in EVIDENCE_GENE_DISEASE_RELATIONS:
                    if target_id.startswith("ENSG"):
                        seen_genes.add(target_id)
                        gene_disease_rows.append(_make_edge(
                            x_id=target_id, x_type=NodeType.GENE.value,
                            y_id=disease_id, y_type=NodeType.DISEASE.value,
                            relation="disease_associated_gene",
                            display_relation="associated disease",
                            source=f"OpenTargets/{dsource}",
                            credibility=cred,
                            score=round(score, 4),
                        ))
                        gene_disease_evidence_rows.append(_evidence_row(
                            "disease_associated_gene",
                            target_id,
                            NodeType.GENE.value,
                            disease_id,
                            NodeType.DISEASE.value,
                        ))
                else:
                    # Unknown datatype — emit as gene-disease if IDs look right
                    if target_id.startswith("ENSG"):
                        seen_genes.add(target_id)
                        gene_disease_rows.append(_make_edge(
                            x_id=target_id, x_type=NodeType.GENE.value,
                            y_id=disease_id, y_type=NodeType.DISEASE.value,
                            relation="disease_associated_gene",
                            display_relation="associated disease",
                            source=f"OpenTargets/{dsource}",
                            credibility=Credibility.SINGLE_EVIDENCE,
                            score=round(score, 4),
                        ))
                        gene_disease_evidence_rows.append(_evidence_row(
                            "disease_associated_gene",
                            target_id,
                            NodeType.GENE.value,
                            disease_id,
                            NodeType.DISEASE.value,
                        ))

            # Flush each chunk's rows immediately to temp files
            if gene_disease_rows:
                _write_chunk(pd.DataFrame(gene_disease_rows), gd_chunks)
            if drug_disease_rows:
                _write_chunk(pd.DataFrame(drug_disease_rows), dd_chunks)
            if pathway_disease_rows:
                _write_chunk(pd.DataFrame(pathway_disease_rows), pd_chunks)
            if gene_disease_evidence_rows:
                _write_chunk(pd.DataFrame(gene_disease_evidence_rows), gd_evidence_chunks)
            if pathway_disease_evidence_rows:
                _write_chunk(pd.DataFrame(pathway_disease_evidence_rows), pd_evidence_chunks)

    dedup_edge = ["x_id", "y_id", "relation", "source"]
    counts: dict[str, int] = {}
    if seen_genes:
        try:
            existing_gene_ids = set(
                kg_storage.read_nodes(root, NodeType.GENE.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_gene_ids = set()
        missing_gene_ids = sorted(seen_genes - existing_gene_ids)
        if missing_gene_ids:
            kg_storage.write_nodes(
                root,
                NodeType.GENE.value,
                pd.DataFrame(
                    {
                        "id": gene_id,
                        "ncbi_gene_id": None,
                        "hgnc_id": None,
                        "uniprot_id": None,
                        "gene_name": None,
                        "name": gene_id,
                        "source": "OpenTargets/evidence",
                    }
                    for gene_id in missing_gene_ids
                ),
                mode="append",
            )
            log.info("  added %d evidence-only gene stubs", len(missing_gene_ids))
    if seen_pathways:
        try:
            existing_pathway_ids = set(
                kg_storage.read_nodes(root, NodeType.PATHWAY.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_pathway_ids = set()
        missing_pathway_ids = sorted(set(seen_pathways) - existing_pathway_ids)
        if missing_pathway_ids:
            kg_storage.write_nodes(
                root,
                NodeType.PATHWAY.value,
                pd.DataFrame(
                    {
                        "id": pathway_id,
                        "go_id": None,
                        "reactome_id": pathway_id,
                        "kegg_id": None,
                        "name": seen_pathways.get(pathway_id) or pathway_id,
                        "source": "OpenTargets/evidence",
                    }
                    for pathway_id in missing_pathway_ids
                ),
                mode="append",
            )
            log.info("  added %d evidence-only pathway stubs", len(missing_pathway_ids))
    n = _finalize_chunks(
        gd_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "disease_associated_gene",
            df,
            mode="append",
        ),
        dedup_edge,
    )
    if n: counts["disease_associated_gene"] = n
    _finalize_chunks(
        gd_evidence_chunks,
        lambda df: kg_evidence.write_evidence(
            root,
            "disease_associated_gene",
            df,
            mode="append",
        ),
        ["relation", "x_id", "y_id", "source_record_id"],
    )
    n = _finalize_chunks(
        dd_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "molecule_treats_disease",
            df,
            mode="append",
        ),
        dedup_edge,
    )
    if n: counts["molecule_treats_disease"] = n
    n = _finalize_chunks(
        pd_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "disease_involves_pathway",
            df,
            mode="append",
        ),
        dedup_edge,
    )
    if n: counts["disease_involves_pathway"] = n
    _finalize_chunks(
        pd_evidence_chunks,
        lambda df: kg_evidence.write_evidence(
            root,
            "disease_involves_pathway",
            df,
            mode="append",
        ),
        ["relation", "x_id", "y_id", "source_record_id"],
    )

    log.info("  Evidence edges: %s", counts)
    return counts


# ---------------------------------------------------------------------------
# 9. Indication ingestion → molecule_treats/contraindicates_disease
# ---------------------------------------------------------------------------

def ingest_indication(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> tuple[int, int]:
    """Ingest OT indication dataset (EMA/FDA approved indications).

    Returns (n_indication_edges, n_contraindication_edges).
    """
    ind_path = ot_dir / "drug_indication"
    if not ind_path.exists():
        log.warning("'drug_indication' dataset not found in %s — skipping", ot_dir)
        return 0, 0

    log.info("Loading drug_indication dataset from %s", ind_path)

    df = _read_parquet_dir(
        ind_path,
        columns=["id", "approvedIndications", "indications"],
    )
    log.info("  %d indication rows", len(df))

    treat_rows: list[dict] = []
    contra_rows: list[dict] = []

    for _, row in df.iterrows():
        chembl_id = str(row["id"]).strip()
        if not chembl_id.startswith("CHEMBL"):
            continue

        # approvedIndications: list of disease EFO IDs
        approved = _to_list(row.get("approvedIndications"))
        for disease_id in approved:
                disease_id = normalize_disease_id(disease_id) or ""
                if disease_id:
                    treat_rows.append(_make_edge(
                        x_id=chembl_id, x_type=NodeType.MOLECULE.value,
                        y_id=disease_id, y_type=NodeType.DISEASE.value,
                        relation="molecule_treats_disease",
                        display_relation="approved indication",
                        source=f"OpenTargets/indication",
                        credibility=Credibility.ESTABLISHED_FACT,
                    ))

        # indications: list of dicts with {disease: "<EFO_ID>", maxPhaseForIndication, ...}
        # (disease is a plain string EFO/MONDO ID, not a nested dict)
        for ind in _to_list(row.get("indications")):
                if not isinstance(ind, dict):
                    continue
                disease_id = normalize_disease_id(ind.get("disease")) or ""
                max_phase = ind.get("maxPhaseForIndication") or 0
                if not disease_id:
                    continue

                cred = (
                    Credibility.ESTABLISHED_FACT if max_phase >= 4
                    else Credibility.MULTI_EVIDENCE if max_phase >= 3
                    else Credibility.SINGLE_EVIDENCE
                )
                treat_rows.append(_make_edge(
                    x_id=chembl_id, x_type=NodeType.MOLECULE.value,
                    y_id=disease_id, y_type=NodeType.DISEASE.value,
                    relation="molecule_treats_disease",
                    display_relation=f"indication (phase {max_phase})",
                    source=f"OpenTargets/indication",
                    credibility=cred,
                    max_phase=max_phase,
                ))

    if treat_rows:
        _save_edge_df(pd.DataFrame(treat_rows), root, "molecule_treats_disease")
    if contra_rows:
        _save_edge_df(pd.DataFrame(contra_rows), root, "molecule_contraindicates_disease")

    log.info("  %d indication edges, %d contraindication edges",
             len(treat_rows), len(contra_rows))
    return len(treat_rows), len(contra_rows)


# ---------------------------------------------------------------------------
# 10. mechanismOfAction → molecule_targets_gene edges
# ---------------------------------------------------------------------------

def ingest_mechanism_of_action(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest OT mechanismOfAction dataset → molecule_targets_gene edges.

    Returns number of edges written.
    """
    moa_path = ot_dir / "drug_mechanism_of_action"
    if not moa_path.exists():
        log.warning("'drug_mechanism_of_action' dataset not found in %s — skipping", ot_dir)
        return 0

    log.info("Loading drug_mechanism_of_action dataset from %s", moa_path)

    df = _read_parquet_dir(
        moa_path,
        columns=["chemblIds", "targetName", "targets", "actionType",
                 "mechanismOfAction"],
    )
    log.info("  %d MoA rows", len(df))

    edge_rows: list[dict] = []

    for _, row in df.iterrows():
        chembl_ids = _to_list(row.get("chemblIds"))
        targets    = _to_list(row.get("targets"))
        action     = str(row.get("actionType") or "").strip()
        moa_label  = str(row.get("mechanismOfAction") or "").strip()

        for chembl_id in chembl_ids:
            chembl_id = str(chembl_id or "").strip()
            if not chembl_id.startswith("CHEMBL"):
                continue

            for target in targets:
                if isinstance(target, dict):
                    gene_id = str(target.get("id") or "").strip()
                else:
                    gene_id = str(target or "").strip()

                if not gene_id.startswith("ENSG"):
                    continue

                # Emit gene-level edge (Ensembl); protein resolution is deferred
                edge_rows.append(_make_edge(
                    x_id=chembl_id, x_type=NodeType.MOLECULE.value,
                    y_id=gene_id,   y_type=NodeType.GENE.value,
                    relation="molecule_targets_gene",
                    display_relation=moa_label or action or "targets",
                    source=SOURCE_NAME,
                    credibility=Credibility.ESTABLISHED_FACT,
                    action_type=action,
                ))

    if edge_rows:
        _save_edge_df(pd.DataFrame(edge_rows), root, "molecule_targets_gene")
    log.info("  %d molecule→gene (MoA) edges saved", len(edge_rows))
    return len(edge_rows)


# ---------------------------------------------------------------------------
# 11. Target essentiality → cell-line nodes + DepMap context edges
# ---------------------------------------------------------------------------

def _target_essentiality_dataset_id() -> str:
    return "OpenTargets:target_essentiality:26.03"


def ingest_target_essentiality(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest OpenTargets DepMap target essentiality context.

    Source: ``target_essentiality``. This conservatively extracts only explicit
    cellular-model identifiers and endpoint IDs present in the source rows.
    It does not infer Cellosaurus IDs or enhancer IDs.
    """

    te_dir = ot_dir / "target_essentiality"
    if not te_dir.exists():
        raise FileNotFoundError(te_dir)

    chunks_base = out_dir / ".chunks" / "target_essentiality"
    cell_line_chunks = chunks_base / "cell_line"
    expr_chunks = chunks_base / "cell_line_expresses_gene"
    protein_expr_chunks = chunks_base / "cell_line_expresses_protein"
    tissue_chunks = chunks_base / "cell_line_derived_from_tissue"
    disease_chunks = chunks_base / "cell_line_associated_disease"
    dataset_cell_line_chunks = chunks_base / "dataset_contains_cell_line"
    dataset_gene_chunks = chunks_base / "dataset_contains_gene"
    dataset_tissue_chunks = chunks_base / "dataset_contains_tissue"
    dataset_disease_chunks = chunks_base / "dataset_contains_disease"

    dataset_id = _target_essentiality_dataset_id()
    kg_storage.write_nodes(
        root,
        NodeType.DATASET.value,
        pd.DataFrame([
            {
                "id": dataset_id,
                "name": "OpenTargets Target - DepMap essentiality 26.03",
                "source": "OpenTargets/target_essentiality",
            }
        ]),
        mode="append",
    )

    seen_cell_lines: set[str] = set()
    gene_to_proteins = _build_gene_to_protein_map(root)

    for chunk in _read_parquet_dir_chunked(
        te_dir,
        columns=["id", "geneEssentiality"],
        chunksize=25_000,
    ):
        cell_line_rows: list[dict[str, object]] = []
        expr_rows: list[dict[str, object]] = []
        protein_expr_rows: list[dict[str, object]] = []
        tissue_rows: list[dict[str, object]] = []
        disease_rows: list[dict[str, object]] = []
        dataset_cell_line_rows: list[dict[str, object]] = []
        dataset_gene_rows: list[dict[str, object]] = []
        dataset_tissue_rows: list[dict[str, object]] = []
        dataset_disease_rows: list[dict[str, object]] = []

        for _, row in chunk.iterrows():
            gene_id = str(row.get("id") or "").strip()
            if not gene_id.startswith("ENSG"):
                continue
            dataset_gene_rows.append(_make_edge(
                x_id=dataset_id,
                x_type=NodeType.DATASET.value,
                y_id=gene_id,
                y_type=NodeType.GENE.value,
                relation="dataset_contains_gene",
                display_relation="contains gene",
                source="OpenTargets/target_essentiality",
                credibility=Credibility.ESTABLISHED_FACT,
            ))

            for essentiality in _to_list(row.get("geneEssentiality")):
                if not isinstance(essentiality, dict):
                    continue
                is_essential = essentiality.get("isEssential")
                for depmap in _to_list(essentiality.get("depMapEssentiality")):
                    if not isinstance(depmap, dict):
                        continue
                    tissue_id = normalize_ontology_curie(depmap.get("tissueId")) or ""
                    tissue_name = str(depmap.get("tissueName") or "").strip()
                    if tissue_id.startswith("UBERON:"):
                        dataset_tissue_rows.append(_make_edge(
                            x_id=dataset_id,
                            x_type=NodeType.DATASET.value,
                            y_id=tissue_id,
                            y_type=NodeType.TISSUE.value,
                            relation="dataset_contains_tissue",
                            display_relation="contains tissue",
                            source="OpenTargets/target_essentiality",
                            credibility=Credibility.ESTABLISHED_FACT,
                        ))

                    for screen in _to_list(depmap.get("screens")):
                        if not isinstance(screen, dict):
                            continue
                        depmap_id = str(screen.get("depmapId") or "").strip()
                        if not depmap_id:
                            continue
                        cell_line_id = depmap_id
                        cell_line_name = str(screen.get("cellLineName") or "").strip()
                        disease_id = normalize_disease_id(screen.get("diseaseCellLineId")) or ""
                        # OpenTargets/DepMap often stores SIDM cell-model IDs
                        # in diseaseCellLineId. SIDM is not a disease ontology;
                        # emitting it as a disease endpoint creates true dangling
                        # KG edges. Keep only ontology-backed disease CURIEs.
                        if disease_id and not disease_id.startswith(("EFO:", "MONDO:", "Orphanet:", "HP:", "DOID:")):
                            disease_id = ""
                        gene_effect = screen.get("geneEffect")
                        expression = screen.get("expression")

                        if cell_line_id not in seen_cell_lines:
                            seen_cell_lines.add(cell_line_id)
                            cell_line_rows.append({
                                "id": cell_line_id,
                                "ccle_name": cell_line_name or None,
                                "cosmic_id": None,
                                "efo_id": disease_id or None,
                                "name": cell_line_name or cell_line_id,
                                "source": "OpenTargets/target_essentiality",
                            })
                        dataset_cell_line_rows.append(_make_edge(
                            x_id=dataset_id,
                            x_type=NodeType.DATASET.value,
                            y_id=cell_line_id,
                            y_type=NodeType.CELL_LINE.value,
                            relation="dataset_contains_cell_line",
                            display_relation="contains cell line",
                            source="OpenTargets/target_essentiality",
                            credibility=Credibility.ESTABLISHED_FACT,
                        ))

                        expr_rows.append(_make_edge(
                            x_id=cell_line_id,
                            x_type=NodeType.CELL_LINE.value,
                            y_id=gene_id,
                            y_type=NodeType.GENE.value,
                            relation="cell_line_expresses_gene",
                            display_relation="expresses gene",
                            source="OpenTargets/DepMap",
                            credibility=Credibility.ESTABLISHED_FACT,
                            gene_effect=gene_effect,
                            expression=expression,
                            is_essential=is_essential,
                        ))
                        for protein_id in gene_to_proteins.get(gene_id, []):
                            protein_expr_rows.append(_make_edge(
                                x_id=cell_line_id,
                                x_type=NodeType.CELL_LINE.value,
                                y_id=protein_id,
                                y_type=NodeType.PROTEIN.value,
                                relation="cell_line_expresses_protein",
                                display_relation="expresses protein",
                                source="OpenTargets/DepMap;projected_via_protein_node_xref",
                                credibility=Credibility.ESTABLISHED_FACT,
                                gene_id=gene_id,
                                gene_effect=gene_effect,
                                expression=expression,
                                is_essential=is_essential,
                            ))

                        if tissue_id.startswith("UBERON:"):
                            tissue_rows.append(_make_edge(
                                x_id=cell_line_id,
                                x_type=NodeType.CELL_LINE.value,
                                y_id=tissue_id,
                                y_type=NodeType.TISSUE.value,
                                relation="cell_line_derived_from_tissue",
                                display_relation="derived from tissue",
                                source="OpenTargets/DepMap",
                                credibility=Credibility.ESTABLISHED_FACT,
                                tissue_name=tissue_name,
                            ))

                        if disease_id:
                            disease_rows.append(_make_edge(
                                x_id=cell_line_id,
                                x_type=NodeType.CELL_LINE.value,
                                y_id=disease_id,
                                y_type=NodeType.DISEASE.value,
                                relation="cell_line_associated_disease",
                                display_relation="associated disease",
                                source="OpenTargets/DepMap",
                                credibility=Credibility.ESTABLISHED_FACT,
                                disease_from_source=screen.get("diseaseFromSource"),
                            ))
                            dataset_disease_rows.append(_make_edge(
                                x_id=dataset_id,
                                x_type=NodeType.DATASET.value,
                                y_id=disease_id,
                                y_type=NodeType.DISEASE.value,
                                relation="dataset_contains_disease",
                                display_relation="contains disease",
                                source="OpenTargets/target_essentiality",
                                credibility=Credibility.ESTABLISHED_FACT,
                            ))

        for df, chunk_dir in [
            (pd.DataFrame(cell_line_rows), cell_line_chunks),
            (pd.DataFrame(expr_rows), expr_chunks),
            (pd.DataFrame(protein_expr_rows), protein_expr_chunks),
            (pd.DataFrame(tissue_rows), tissue_chunks),
            (pd.DataFrame(disease_rows), disease_chunks),
            (pd.DataFrame(dataset_cell_line_rows), dataset_cell_line_chunks),
            (pd.DataFrame(dataset_gene_rows), dataset_gene_chunks),
            (pd.DataFrame(dataset_tissue_rows), dataset_tissue_chunks),
            (pd.DataFrame(dataset_disease_rows), dataset_disease_chunks),
        ]:
            if not df.empty:
                _write_chunk(df, chunk_dir)

    results: dict[str, int] = {}
    results["cell_line"] = _finalize_chunks(
        cell_line_chunks,
        lambda df: kg_storage.write_nodes(root, NodeType.CELL_LINE.value, df, mode="overwrite"),
        dedup_cols=["id"],
    )
    results["cell_line_expresses_gene"] = _finalize_edge_chunks_streaming(
        expr_chunks,
        root,
        "cell_line_expresses_gene",
        dedup_cols=["x_id", "y_id", "relation", "source"],
    )
    results["cell_line_expresses_protein"] = _finalize_edge_chunks_streaming(
        protein_expr_chunks,
        root,
        "cell_line_expresses_protein",
        dedup_cols=["x_id", "y_id", "relation", "source"],
    )
    results["cell_line_derived_from_tissue"] = _finalize_edge_chunks_streaming(
        tissue_chunks,
        root,
        "cell_line_derived_from_tissue",
        dedup_cols=["x_id", "y_id", "relation", "source"],
    )
    results["cell_line_associated_disease"] = _finalize_edge_chunks_streaming(
        disease_chunks,
        root,
        "cell_line_associated_disease",
        dedup_cols=["x_id", "y_id", "relation", "source"],
    )
    for relation, chunk_dir in [
        ("dataset_contains_cell_line", dataset_cell_line_chunks),
        ("dataset_contains_gene", dataset_gene_chunks),
        ("dataset_contains_tissue", dataset_tissue_chunks),
        ("dataset_contains_disease", dataset_disease_chunks),
    ]:
        results[relation] = _finalize_edge_chunks_streaming(
            chunk_dir,
            root,
            relation,
            dedup_cols=["x_id", "y_id", "relation", "source"],
        )

    return results


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

ALL_DATASETS = [
    "target",
    "disease",
    "drug_molecule",
    "interaction",
    "evidence",          # pseudo-name: ingests all evidence_* subdirs
    "go",
    "reactome",
    "literature",        # pseudo-name: reads from evidence_europepmc
    "drug_indication",
    "drug_mechanism_of_action",
    "target_essentiality",
]

# ---------------------------------------------------------------------------
# Phase 5a — Disease-phenotype (HPO) associations
# ---------------------------------------------------------------------------

def ingest_disease_phenotype(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest disease-phenotype associations → ``disease_has_phenotype`` edges.

    Source: ``data/opentargets/disease_phenotype/``
    Schema: disease (MONDO_...), phenotype (HP_...), evidence (list of dicts)
    Produces: ``edges/disease_has_phenotype.parquet``

    Credibility is assigned from the HPO ``evidenceType``:
    - TAS / PCS  → 3 (curated / published clinical series)
    - IEA        → 2 (inferred from electronic annotation)
    - other      → 1
    """
    dp_dir = ot_dir / "disease_phenotype"
    if not dp_dir.exists():
        raise FileNotFoundError(dp_dir)

    rows: list[dict] = []
    seen_diseases: set[str] = set()
    seen_phenotypes: set[str] = set()
    for chunk in _read_parquet_dir_chunked(
        dp_dir, columns=["disease", "phenotype", "evidence"], chunksize=100_000
    ):
        for _, row in chunk.iterrows():
            disease_id  = row["disease"]
            phenotype_id = row["phenotype"]
            evidence_list = _to_list(row.get("evidence", []))

            # Basic ID validation
            if not isinstance(disease_id, str) or not disease_id.startswith("MONDO_"):
                continue
            if not isinstance(phenotype_id, str) or not phenotype_id.startswith("HP_"):
                continue
            disease_id = _normalize_mondo_id(disease_id)
            phenotype_id = _normalize_hp_id(phenotype_id)

            # Skip negated associations (qualifierNot=True in any evidence item)
            if any(
                isinstance(e, dict) and e.get("qualifierNot", False)
                for e in evidence_list
            ):
                continue
            seen_diseases.add(disease_id)
            seen_phenotypes.add(phenotype_id)

            # Derive credibility from the strongest evidenceType present
            ev_types = {
                e.get("evidenceType", "")
                for e in evidence_list
                if isinstance(e, dict)
            }
            if ev_types & {"TAS", "PCS"}:
                cred = Credibility.ESTABLISHED_FACT
            elif "IEA" in ev_types:
                cred = Credibility.MULTI_EVIDENCE
            else:
                cred = Credibility.SINGLE_EVIDENCE

            rows.append(_make_edge(
                x_id=disease_id,
                x_type=NodeType.DISEASE.value,
                y_id=phenotype_id,
                y_type=NodeType.PHENOTYPE.value,
                relation="disease_has_phenotype",
                display_relation="has phenotype",
                source="OpenTargets/HPO",
                credibility=int(cred),
            ))

    if not rows:
        log.warning("ingest_disease_phenotype: no rows written")
        return 0

    if seen_diseases:
        try:
            existing_disease_ids = set(
                kg_storage.read_nodes(root, NodeType.DISEASE.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_disease_ids = set()
        missing_disease_ids = sorted(seen_diseases - existing_disease_ids)
        if missing_disease_ids:
            kg_storage.write_nodes(
                root,
                NodeType.DISEASE.value,
                pd.DataFrame(
                    {
                        "id": disease_id,
                        "mondo_id": disease_id,
                        "omim_id": None,
                        "doid_id": None,
                        "icd10_code": None,
                        "name": disease_id,
                        "mesh_id": None,
                        "hp_id": None,
                        "source": "OpenTargets/HPO",
                    }
                    for disease_id in missing_disease_ids
                ),
                mode="append",
            )
            log.info("  added %d disease-phenotype disease stubs", len(missing_disease_ids))
    if seen_phenotypes:
        try:
            existing_phenotype_ids = set(
                kg_storage.read_nodes(root, NodeType.PHENOTYPE.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_phenotype_ids = set()
        missing_phenotype_ids = sorted(seen_phenotypes - existing_phenotype_ids)
        if missing_phenotype_ids:
            kg_storage.write_nodes(
                root,
                NodeType.PHENOTYPE.value,
                pd.DataFrame(
                    {
                        "id": phenotype_id,
                        "mondo_id": None,
                        "efo_id": None,
                        "mp_id": None,
                        "mesh_id": None,
                        "name": phenotype_id,
                        "source": "OpenTargets/HPO",
                    }
                    for phenotype_id in missing_phenotype_ids
                ),
                mode="append",
            )
            log.info("  added %d disease-phenotype phenotype stubs", len(missing_phenotype_ids))

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["x_id", "y_id", "relation", "source"], keep="first")
    _save_edge_df(df, root, "disease_has_phenotype")
    log.info("  saved disease_has_phenotype.parquet  (%d rows)", len(df))
    return len(df)


# ---------------------------------------------------------------------------
# Phase 5b — Gene expression (GTEx / HPA via OpenTargets)
# ---------------------------------------------------------------------------

def ingest_expression(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest gene-expression data → tissue/cell-type expression edges.

    Source: ``data/opentargets/expression/``
    Schema: id (ENSG), tissues (array of dicts with efo_code, rna.value, …)
    Produces:
      ``edges/tissue_expresses_gene.parquet``   (UBERON_ tissues)
      ``edges/cell_type_expresses_gene.parquet``  (CL_ cell types)
    """
    exp_dir = ot_dir / "expression"
    if not exp_dir.exists():
        raise FileNotFoundError(exp_dir)

    tissue_rows:    list[dict] = []
    cell_type_rows: list[dict] = []
    cell_type_protein_rows: list[dict] = []
    seen_genes: set[str] = set()
    gene_to_proteins = _build_gene_to_protein_map(root)

    for chunk in _read_parquet_dir_chunked(
        exp_dir, columns=["id", "tissues"], chunksize=50_000
    ):
        for _, row in chunk.iterrows():
            gene_id   = row["id"]
            if not isinstance(gene_id, str) or not gene_id.startswith("ENSG"):
                continue
            seen_genes.add(gene_id)
            tissues = _to_list(row.get("tissues", []))
            for t in tissues:
                if not isinstance(t, dict):
                    continue
                efo_code = t.get("efo_code", "")
                if not isinstance(efo_code, str):
                    continue

                # RNA expression value (TPM)
                rna = t.get("rna") or {}
                tpm   = rna.get("value") if isinstance(rna, dict) else None
                level = rna.get("level") if isinstance(rna, dict) else None

                extra: dict = {}
                if tpm is not None:
                    extra["tpm"] = float(tpm)
                if level is not None:
                    extra["expression_level"] = int(level)

                if efo_code.startswith("UBERON_"):
                    tissue_id = _normalize_uberon_id(efo_code)
                    tissue_rows.append(_make_edge(
                        x_id=tissue_id,
                        x_type=NodeType.TISSUE.value,
                        y_id=gene_id,
                        y_type=NodeType.GENE.value,
                        relation="tissue_expresses_gene",
                        display_relation="expresses",
                        source="OpenTargets/HPA",
                        credibility=int(Credibility.ESTABLISHED_FACT),
                        **extra,
                    ))
                elif efo_code.startswith("CL_"):
                    cell_type_rows.append(_make_edge(
                        x_id=efo_code,
                        x_type=NodeType.CELL_TYPE.value,
                        y_id=gene_id,
                        y_type=NodeType.GENE.value,
                        relation="cell_type_expresses_gene",
                        display_relation="expresses",
                        source="OpenTargets/HPA",
                        credibility=int(Credibility.ESTABLISHED_FACT),
                        **extra,
                    ))
                    for protein_id in gene_to_proteins.get(gene_id, []):
                        cell_type_protein_rows.append(_make_edge(
                            x_id=efo_code,
                            x_type=NodeType.CELL_TYPE.value,
                            y_id=protein_id,
                            y_type=NodeType.PROTEIN.value,
                            relation="cell_type_expresses_protein",
                            display_relation="expresses",
                            source="OpenTargets/HPA;projected_via_protein_node_xref",
                            credibility=int(Credibility.ESTABLISHED_FACT),
                            gene_id=gene_id,
                            **extra,
                        ))

    dedup = ["x_id", "y_id", "relation", "source"]
    results: dict[str, int] = {}
    if seen_genes:
        try:
            existing_gene_ids = set(
                kg_storage.read_nodes(root, NodeType.GENE.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_gene_ids = set()
        missing_gene_ids = sorted(seen_genes - existing_gene_ids)
        if missing_gene_ids:
            kg_storage.write_nodes(
                root,
                NodeType.GENE.value,
                pd.DataFrame(
                    {
                        "id": gene_id,
                        "ncbi_gene_id": None,
                        "hgnc_id": None,
                        "uniprot_id": None,
                        "gene_name": None,
                        "name": gene_id,
                        "source": "OpenTargets/expression",
                    }
                    for gene_id in missing_gene_ids
                ),
                mode="append",
            )
            log.info("  added %d expression-only gene stubs", len(missing_gene_ids))

    for relation, rows in [
        ("tissue_expresses_gene",    tissue_rows),
        ("cell_type_expresses_gene", cell_type_rows),
        ("cell_type_expresses_protein", cell_type_protein_rows),
    ]:
        if not rows:
            log.warning("ingest_expression: no rows for %s", relation)
            results[relation] = 0
            continue
        df = pd.DataFrame(rows).drop_duplicates(subset=dedup, keep="first")
        _save_edge_df(df, root, relation)
        log.info("  saved %s.parquet  (%d rows)", relation, len(df))
        results[relation] = len(df)

    return results


# ---------------------------------------------------------------------------
# Phase 5c — Biosample (cell-type and tissue node registry)
# ---------------------------------------------------------------------------

def ingest_biosample(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Register cell-type and tissue nodes from the OpenTargets biosample table.

    Source: ``data/opentargets/biosample/``
    Columns: biosampleId, biosampleName, …
    Produces:
      ``nodes/cell_type.parquet``  (CL_ IDs)
      ``nodes/tissue.parquet``     (UBERON_ IDs)
    """
    bs_dir = ot_dir / "biosample"
    if not bs_dir.exists():
        raise FileNotFoundError(bs_dir)

    cell_type_rows: list[dict] = []
    tissue_rows:    list[dict] = []

    for chunk in _read_parquet_dir_chunked(
        bs_dir, columns=["biosampleId", "biosampleName"], chunksize=50_000
    ):
        for _, row in chunk.iterrows():
            bid  = row["biosampleId"]
            name = row.get("biosampleName", "")
            if not isinstance(bid, str):
                continue
            node = {"id": bid, "name": str(name) if name else None, "source": SOURCE_NAME}
            if bid.startswith("CL_"):
                cell_type_rows.append(node)
            elif bid.startswith("UBERON_"):
                node["id"] = _normalize_uberon_id(bid)
                tissue_rows.append(node)

    results: dict[str, int] = {}
    for ntype, rows in [
        (NodeType.CELL_TYPE.value, cell_type_rows),
        (NodeType.TISSUE.value,    tissue_rows),
    ]:
        if not rows:
            log.warning("ingest_biosample: no rows for node type %s", ntype)
            results[ntype] = 0
            continue
        df = pd.DataFrame(rows).drop_duplicates(subset=["id"], keep="first")
        _save_node_df(df, root, ntype)
        log.info("  saved nodes/%s.parquet  (%d rows)", ntype, len(df))
        results[ntype] = len(df)

    return results


# ---------------------------------------------------------------------------
# Phase 5d — Pharmacogenomics (variant–drug response)
# ---------------------------------------------------------------------------

def ingest_pharmacogenomics(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> int:
    """Ingest pharmacogenomics data → ``mutation_affects_molecule_response`` edges.

    Source: ``data/opentargets/pharmacogenomics/``
    Key columns: variantId (chr_pos_ref_alt), variantRsId, targetFromSourceId (ENSG),
                 drugs (array of {drugFromSource, drugId (ChEMBL)})
    Produces: ``edges/mutation_affects_molecule_response.parquet``

    Only rows where a ChEMBL drugId is present are emitted.
    """
    pg_dir = ot_dir / "pharmacogenomics"
    if not pg_dir.exists():
        raise FileNotFoundError(pg_dir)

    rows: list[dict] = []
    seen_mutations: dict[str, str | None] = {}
    seen_molecules: set[str] = set()
    pg_cols = ["variantId", "variantRsId", "targetFromSourceId", "drugs",
               "evidenceLevel", "pgxCategory", "datasourceId"]

    for chunk in _read_parquet_dir_chunked(pg_dir, columns=pg_cols, chunksize=100_000):
        for _, row in chunk.iterrows():
            variant_id = row.get("variantId")
            if not isinstance(variant_id, str) or not variant_id:
                continue
            variant_rs_id = row.get("variantRsId")

            drugs = _to_list(row.get("drugs", []))
            ev_level = row.get("evidenceLevel")
            pgx_cat  = row.get("pgxCategory", "")
            datasrc  = str(row.get("datasourceId", SOURCE_NAME))

            # Assign credibility from evidenceLevel (PharmGKB: 1A/1B > 2A/2B > 3/4)
            try:
                level_str = str(ev_level).strip() if ev_level is not None else ""
                if level_str in ("1A", "1B"):
                    cred = int(Credibility.ESTABLISHED_FACT)
                elif level_str in ("2A", "2B"):
                    cred = int(Credibility.MULTI_EVIDENCE)
                else:
                    cred = int(Credibility.SINGLE_EVIDENCE)
            except Exception:
                cred = int(Credibility.SINGLE_EVIDENCE)

            for drug in drugs:
                if not isinstance(drug, dict):
                    continue
                drug_id = drug.get("drugId")
                if not isinstance(drug_id, str) or not drug_id.startswith("CHEMBL"):
                    continue
                seen_mutations.setdefault(
                    variant_id,
                    str(variant_rs_id).strip() if variant_rs_id is not None else None,
                )
                seen_molecules.add(drug_id)

                rows.append(_make_edge(
                    x_id=variant_id,
                    x_type=NodeType.MUTATION.value,
                    y_id=drug_id,
                    y_type=NodeType.MOLECULE.value,
                    relation="mutation_affects_molecule_response",
                    display_relation="affects response to",
                    source=f"OpenTargets/{datasrc}",
                    credibility=cred,
                    pgx_category=str(pgx_cat) if pgx_cat else None,
                ))

    if not rows:
        log.warning("ingest_pharmacogenomics: no rows written")
        return 0

    if seen_mutations:
        try:
            existing_mutation_ids = set(
                kg_storage.read_nodes(root, NodeType.MUTATION.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_mutation_ids = set()
        missing_mutation_ids = sorted(set(seen_mutations) - existing_mutation_ids)
        if missing_mutation_ids:
            kg_storage.write_nodes(
                root,
                NodeType.MUTATION.value,
                pd.DataFrame(
                    {
                        "id": mutation_id,
                        "hgvs": None,
                        "clinvar_id": None,
                        "gnomad_id": None,
                        "name": seen_mutations.get(mutation_id) or mutation_id,
                        "source": "OpenTargets/pharmacogenomics",
                    }
                    for mutation_id in missing_mutation_ids
                ),
                mode="append",
            )
            log.info("  added %d pharmacogenomics mutation stubs", len(missing_mutation_ids))
    if seen_molecules:
        try:
            existing_molecule_ids = set(
                kg_storage.read_nodes(root, NodeType.MOLECULE.value, columns=["id"])["id"].astype(str)
            )
        except Exception:
            existing_molecule_ids = set()
        missing_molecule_ids = sorted(seen_molecules - existing_molecule_ids)
        if missing_molecule_ids:
            kg_storage.write_nodes(
                root,
                NodeType.MOLECULE.value,
                pd.DataFrame(
                    {
                        "id": molecule_id,
                        "drugbank_id": None,
                        "pubchem_cid": None,
                        "cas_rn": None,
                        "inchikey": None,
                        "smiles": None,
                        "name": molecule_id,
                        "source": "OpenTargets/pharmacogenomics",
                    }
                    for molecule_id in missing_molecule_ids
                ),
                mode="append",
            )
            log.info("  added %d pharmacogenomics molecule stubs", len(missing_molecule_ids))

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["x_id", "y_id", "relation", "source"], keep="first")
    _save_edge_df(df, root, "mutation_affects_molecule_response")
    log.info("  saved mutation_affects_molecule_response.parquet  (%d rows)", len(df))
    return len(df)


# ---------------------------------------------------------------------------
# Phase 5e — Variant (mutation nodes + consequence edges)
# ---------------------------------------------------------------------------

def _build_uniprot_to_ensp(root: kg_storage.KGRoot) -> dict[str, str]:
    """Return unambiguous UniProt accession → ENSP node ID mappings."""
    try:
        protein_df = kg_storage.read_nodes(
            root,
            NodeType.PROTEIN.value,
            columns=["id", "uniprot_id"],
        )
    except Exception as exc:
        log.warning("Could not read protein nodes for UniProt→ENSP mapping: %s", exc)
        return {}

    if "uniprot_id" not in protein_df.columns:
        return {}

    protein_map = protein_df[["id", "uniprot_id"]].dropna()
    protein_map = protein_map[
        (protein_map["id"].astype(str).str.startswith("ENSP"))
        & (protein_map["uniprot_id"].astype(str).str.strip() != "")
    ].copy()
    grouped = protein_map.groupby("uniprot_id")["id"].nunique()
    unique_uniprots = set(grouped[grouped == 1].index)
    protein_map = protein_map[protein_map["uniprot_id"].isin(unique_uniprots)]
    mapping = dict(zip(protein_map["uniprot_id"], protein_map["id"], strict=False))
    log.info("Loaded %d unambiguous UniProt→ENSP mappings", len(mapping))
    return mapping


def ingest_variants(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest variant data → mutation nodes + gene/transcript/protein edges.

    Source: ``data/opentargets/variant/`` (25 parquet files, large)
    Key columns: variantId (chr_pos_ref_alt), hgvsId, rsIds,
                 transcriptConsequences (array of consequence dicts)
    Produces:
      ``nodes/mutation.parquet``
      ``edges/mutation_in_gene.parquet``              (→ ENSG via targetId)
      ``edges/mutation_affects_transcript.parquet``   (→ ENST via transcriptId)
      ``edges/mutation_causes_protein_change.parquet`` (→ ENSP via UniProt xref, only if aminoAcidChange)

    Uses per-chunk flushing to avoid OOM on large files.
    """
    var_dir = ot_dir / "variant"
    if not var_dir.exists():
        raise FileNotFoundError(var_dir)

    uniprot_to_ensp = _build_uniprot_to_ensp(root)

    chunks_base   = out_dir / ".chunks" / "variants"
    mut_chunks    = chunks_base / "mutation"
    gene_chunks   = chunks_base / "mutation_in_gene"
    tx_chunks     = chunks_base / "mutation_affects_transcript"
    prot_chunks   = chunks_base / "mutation_causes_protein_change"

    var_cols = [
        "variantId", "hgvsId", "rsIds", "chromosome", "position",
        "referenceAllele", "alternateAllele", "mostSevereConsequenceId",
        "transcriptConsequences",
    ]

    for chunk in _read_parquet_dir_chunked(var_dir, columns=var_cols, chunksize=25_000):
        # ── Mutation nodes (fully vectorized) ───────────────────────────────
        mut_df = chunk.rename(columns={
            "variantId": "id",
            "hgvsId": "hgvs",
        })[["id", "hgvs", "rsIds"]].copy()

        # First rsId element as alias (list column → scalar)
        mut_df["clinvar_id"] = mut_df["rsIds"].apply(
            lambda x: list(x)[0] if x is not None and hasattr(x, "__len__") and len(x) > 0 else None
        )
        mut_df["gnomad_id"] = mut_df["id"]
        # Human-readable name: prefer HGVS, fall back to variantId
        mut_df["name"] = mut_df["hgvs"].combine_first(mut_df["id"])
        mut_df["source"] = SOURCE_NAME
        mut_df = mut_df.drop(columns=["rsIds"])
        # Drop rows with missing variantId
        mut_df = mut_df[mut_df["id"].notna() & (mut_df["id"] != "")]
        _write_chunk(mut_df, mut_chunks)

        # ── Consequence edges (explode → json_normalize → mask) ─────────────
        tc_df = chunk[["variantId", "transcriptConsequences"]].copy()
        tc_df = tc_df.explode("transcriptConsequences")
        tc_df = tc_df.dropna(subset=["transcriptConsequences"])

        # Keep only Ensembl canonical transcripts
        is_canonical = tc_df["transcriptConsequences"].apply(
            lambda x: isinstance(x, dict) and bool(x.get("isEnsemblCanonical", False))
        )
        tc_df = tc_df[is_canonical]

        if len(tc_df) == 0:
            _write_chunk(pd.DataFrame(), gene_chunks)
            _write_chunk(pd.DataFrame(), tx_chunks)
            _write_chunk(pd.DataFrame(), prot_chunks)
            continue

        # Expand the consequence dict into flat columns
        tc_exp = pd.json_normalize(tc_df["transcriptConsequences"].tolist())
        tc_exp.index = tc_df.index
        tc_exp["variantId"] = tc_df["variantId"].values

        # Gene edges  (mutation → ENSG)
        if "targetId" in tc_exp.columns:
            gene_mask = tc_exp["targetId"].str.startswith("ENSG", na=False)
            g = tc_exp.loc[gene_mask, ["variantId", "targetId"]].rename(
                columns={"variantId": "x_id", "targetId": "y_id"}
            ).copy()
            g["x_type"]          = NodeType.MUTATION.value
            g["y_type"]          = NodeType.GENE.value
            g["relation"]        = "mutation_in_gene"
            g["display_relation"] = "in gene"
            g["source"]          = SOURCE_NAME
            g["credibility"]     = int(Credibility.ESTABLISHED_FACT)
            _write_chunk(g, gene_chunks)
        else:
            _write_chunk(pd.DataFrame(), gene_chunks)

        # Transcript edges  (mutation → ENST)
        if "transcriptId" in tc_exp.columns:
            tx_mask = tc_exp["transcriptId"].str.startswith("ENST", na=False)
            t = tc_exp.loc[tx_mask, ["variantId", "transcriptId"]].rename(
                columns={"variantId": "x_id", "transcriptId": "y_id"}
            ).copy()
            t["x_type"]          = NodeType.MUTATION.value
            t["y_type"]          = NodeType.TRANSCRIPT.value
            t["relation"]        = "mutation_affects_transcript"
            t["display_relation"] = "affects transcript"
            t["source"]          = SOURCE_NAME
            t["credibility"]     = int(Credibility.ESTABLISHED_FACT)
            _write_chunk(t, tx_chunks)
        else:
            _write_chunk(pd.DataFrame(), tx_chunks)

        # Protein-change edges  (mutation → ENSP via UniProt xref, only if aminoAcidChange set)
        if "aminoAcidChange" in tc_exp.columns and "uniprotAccessions" in tc_exp.columns:
            aa_mask = (
                tc_exp["aminoAcidChange"].notna()
                & (tc_exp["aminoAcidChange"].astype(str).str.strip() != "")
                & (tc_exp["aminoAcidChange"].astype(str) != "nan")
            )
            prot_tc = tc_exp.loc[aa_mask, ["variantId", "uniprotAccessions",
                                           "aminoAcidChange"]].copy()
            if len(prot_tc) > 0:
                prot_tc = prot_tc.explode("uniprotAccessions")
                prot_tc = prot_tc.dropna(subset=["uniprotAccessions"])
                valid_up = prot_tc["uniprotAccessions"].str.len() > 0
                prot_tc = prot_tc[valid_up]
                if len(prot_tc) > 0:
                    prot_tc["ensp_id"] = prot_tc["uniprotAccessions"].map(uniprot_to_ensp)
                    prot_tc = prot_tc.dropna(subset=["ensp_id"])
                if len(prot_tc) > 0:
                    p = prot_tc.rename(columns={
                        "variantId": "x_id", "ensp_id": "y_id"
                    }).copy()
                    p["x_type"]          = NodeType.MUTATION.value
                    p["y_type"]          = NodeType.PROTEIN.value
                    p["relation"]        = "mutation_causes_protein_change"
                    p["display_relation"] = "causes protein change"
                    p["source"]          = SOURCE_NAME
                    p["credibility"]     = int(Credibility.ESTABLISHED_FACT)
                    p["amino_acid_change"] = p["aminoAcidChange"]
                    p["uniprot_id"] = p["uniprotAccessions"]
                    p = p.drop(columns=["aminoAcidChange", "uniprotAccessions"])
                    _write_chunk(p, prot_chunks)
                    continue
        _write_chunk(pd.DataFrame(), prot_chunks)

    dedup_edge = ["x_id", "y_id", "relation", "source"]
    results: dict[str, int] = {}
    results["mutation"] = _finalize_chunks(
        mut_chunks,
        lambda df: kg_storage.write_nodes(
            root,
            NodeType.MUTATION.value,
            df,
            mode="overwrite",
        ),
        dedup_cols=["id"],
    )
    results["mutation_in_gene"] = _finalize_chunks(
        gene_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "mutation_in_gene",
            df,
            mode="overwrite",
        ),
        dedup_cols=dedup_edge,
    )
    results["mutation_affects_transcript"] = _finalize_chunks(
        tx_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "mutation_affects_transcript",
            df,
            mode="overwrite",
        ),
        dedup_cols=dedup_edge,
    )
    results["mutation_causes_protein_change"] = _finalize_chunks(
        prot_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "mutation_causes_protein_change",
            df,
            mode="overwrite",
        ),
        dedup_cols=dedup_edge,
    )
    return results


def ingest_variant_protein_changes(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest only mutation→ENSP protein-change edges from OpenTargets variants.

    The full variant graph is extremely dense: a one-file smoke emitted more
    than 11M gene and transcript consequence edges. This bounded slice keeps
    the graph-valid protein consequence signal without promoting those full
    gene/transcript relations.
    """
    var_dir = ot_dir / "variant"
    if not var_dir.exists():
        raise FileNotFoundError(var_dir)

    uniprot_to_ensp = _build_uniprot_to_ensp(root)
    chunks_base = out_dir / ".chunks" / "variant_protein_change"
    mut_chunks = chunks_base / "mutation"
    edge_chunks = chunks_base / "mutation_causes_protein_change"
    var_cols = ["variantId", "hgvsId", "rsIds", "transcriptConsequences"]

    for chunk in _read_parquet_dir_chunked(var_dir, columns=var_cols, chunksize=5_000):
        edge_rows: list[dict[str, object]] = []
        for row in chunk.itertuples(index=False):
            variant_id = getattr(row, "variantId", None)
            consequences = _to_list(getattr(row, "transcriptConsequences", None))
            if not isinstance(variant_id, str) or not consequences:
                continue
            for consequence in consequences:
                if not isinstance(consequence, dict):
                    continue
                aa_change = consequence.get("aminoAcidChange")
                if aa_change is None or str(aa_change).strip() in {"", "nan"}:
                    continue
                for uniprot_id in _to_list(consequence.get("uniprotAccessions")):
                    ensp_id = uniprot_to_ensp.get(uniprot_id)
                    if not ensp_id:
                        continue
                    edge_rows.append({
                        "x_id": variant_id,
                        "x_type": NodeType.MUTATION.value,
                        "y_id": ensp_id,
                        "y_type": NodeType.PROTEIN.value,
                        "relation": "mutation_causes_protein_change",
                        "display_relation": "causes protein change",
                        "source": SOURCE_NAME,
                        "credibility": int(Credibility.ESTABLISHED_FACT),
                        "amino_acid_change": aa_change,
                        "uniprot_id": uniprot_id,
                    })

        if not edge_rows:
            _write_chunk(pd.DataFrame(), mut_chunks)
            _write_chunk(pd.DataFrame(), edge_chunks)
            continue

        edge_df = pd.DataFrame(edge_rows)
        _write_chunk(edge_df, edge_chunks)

        mutation_ids = set(edge_df["x_id"].astype(str))
        mut_df = chunk.rename(columns={"variantId": "id", "hgvsId": "hgvs"})[
            ["id", "hgvs", "rsIds"]
        ].copy()
        mut_df = mut_df[mut_df["id"].astype(str).isin(mutation_ids)]
        mut_df["clinvar_id"] = mut_df["rsIds"].apply(
            lambda x: list(x)[0] if x is not None and hasattr(x, "__len__") and len(x) > 0 else None
        )
        mut_df["gnomad_id"] = mut_df["id"]
        mut_df["name"] = mut_df["hgvs"].combine_first(mut_df["id"])
        mut_df["source"] = SOURCE_NAME
        mut_df = mut_df.drop(columns=["rsIds"])
        _write_chunk(mut_df, mut_chunks)

    dedup_edge = ["x_id", "y_id", "relation", "source"]
    results: dict[str, int] = {}
    results["mutation"] = _finalize_chunks(
        mut_chunks,
        lambda df: kg_storage.write_nodes(
            root,
            NodeType.MUTATION.value,
            df,
            mode="append",
        ),
        dedup_cols=["id"],
    )
    results["mutation_causes_protein_change"] = _finalize_chunks(
        edge_chunks,
        lambda df: kg_storage.write_edges(
            root,
            "mutation_causes_protein_change",
            df,
            mode="overwrite",
        ),
        dedup_cols=dedup_edge,
    )
    return results


def _sqlite_jsonable(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (list, tuple, dict, np.ndarray)):
        payload = value.tolist() if isinstance(value, np.ndarray) else value
        return json.dumps(payload, sort_keys=True)
    return value


def _sqlite_insert_chunk(
    conn: sqlite3.Connection,
    table: str,
    chunk: pd.DataFrame,
    columns: list[str],
) -> None:
    if chunk.empty:
        return
    projected = chunk.reindex(columns=columns).copy()
    for column in projected.columns:
        if projected[column].dtype == "object":
            projected[column] = projected[column].map(_sqlite_jsonable)
    projected.to_sql(table, conn, if_exists="append", index=False)


def _build_gwas_evidence_sqlite(
    ot_dir: Path,
    db_path: Path,
    *,
    chunksize: int = 100_000,
) -> int:
    evidence_dir = ot_dir / GWAS_CREDIBLE_SET_EVIDENCE_DIR
    if not evidence_dir.exists():
        return 0

    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(
        """
        CREATE TABLE evidence (
            studyLocusId TEXT NOT NULL,
            diseaseId TEXT NOT NULL,
            datatypeId TEXT,
            datasourceId TEXT,
            score REAL,
            resourceScore REAL,
            targetId TEXT
        )
        """
    )

    available = _parquet_available_columns(evidence_dir, list(GWAS_EVIDENCE_COLUMNS))
    if "studyLocusId" not in available or "diseaseId" not in available:
        conn.close()
        return 0

    n_rows = 0
    for chunk in _read_parquet_dir_chunked(evidence_dir, columns=available, chunksize=chunksize):
        chunk = chunk[chunk["studyLocusId"].notna() & chunk["diseaseId"].notna()].copy()
        if "datasourceId" in chunk.columns:
            chunk = chunk[
                chunk["datasourceId"].fillna("gwas_credible_sets").astype(str).eq("gwas_credible_sets")
            ]
        if chunk.empty:
            continue
        _sqlite_insert_chunk(conn, "evidence", chunk, list(GWAS_EVIDENCE_COLUMNS))
        n_rows += len(chunk)

    conn.execute("CREATE INDEX evidence_locus_idx ON evidence(studyLocusId)")
    conn.commit()
    conn.close()
    return n_rows


def _build_l2g_sqlite(
    ot_dir: Path,
    db_path: Path,
    *,
    score_min: float = 0.75,
    chunksize: int = 100_000,
) -> int:
    l2g_dir = ot_dir / "l2g_prediction"
    if not l2g_dir.exists():
        return 0

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS l2g (
            studyLocusId TEXT NOT NULL,
            geneId TEXT NOT NULL,
            score REAL
        )
        """
    )
    available = _parquet_available_columns(l2g_dir, list(GWAS_L2G_COLUMNS))
    if not set(GWAS_L2G_COLUMNS).issubset(available):
        conn.close()
        return 0

    n_rows = 0
    for chunk in _read_parquet_dir_chunked(l2g_dir, columns=available, chunksize=chunksize):
        chunk = chunk[
            chunk["studyLocusId"].notna()
            & chunk["geneId"].notna()
            & chunk["score"].fillna(0.0).astype(float).ge(score_min)
        ].copy()
        if chunk.empty:
            continue
        _sqlite_insert_chunk(conn, "l2g", chunk, list(GWAS_L2G_COLUMNS))
        n_rows += len(chunk)

    conn.execute("CREATE INDEX IF NOT EXISTS l2g_locus_idx ON l2g(studyLocusId)")
    conn.commit()
    conn.close()
    return n_rows


def _fetch_sqlite_rows_for_loci(
    conn: sqlite3.Connection,
    table: str,
    loci: list[str],
) -> pd.DataFrame:
    if not loci:
        return pd.DataFrame()
    conn.execute("DROP TABLE IF EXISTS tmp_loci")
    conn.execute("CREATE TEMP TABLE tmp_loci (studyLocusId TEXT PRIMARY KEY)")
    conn.executemany(
        "INSERT OR IGNORE INTO tmp_loci(studyLocusId) VALUES (?)",
        [(locus,) for locus in loci],
    )
    return pd.read_sql_query(
        f"SELECT {table}.* FROM {table} JOIN tmp_loci USING(studyLocusId)",
        conn,
    )


def _ingest_gwas_credible_set_join(
    ot_dir: Path,
    chunks_base: Path,
    seen_diseases: set[str],
    seen_genes: set[str],
    *,
    pvalue_exponent_max: int = -8,
    l2g_score_min: float = 0.75,
    emit_l2g_edges: bool = True,
    chunksize: int = 100_000,
) -> dict[str, int]:
    credible_dir = ot_dir / "credible_set"
    evidence_dir = ot_dir / GWAS_CREDIBLE_SET_EVIDENCE_DIR
    if not credible_dir.exists() or not evidence_dir.exists():
        return {}

    chunks_base.mkdir(parents=True, exist_ok=True)
    db_path = chunks_base / "gwas_join.sqlite"
    evidence_rows = _build_gwas_evidence_sqlite(ot_dir, db_path, chunksize=chunksize)
    if not evidence_rows:
        return {}
    l2g_rows = (
        _build_l2g_sqlite(ot_dir, db_path, score_min=l2g_score_min, chunksize=chunksize)
        if emit_l2g_edges
        else 0
    )

    mut_chunks = chunks_base / "mutation"
    disease_chunks = chunks_base / "mutation_associated_disease"
    mutation_gene_chunks = chunks_base / "mutation_associated_gene"
    available = _parquet_available_columns(credible_dir, list(GWAS_CREDIBLE_SET_COLUMNS))
    if "studyLocusId" not in available or "variantId" not in available:
        return {}

    conn = sqlite3.connect(db_path)
    for credible in _read_parquet_dir_chunked(credible_dir, columns=available, chunksize=chunksize):
        credible = credible[credible["studyLocusId"].notna() & credible["variantId"].notna()].copy()
        if "pValueExponent" in credible.columns:
            pval = pd.to_numeric(credible["pValueExponent"], errors="coerce")
            credible = credible[pval.isna() | pval.le(pvalue_exponent_max)]
        if credible.empty:
            continue

        loci = sorted(credible["studyLocusId"].astype(str).unique())
        evidence = _fetch_sqlite_rows_for_loci(conn, "evidence", loci)
        if evidence.empty:
            continue
        joined = credible.merge(evidence, on="studyLocusId", how="inner")
        if joined.empty:
            continue

        mutation_rows: list[dict[str, object]] = []
        disease_rows: list[dict[str, object]] = []
        for _, row in joined.iterrows():
            variant_id = str(row.get("variantId") or "").strip()
            disease_id = normalize_disease_id(row.get("diseaseId")) or ""
            if not variant_id or not disease_id:
                continue
            dtype = str(row.get("datatypeId") or "gwas_credible_sets")
            source_id = str(row.get("datasourceId") or "ot_genetics_portal")
            score = float(row.get("score") or row.get("resourceScore") or 0.0)
            seen_diseases.add(disease_id)
            rs_name = variant_id if variant_id.startswith("rs") else None
            mutation_rows.append({
                "id": variant_id,
                "hgvs": None,
                "clinvar_id": rs_name,
                "gnomad_id": variant_id if not variant_id.startswith("rs") else None,
                "name": rs_name or variant_id,
                "source": f"OpenTargets/{source_id}",
            })
            disease_rows.append(_make_edge(
                x_id=variant_id,
                x_type=NodeType.MUTATION.value,
                y_id=disease_id,
                y_type=NodeType.DISEASE.value,
                relation="mutation_associated_disease",
                display_relation="associated disease",
                source=f"OpenTargets/{source_id}",
                credibility=_credibility_from_score(score, dtype),
                score=round(score, 4),
                datatype=dtype,
                studyLocusId=str(row.get("studyLocusId")),
            ))

        if mutation_rows:
            _write_chunk(pd.DataFrame(mutation_rows), mut_chunks)
        if disease_rows:
            _write_chunk(pd.DataFrame(disease_rows), disease_chunks)

        if emit_l2g_edges and l2g_rows:
            l2g = _fetch_sqlite_rows_for_loci(conn, "l2g", loci)
            if l2g.empty:
                continue
            variants = credible[["studyLocusId", "variantId"]].drop_duplicates()
            l2g_joined = l2g.merge(variants, on="studyLocusId", how="inner")
            gene_rows: list[dict[str, object]] = []
            for _, row in l2g_joined.iterrows():
                variant_id = str(row.get("variantId") or "").strip()
                gene_id = str(row.get("geneId") or "").strip()
                if not variant_id or not gene_id:
                    continue
                seen_genes.add(gene_id)
                score = float(row.get("score") or 0.0)
                gene_rows.append(_make_edge(
                    x_id=variant_id,
                    x_type=NodeType.MUTATION.value,
                    y_id=gene_id,
                    y_type=NodeType.GENE.value,
                    relation="mutation_associated_gene",
                    display_relation="associated gene",
                    source="OpenTargets/l2g",
                    credibility=_credibility_from_score(score, "l2g"),
                    score=round(score, 4),
                    datatype="l2g",
                    studyLocusId=str(row.get("studyLocusId")),
                ))
            if gene_rows:
                _write_chunk(pd.DataFrame(gene_rows), mutation_gene_chunks)

    conn.close()
    return {"gwas_evidence_rows": evidence_rows}


def ingest_evidence_backed_variants(
    ot_dir: Path,
    out_dir: Path,
    root: kg_storage.KGRoot,
) -> dict[str, int]:
    """Ingest variant nodes/edges only when backed by OpenTargets evidence.

    This is the sparse counterpart to the raw ``variant/`` consequence graph:
    it keeps variants that appear in high-value evidence datasets such as GWAS,
    credible sets, ClinVar/EVA, gene burden, somatic mutation, and UniProt
    variant evidence. It deliberately ignores plain consequence annotations
    without disease/phenotype/cell-context signal.
    """
    import pyarrow.parquet as _pq

    ev_dirs = sorted(ot_dir.glob("evidence_*"))
    if not ev_dirs:
        log.warning("No 'evidence_*' datasets found in %s", ot_dir)
        return {}

    chunks_base = out_dir / ".chunks" / "evidence_backed_variants"
    mut_chunks = chunks_base / "mutation"
    disease_chunks = chunks_base / "mutation_associated_disease"
    mutation_gene_chunks = chunks_base / "mutation_associated_gene"
    seen_mutations: dict[str, dict[str, object]] = {}
    seen_diseases: set[str] = set()
    seen_genes: set[str] = set()

    base_cols = ["diseaseId", "datatypeId", "datasourceId", "score"]
    optional_cols = list(VARIANT_EVIDENCE_ID_COLUMNS) + [
        "studyLocusId",
        "locus",
        "credibleSet",
        "credibleSets",
    ]

    for ev_path in ev_dirs:
        if ev_path.name == GWAS_CREDIBLE_SET_EVIDENCE_DIR:
            continue
        parquet_files = sorted(ev_path.glob("*.parquet"))
        if not parquet_files:
            continue
        try:
            schema_fields = {field.name for field in _pq.read_schema(parquet_files[0])}
        except Exception as exc:
            log.warning("Could not read schema for %s: %s", ev_path, exc)
            continue

        cols = [col for col in base_cols + optional_cols if col in schema_fields]
        if "diseaseId" not in cols or "datatypeId" not in cols:
            continue
        if not any(col in schema_fields for col in optional_cols):
            continue

        log.info("  Processing evidence-backed variants from %s", ev_path.name)
        for chunk in _read_parquet_dir_chunked(ev_path, columns=cols, chunksize=100_000):
            disease_rows: list[dict[str, object]] = []
            mutation_rows: list[dict[str, object]] = []

            for _, row in chunk.iterrows():
                dtype = str(row.get("datatypeId") or "").strip()
                if dtype not in EVIDENCE_BACKED_VARIANT_DATATYPES:
                    continue

                disease_id = normalize_disease_id(row.get("diseaseId")) or ""
                if not disease_id:
                    continue
                seen_diseases.add(disease_id)

                variant_id = _variant_id_from_evidence_row(row)
                if not variant_id:
                    continue

                source_id = str(row.get("datasourceId") or dtype).strip()
                score = float(row.get("score") or 0.0)
                cred = _credibility_from_score(score, dtype)

                rs_name = variant_id if variant_id.startswith("rs") else None
                seen_mutations.setdefault(
                    variant_id,
                    {
                        "id": variant_id,
                        "hgvs": None,
                        "clinvar_id": rs_name,
                        "gnomad_id": variant_id if not variant_id.startswith("rs") else None,
                        "name": rs_name or variant_id,
                        "source": f"OpenTargets/{source_id}",
                    },
                )
                mutation_rows.append(seen_mutations[variant_id])
                disease_rows.append(_make_edge(
                    x_id=variant_id,
                    x_type=NodeType.MUTATION.value,
                    y_id=disease_id,
                    y_type=NodeType.DISEASE.value,
                    relation="mutation_associated_disease",
                    display_relation="associated disease",
                    source=f"OpenTargets/{source_id}",
                    credibility=cred,
                    score=round(score, 4),
                    datatype=dtype,
                ))

            if mutation_rows:
                _write_chunk(pd.DataFrame(mutation_rows), mut_chunks)
            if disease_rows:
                _write_chunk(pd.DataFrame(disease_rows), disease_chunks)

    _ingest_gwas_credible_set_join(ot_dir, chunks_base, seen_diseases, seen_genes)

    dedup_edge = ["x_id", "y_id", "relation", "source", "datatype"]
    results: dict[str, int] = {}
    if seen_diseases:
        existing_disease_ids = {
            normalize_disease_id(node_id) or node_id
            for node_id in _existing_node_ids(root, NodeType.DISEASE)
        }
        missing_disease_ids = sorted(seen_diseases - existing_disease_ids)
        if missing_disease_ids:
            kg_storage.write_nodes(
                root,
                NodeType.DISEASE.value,
                pd.DataFrame(
                    {
                        "id": disease_id,
                        "mondo_id": disease_id if disease_id.startswith("MONDO:") else None,
                        "omim_id": None,
                        "doid_id": None,
                        "icd10_code": None,
                        "mesh_id": None,
                        "hp_id": disease_id if disease_id.startswith("HP:") else None,
                        "name": disease_id,
                        "source": "OpenTargets/evidence",
                    }
                    for disease_id in missing_disease_ids
                ),
                mode="append",
            )
            results["disease"] = len(missing_disease_ids)
    if seen_genes:
        existing_gene_ids = _existing_node_ids(root, NodeType.GENE)
        missing_gene_ids = sorted(seen_genes - existing_gene_ids)
        if missing_gene_ids:
            kg_storage.write_nodes(
                root,
                NodeType.GENE.value,
                pd.DataFrame(
                    {
                        "id": gene_id,
                        "ncbi_gene_id": None,
                        "hgnc_id": None,
                        "uniprot_id": None,
                        "gene_name": None,
                        "name": gene_id,
                        "source": "OpenTargets/l2g",
                    }
                    for gene_id in missing_gene_ids
                ),
                mode="append",
            )
            results["gene"] = len(missing_gene_ids)
    results["mutation"] = _finalize_chunks(
        mut_chunks,
        lambda df: kg_storage.write_nodes(
            root,
            NodeType.MUTATION.value,
            df,
            mode="append",
        ),
        dedup_cols=["id"],
    )
    results["mutation_associated_disease"] = _finalize_edge_chunks_streaming(
        disease_chunks,
        root,
        "mutation_associated_disease",
        dedup_edge,
    )
    results["mutation_associated_gene"] = _finalize_edge_chunks_streaming(
        mutation_gene_chunks,
        root,
        "mutation_associated_gene",
        ["x_id", "y_id", "relation", "source", "datatype", "studyLocusId"],
    )
    return {key: value for key, value in results.items() if value}


# ---------------------------------------------------------------------------
# Phase 5f — Enhancer-to-gene (E2G predictions)
# ---------------------------------------------------------------------------

def ingest_enhancers(ot_dir: Path, out_dir: Path, root: kg_storage.KGRoot) -> dict[str, int]:
    """Ingest enhancer-to-gene links → enhancer nodes + regulatory edges.

    Source: ``data/opentargets/enhancer_to_gene/`` (83 parquet files)
    Key columns: intervalId, geneId (ENSG), biosampleId (UBERON_/CL_),
                 biosampleName, chromosome, start, end, score, datasourceId
    Produces:
      ``nodes/enhancer.parquet``
      ``edges/enhancer_regulates_gene.parquet``
      ``edges/enhancer_active_in_tissue.parquet``   (UBERON_ biosamples)
      ``edges/enhancer_active_in_cell_type.parquet`` (CL_ biosamples)

    Uses per-chunk flushing (83 files, large).
    """
    enh_dir = ot_dir / "enhancer_to_gene"
    if not enh_dir.exists():
        raise FileNotFoundError(enh_dir)

    chunks_base    = out_dir / ".chunks" / "enhancers"
    enh_node_chks  = chunks_base / "enhancer"
    gene_edge_chks = chunks_base / "enhancer_regulates_gene"
    tis_edge_chks  = chunks_base / "enhancer_active_in_tissue"
    ct_edge_chks   = chunks_base / "enhancer_active_in_cell_type"

    enh_cols = [
        "intervalId", "geneId", "biosampleId", "biosampleName",
        "chromosome", "start", "end", "score", "datasourceId", "pmid",
    ]

    dedup_edge = ["x_id", "y_id", "relation", "source"]

    for chunk in _read_parquet_dir_chunked(enh_dir, columns=enh_cols, chunksize=500_000):
        # Drop rows with missing intervalId
        chunk = chunk[chunk["intervalId"].notna() & (chunk["intervalId"] != "")].copy()
        if len(chunk) == 0:
            continue

        # Shared derived columns
        src_col = "OpenTargets/" + chunk["datasourceId"].fillna("E2G").astype(str)

        # Credibility from E2G score using pd.cut (vectorized)
        score_col = pd.to_numeric(chunk["score"], errors="coerce").fillna(0.0)
        cred_col = pd.cut(
            score_col,
            bins=[-np.inf, 0.5, 0.9, np.inf],
            labels=[int(Credibility.SINGLE_EVIDENCE),
                    int(Credibility.MULTI_EVIDENCE),
                    int(Credibility.ESTABLISHED_FACT)],
        ).astype(int)

        # ── Enhancer nodes ──────────────────────────────────────────────────
        enh_df = chunk[["intervalId", "chromosome", "start", "end"]].rename(
            columns={"intervalId": "id"}
        ).copy()
        enh_df["name"]   = enh_df["id"]
        enh_df["source"] = src_col.values
        _write_chunk(enh_df, enh_node_chks)

        # ── enhancer → gene edges ───────────────────────────────────────────
        gene_mask = chunk["geneId"].str.startswith("ENSG", na=False)
        if gene_mask.any():
            g = chunk.loc[gene_mask, ["intervalId", "geneId", "score"]].rename(
                columns={"intervalId": "x_id", "geneId": "y_id", "score": "e2g_score"}
            ).copy()
            g["x_type"]          = NodeType.ENHANCER.value
            g["y_type"]          = NodeType.GENE.value
            g["relation"]        = "enhancer_regulates_gene"
            g["display_relation"] = "regulates"
            g["source"]          = src_col[gene_mask].values
            g["credibility"]     = cred_col[gene_mask].values
            _write_chunk(g, gene_edge_chks)

        # ── enhancer → tissue edges (UBERON_) ───────────────────────────────
        tis_mask = chunk["biosampleId"].str.startswith("UBERON_", na=False)
        if tis_mask.any():
            t = chunk.loc[tis_mask, ["intervalId", "biosampleId"]].rename(
                columns={"intervalId": "x_id", "biosampleId": "y_id"}
            ).copy()
            t["y_id"] = t["y_id"].map(lambda value: normalize_ontology_curie(value) or value)
            t["x_type"]          = NodeType.ENHANCER.value
            t["y_type"]          = NodeType.TISSUE.value
            t["relation"]        = "enhancer_active_in_tissue"
            t["display_relation"] = "active in tissue"
            t["source"]          = src_col[tis_mask].values
            t["credibility"]     = cred_col[tis_mask].values
            _write_chunk(t, tis_edge_chks)

        # ── enhancer → cell-type edges (CL_) ────────────────────────────────
        ct_mask = chunk["biosampleId"].str.startswith("CL_", na=False)
        if ct_mask.any():
            c = chunk.loc[ct_mask, ["intervalId", "biosampleId"]].rename(
                columns={"intervalId": "x_id", "biosampleId": "y_id"}
            ).copy()
            c["y_id"] = c["y_id"].map(lambda value: normalize_ontology_curie(value) or value)
            c["x_type"]          = NodeType.ENHANCER.value
            c["y_type"]          = NodeType.CELL_TYPE.value
            c["relation"]        = "enhancer_active_in_cell_type"
            c["display_relation"] = "active in cell type"
            c["source"]          = src_col[ct_mask].values
            c["credibility"]     = cred_col[ct_mask].values
            _write_chunk(c, ct_edge_chks)

    results: dict[str, int] = {}
    results["enhancer"] = _finalize_node_chunks_streaming(
        enh_node_chks,
        root,
        NodeType.ENHANCER.value,
        dedup_cols=["id"],
    )
    results["enhancer_regulates_gene"] = _finalize_edge_chunks_streaming(
        gene_edge_chks,
        root,
        "enhancer_regulates_gene",
        dedup_cols=dedup_edge,
    )
    results["enhancer_active_in_tissue"] = _finalize_edge_chunks_streaming(
        tis_edge_chks,
        root,
        "enhancer_active_in_tissue",
        dedup_cols=dedup_edge,
    )
    results["enhancer_active_in_cell_type"] = _finalize_edge_chunks_streaming(
        ct_edge_chks,
        root,
        "enhancer_active_in_cell_type",
        dedup_cols=dedup_edge,
    )
    return results


def ingest_go(opentargets_dir: Path, kg_dir: Path, root: kg_storage.KGRoot) -> tuple[int, int]:
    """Ingest GO pathway nodes and target GO memberships.

    Kept small and source-native: GO terms become `pathway` nodes and target GO
    annotations become `pathway_contains_gene` edges.
    """

    go_dir = opentargets_dir / "go"
    target_dir = opentargets_dir / "target"
    pathway_rows = pd.DataFrame()
    if go_dir.exists():
        go = _read_parquet_dir(go_dir)
        if not go.empty:
            normalized_ids = go.get("id", pd.Series(dtype=str)).astype(str).map(lambda v: normalize_ontology_curie(v) or v)
            pathway_rows = pd.DataFrame(
                {
                    "id": normalized_ids,
                    "go_id": normalized_ids.where(normalized_ids.str.startswith("GO:"), None),
                    "reactome_id": None,
                    "kegg_id": None,
                    "name": go.get("label", go.get("name", pd.Series(dtype=str))).astype(str),
                    "source": SOURCE_NAME + "/go",
                }
            ).drop_duplicates(subset=["id"])
            kg_storage.write_nodes(root, NodeType.PATHWAY.value, pathway_rows, mode="append")

    edge_rows: list[dict[str, object]] = []
    if target_dir.exists():
        targets = _read_parquet_dir_available(target_dir, ["id", "go"])
        for _, row in targets.iterrows():
            gene_id = str(row.get("id", ""))
            if not gene_id.startswith("ENSG"):
                continue
            for item in _to_list(row.get("go")):
                if not isinstance(item, dict):
                    continue
                go_id = normalize_ontology_curie(item.get("id")) or str(item.get("id", ""))
                if not go_id.startswith("GO:"):
                    continue
                edge_rows.append(
                    {
                        "x_id": go_id,
                        "x_type": NodeType.PATHWAY.value,
                        "y_id": gene_id,
                        "y_type": NodeType.GENE.value,
                        "relation": "pathway_contains_gene",
                        "display_relation": "contains gene",
                        "source": SOURCE_NAME + "/go",
                        "credibility": int(Credibility.ESTABLISHED_FACT),
                        "predicate": item.get("evidence", ""),
                        "aspect": item.get("aspect", ""),
                    }
                )
    edge_df = pd.DataFrame(edge_rows)
    edge_count = 0
    if not edge_df.empty:
        edge_count = kg_storage.write_edges(root, "pathway_contains_gene", edge_df, mode="append")
    return len(pathway_rows), int(edge_count)


# ---------------------------------------------------------------------------
# Dataset dispatch table
# ---------------------------------------------------------------------------

_DATASET_FUNCTION_NAMES = {
    "target": "ingest_targets",
    "orthology": "ingest_orthology",
    "target_homologues": "ingest_orthology",
    "disease": "ingest_diseases",
    "drug_molecule": "ingest_drugs",
    "molecule": "ingest_drugs",
    "drug": "ingest_drugs",
    "interaction": "ingest_interactions",
    "evidence": "ingest_evidence",
    "reactome": "ingest_reactome",
    "literature": "ingest_literature",
    "drug_indication": "ingest_indication",
    "indication": "ingest_indication",
    "drug_mechanism_of_action": "ingest_mechanism_of_action",
    "mechanismOfAction": "ingest_mechanism_of_action",
    "target_essentiality": "ingest_target_essentiality",
    "disease_phenotype": "ingest_disease_phenotype",
    "expression": "ingest_expression",
    "biosample": "ingest_biosample",
    "pharmacogenomics": "ingest_pharmacogenomics",
    "variant": "ingest_variant_protein_changes",
    "evidence_backed_variant": "ingest_evidence_backed_variants",
    "known_variant": "ingest_evidence_backed_variants",
    "enhancer_to_gene": "ingest_enhancers",
    "enhancers": "ingest_enhancers",
}

DATASET_FUNCTIONS = {
    dataset: globals()[function_name]
    for dataset, function_name in _DATASET_FUNCTION_NAMES.items()
    if function_name in globals()
}


def run(
    data_dir: Path,
    datasets: list[str] | None = None,
    release: str = "latest",
    download: bool = True,
    workers: int = 8,
) -> None:
    """Download (optionally) and ingest OpenTargets datasets.

    Args:
        data_dir:  Root data directory; OT data lands in ``{data_dir}/opentargets/``.
        datasets:  Dataset names to process.  Defaults to ``ALL_DATASETS``.
        release:   OT release tag or ``"latest"``.
        download:  If True (default), download missing datasets first.
        workers:   Parallel download threads.
    """
    if datasets is None:
        datasets = list(ALL_DATASETS)

    ot_dir  = data_dir / "opentargets"
    out_dir = data_dir / "kg"
    out_dir.mkdir(parents=True, exist_ok=True)
    kg_root = kg_storage.open_kg_root(str(out_dir))

    # ── Download ─────────────────────────────────────────────────────────────
    if download:
        try:
            # Import inside to avoid hard dependency at module import time
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from txdata_download import download_opentargets_datasets

            download_opentargets_datasets(
                datasets=datasets,
                dest_dir=ot_dir,
                release=release,
                workers=workers,
            )
        except ImportError:
            log.warning("txdata_download not importable; assuming data is already local")

    # ── Ingest ───────────────────────────────────────────────────────────────
    summary: dict[str, object] = {}
    for ds_name in datasets:
        fn = DATASET_FUNCTIONS.get(ds_name)
        if fn is None:
            log.warning("No ingestion function for dataset %r — skipping", ds_name)
            continue
        log.info("\n=== Ingesting %s ===", ds_name)
        try:
            result = fn(ot_dir, out_dir, kg_root)
            summary[ds_name] = result
        except FileNotFoundError as exc:
            log.error("Dataset %r not found: %s", ds_name, exc)
            summary[ds_name] = "MISSING"
        except Exception as exc:
            log.error("Error ingesting %r: %s", ds_name, exc, exc_info=True)
            summary[ds_name] = f"ERROR: {exc}"

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n=== OpenTargets ingestion summary ===")
    for ds_name, result in summary.items():
        print(f"  {ds_name:<25}  {result}")
    print(f"\n  Output directory: {out_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ingest OpenTargets Platform data into the Jouvence KG Parquet schema"
    )
    parser.add_argument(
        "--data-dir", default="./data",
        help="Root data directory (default: ./data)",
    )
    parser.add_argument(
        "--release", default="latest",
        help="OpenTargets release tag, e.g. '25.06' (default: latest)",
    )
    parser.add_argument(
        "--datasets", nargs="+", default=None,
        metavar="DATASET",
        help=f"Datasets to ingest (default: all). Choices: {ALL_DATASETS}",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Skip downloading; use already-local data only",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Parallel download threads (default: 8)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s  %(message)s",
        stream=sys.stderr,
    )

    run(
        data_dir=Path(args.data_dir),
        datasets=args.datasets,
        release=args.release,
        download=not args.no_download,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
