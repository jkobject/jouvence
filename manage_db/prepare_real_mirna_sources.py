"""Prepare real miRNA source tables for staged KG ingestion.

This module does source-specific normalization before
``manage_db.build_staged_mirna_targets`` writes staged nodes/edges/evidence.
It deliberately writes intermediate inputs and reports only; it does not write the
canonical KG.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests

BIOMART_URL = "https://www.ensembl.org/biomart/martservice"

CATALOG_COLUMNS = [
    "id",
    "name",
    "mirna_product_type",
    "species_id",
    "mirbase_mature_accession",
    "mirbase_mature_name",
    "mirbase_precursor_accession",
    "mirbase_precursor_name",
    "arm",
    "ensembl_gene_id",
    "ensembl_transcript_id",
    "rnacentral_id",
    "sequence",
    "source",
    "source_release",
    "mapping_confidence",
    "mapping_method",
]

MAPPING_COLUMNS = [
    "ensembl_transcript_id",
    "ensembl_gene_id",
    "mirbase_accession",
    "mirbase_name",
    "mirbase_entity_type",
    "rnacentral_id",
    "mapping_method",
    "mapping_confidence",
    "source_dataset",
    "source_release",
    "source_record_id",
    "species_id",
    "notes_json",
    "is_same_entity_as_transcript",
]

TARGET_COLUMNS = [
    "source",
    "source_dataset",
    "source_release",
    "source_record_id",
    "mirna_id",
    "mirna_name",
    "mirbase_mature_accession",
    "mirbase_mature_name",
    "mirbase_precursor_accession",
    "mirna_product_type",
    "target_endpoint_level",
    "target_gene_id",
    "original_target_id",
    "original_target_name",
    "target_id_namespace",
    "target_mapping_method",
    "target_mapping_confidence",
    "species_id",
    "species_name",
    "assay",
    "support_type",
    "predicate",
    "evidence_type",
    "pmid",
    "confidence",
    "license_checked",
    "source_url",
]


def _nonnull(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _normalise_mirna_name(name: Any) -> str:
    text = _nonnull(name)
    text = text.replace("−", "-").replace("–", "-")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _arm(name: str) -> str:
    match = re.search(r"-(5p|3p)$", name, flags=re.I)
    return match.group(1).lower() if match else ""


def parse_mirbase_dat(path: str | Path, *, source_release: str = "miRBase current download 2026-06-22") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse human precursor and mature miRNA entities from miRBase miRNA.dat."""
    text = Path(path).read_text(errors="replace")
    rows: list[dict[str, Any]] = []
    mature_rows: list[dict[str, Any]] = []
    for record in text.split("\n//"):
        if "\nID   hsa" not in "\n" + record:
            continue
        lines = record.splitlines()
        id_line = next((line for line in lines if line.startswith("ID")), "")
        ac_line = next((line for line in lines if line.startswith("AC")), "")
        precursor_name = id_line.split()[1] if len(id_line.split()) > 1 else ""
        precursor_acc = ac_line.replace("AC", "", 1).replace(";", "").strip()
        hgnc = ""
        entrez = ""
        for line in lines:
            if line.startswith("DR   HGNC;"):
                parts = [p.strip() for p in line.split(";")]
                hgnc = parts[-1].strip(".") if parts else ""
            elif line.startswith("DR   ENTREZGENE;"):
                parts = [p.strip() for p in line.split(";")]
                entrez = parts[1] if len(parts) > 1 else ""
        rows.append(
            {
                "id": precursor_acc,
                "name": precursor_name,
                "mirna_product_type": "precursor_hairpin",
                "species_id": "NCBITaxon:9606",
                "mirbase_mature_accession": "",
                "mirbase_mature_name": "",
                "mirbase_precursor_accession": precursor_acc,
                "mirbase_precursor_name": precursor_name,
                "arm": "",
                "ensembl_gene_id": "",
                "ensembl_transcript_id": "",
                "rnacentral_id": "",
                "sequence": "",
                "source": "miRBase",
                "source_release": source_release,
                "mapping_confidence": "source_native",
                "mapping_method": "miRBase_miRNA.dat",
                "hgnc_symbol": hgnc,
                "entrezgene_id": entrez,
            }
        )
        current: dict[str, str] | None = None
        for line in lines:
            if line.startswith("FT   miRNA"):
                current = {}
            elif current is not None and line.startswith("FT"):
                if "/accession=" in line:
                    current["accession"] = line.split('"')[1]
                elif "/product=" in line:
                    current["product"] = line.split('"')[1]
                elif line.startswith("XX"):
                    current = None
            if current is not None and {"accession", "product"}.issubset(current):
                mature_acc = current["accession"]
                mature_name = current["product"]
                mature_rows.append(
                    {
                        "id": mature_acc,
                        "name": mature_name,
                        "mirna_product_type": "mature",
                        "species_id": "NCBITaxon:9606",
                        "mirbase_mature_accession": mature_acc,
                        "mirbase_mature_name": mature_name,
                        "mirbase_precursor_accession": precursor_acc,
                        "mirbase_precursor_name": precursor_name,
                        "arm": _arm(mature_name),
                        "ensembl_gene_id": "",
                        "ensembl_transcript_id": "",
                        "rnacentral_id": "",
                        "sequence": "",
                        "source": "miRBase",
                        "source_release": source_release,
                        "mapping_confidence": "source_native",
                        "mapping_method": "miRBase_miRNA.dat",
                        "hgnc_symbol": hgnc,
                        "entrezgene_id": entrez,
                    }
                )
                current = None
    catalog = pd.DataFrame(rows + mature_rows).drop_duplicates(subset=["id"], keep="last")
    return catalog[CATALOG_COLUMNS + ["hgnc_symbol", "entrezgene_id"]], pd.DataFrame(mature_rows)


def biomart_query(attributes: list[str], filters: dict[str, str] | None = None, *, timeout: int = 120) -> pd.DataFrame:
    filters = filters or {}
    filter_xml = "".join(f'<Filter name="{k}" value="{v}" />' for k, v in filters.items())
    attr_xml = "".join(f'<Attribute name="{a}" />' for a in attributes)
    query = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Query>
<Query virtualSchemaName="default" formatter="TSV" header="1" uniqueRows="0" count="" datasetConfigVersion="0.6">
  <Dataset name="hsapiens_gene_ensembl" interface="default">
    {filter_xml}
    {attr_xml}
  </Dataset>
</Query>"""
    resp = requests.get(BIOMART_URL + "?" + urlencode({"query": query}), timeout=timeout)
    resp.raise_for_status()
    from io import StringIO

    return pd.read_csv(StringIO(resp.text), sep="\t", dtype=str).fillna("")


def build_biomart_mirbase_mapping(biomart_df: pd.DataFrame, *, source_release: str = "Ensembl BioMart current 2026-06-22") -> pd.DataFrame:
    if len(biomart_df.columns) == 1 and str(biomart_df.columns[0]).startswith("Query ERROR"):
        return pd.DataFrame(columns=MAPPING_COLUMNS)
    cols = {c.lower(): c for c in biomart_df.columns}
    def col(name: str) -> str:
        return cols.get(name.lower(), name)

    rows = []
    for _, row in biomart_df.iterrows():
        enst = _nonnull(row.get(col("Transcript stable ID"), row.get("ensembl_transcript_id")))
        ensg = _nonnull(row.get(col("Gene stable ID"), row.get("ensembl_gene_id")))
        mirbase_acc = _nonnull(row.get(col("miRBase accession"), row.get("mirbase_accession")))
        mirbase_id = _nonnull(row.get(col("miRBase ID"), row.get("mirbase_id")))
        rnacentral = _nonnull(row.get(col("RNAcentral ID"), row.get("rnacentral")))
        if not enst or not mirbase_acc:
            continue
        rows.append(
            {
                "ensembl_transcript_id": enst,
                "ensembl_gene_id": ensg,
                "mirbase_accession": mirbase_acc,
                "mirbase_name": mirbase_id,
                "mirbase_entity_type": "precursor_hairpin" if mirbase_acc.startswith("MI") else "ambiguous",
                "rnacentral_id": rnacentral,
                "mapping_method": "Ensembl_BioMart_xref",
                "mapping_confidence": "exact",
                "source_dataset": "Ensembl BioMart miRBase xref",
                "source_release": source_release,
                "source_record_id": f"{enst}|{mirbase_acc}",
                "species_id": "NCBITaxon:9606",
                "notes_json": json.dumps(
                    {
                        "external_gene_name": _nonnull(row.get(col("Gene name"))),
                        "external_transcript_name": _nonnull(row.get(col("Transcript name"))),
                        "mirbase_trans_name": _nonnull(row.get(col("miRBase transcript name ID"))),
                    },
                    sort_keys=True,
                ),
                "is_same_entity_as_transcript": True,
            }
        )
    return pd.DataFrame(rows, columns=MAPPING_COLUMNS).drop_duplicates()


def build_hgnc_mirbase_mapping(
    *,
    gene_has_transcript_path: str | Path,
    gene_nodes_path: str | Path,
    mirbase_catalog: pd.DataFrame,
    source_release: str = "canonical gene_has_transcript + miRBase/HGNC 2026-06-22",
) -> pd.DataFrame:
    """Build conservative ENST<->miRBase precursor aliases via HGNC symbols.

    This is used when BioMart direct external-reference extraction is unavailable
    or incomplete. It only emits rows where all three joins are one-to-one:
    Ensembl gene -> one miRNA-biotype transcript, HGNC symbol -> one miRBase
    precursor, and miRBase precursor -> one Ensembl gene. Everything else is
    left out so the downstream builder's rejected table remains honest rather
    than pretending a name-only mapping is exact.
    """
    ght = pd.read_parquet(gene_has_transcript_path)
    genes = pd.read_parquet(gene_nodes_path)
    mirna_edges = ght[ght.get("transcript_biotype", pd.Series(dtype=str)).astype(str).str.lower().eq("mirna")].copy()
    gene_cols = [c for c in ["id", "gene_name", "name", "ncbi_gene_id", "hgnc_id"] if c in genes.columns]
    gene_lookup = genes[gene_cols].copy()
    joined = mirna_edges.merge(gene_lookup, left_on="x_id", right_on="id", how="left", suffixes=("", "_gene"))
    joined["hgnc_symbol"] = joined.get("gene_name", pd.Series(dtype=str)).map(_nonnull)
    joined.loc[joined["hgnc_symbol"].eq(""), "hgnc_symbol"] = joined.get("name", pd.Series(dtype=str)).map(_nonnull)
    joined["hgnc_symbol_norm"] = joined["hgnc_symbol"].str.upper()

    precursors = mirbase_catalog[mirbase_catalog["mirna_product_type"].eq("precursor_hairpin")].copy()
    precursors["hgnc_symbol_norm"] = precursors.get("hgnc_symbol", pd.Series(dtype=str)).map(_nonnull).str.upper()
    precursors = precursors[precursors["hgnc_symbol_norm"].ne("")]

    gene_tx_counts = joined.groupby("x_id")["y_id"].nunique()
    symbol_precursor_counts = precursors.groupby("hgnc_symbol_norm")["id"].nunique()
    precursor_symbol_counts = precursors.groupby("id")["hgnc_symbol_norm"].nunique()
    joined_symbol_counts = joined.groupby("hgnc_symbol_norm")["x_id"].nunique()

    rows = []
    for _, row in joined.iterrows():
        symbol = _nonnull(row.get("hgnc_symbol_norm"))
        if not symbol:
            continue
        hits = precursors[precursors["hgnc_symbol_norm"].eq(symbol)]
        if hits.empty:
            continue
        strict_one_to_one = (
            gene_tx_counts.get(row["x_id"], 0) == 1
            and joined_symbol_counts.get(symbol, 0) == 1
            and symbol_precursor_counts.get(symbol, 0) == 1
        )
        for _, hit in hits.iterrows():
            hit_is_strict = strict_one_to_one and precursor_symbol_counts.get(hit["id"], 0) == 1
            reasons = []
            if gene_tx_counts.get(row["x_id"], 0) != 1:
                reasons.append("ensembl_gene_has_multiple_mirna_transcripts")
            if joined_symbol_counts.get(symbol, 0) != 1:
                reasons.append("hgnc_symbol_maps_to_multiple_ensembl_genes")
            if symbol_precursor_counts.get(symbol, 0) != 1:
                reasons.append("hgnc_symbol_maps_to_multiple_mirbase_precursors")
            if precursor_symbol_counts.get(hit["id"], 0) != 1:
                reasons.append("mirbase_precursor_maps_to_multiple_hgnc_symbols")
            rows.append(
                {
                "ensembl_transcript_id": _nonnull(row.get("y_id")),
                "ensembl_gene_id": _nonnull(row.get("x_id")),
                "mirbase_accession": _nonnull(hit.get("id")),
                "mirbase_name": _nonnull(hit.get("name")),
                "mirbase_entity_type": "precursor_hairpin",
                "rnacentral_id": "",
                "mapping_method": "canonical_gene_has_transcript_HGNC_to_miRBase_DR_HGNC",
                "mapping_confidence": "high" if hit_is_strict else "ambiguous",
                "source_dataset": "canonical gene_has_transcript + miRBase DR HGNC",
                "source_release": source_release,
                "source_record_id": f"{row.get('y_id')}|{hit.get('id')}",
                "species_id": "NCBITaxon:9606",
                "notes_json": json.dumps(
                    {
                        "hgnc_symbol": _nonnull(row.get("hgnc_symbol")),
                        "rule": "one Ensembl miRNA transcript for gene and one miRBase precursor for HGNC symbol",
                        "reject_reasons": reasons,
                    },
                    sort_keys=True,
                ),
                "is_same_entity_as_transcript": bool(hit_is_strict),
            }
            )
    return pd.DataFrame(rows, columns=MAPPING_COLUMNS).drop_duplicates()


def build_gene_map(gene_df: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    cols = {c.lower(): c for c in gene_df.columns}
    def col(name: str) -> str:
        return cols.get(name.lower(), name)
    entrez_to_ensg: dict[str, str] = {}
    symbol_counts = Counter(_nonnull(v).upper() for v in gene_df.get(col("Gene name"), pd.Series(dtype=str)) if _nonnull(v))
    symbol_to_ensg: dict[str, str] = {}
    for _, row in gene_df.iterrows():
        ensg = _nonnull(row.get(col("Gene stable ID"), row.get("ensembl_gene_id")))
        entrez = _nonnull(row.get(col("NCBI gene (formerly Entrezgene) ID"), row.get("entrezgene_id")))
        symbol = _nonnull(row.get(col("Gene name"), row.get("external_gene_name"))).upper()
        if ensg and entrez and entrez not in entrez_to_ensg:
            entrez_to_ensg[entrez] = ensg
        if ensg and symbol and symbol_counts[symbol] == 1:
            symbol_to_ensg[symbol] = ensg
    return entrez_to_ensg, symbol_to_ensg


def normalise_mirtarbase(
    xlsx_path: str | Path,
    mirbase_catalog: pd.DataFrame,
    gene_df: pd.DataFrame,
    *,
    source_release: str = "miRTarBase 9.0 2025-04-22",
    source_url: str = "https://mirtarbase.cuhk.edu.cn/~miRTarBase/miRTarBase_2025/cache/download/9.0/miRTarBase_MTI.xlsx",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_excel(xlsx_path, dtype=str).fillna("")
    entrez_to_ensg, symbol_to_ensg = build_gene_map(gene_df)
    mature_catalog = mirbase_catalog[mirbase_catalog["mirna_product_type"].eq("mature")].copy()
    name_counts = Counter(mature_catalog["name"].map(_normalise_mirna_name))
    name_to_row = {
        _normalise_mirna_name(r["name"]): r
        for _, r in mature_catalog.iterrows()
        if name_counts[_normalise_mirna_name(r["name"])] == 1
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    human = df[(df["Species (miRNA)"].eq("Homo sapiens")) & (df["Species (Target Gene)"].eq("Homo sapiens"))].copy()
    for idx, row in human.iterrows():
        mirna_name = _nonnull(row.get("miRNA"))
        mirna_hit = name_to_row.get(_normalise_mirna_name(mirna_name))
        entrez = _nonnull(row.get("Target Gene (Entrez ID")) or _nonnull(row.get("Target Gene (Entrez ID)"))
        target_symbol = _nonnull(row.get("Target Gene"))
        target_ensg = entrez_to_ensg.get(entrez) or symbol_to_ensg.get(target_symbol.upper(), "")
        reasons = []
        if mirna_hit is None:
            reasons.append("unresolved_or_nonunique_mirbase_mature_name")
        if not target_ensg:
            reasons.append("unresolved_target_gene_to_ensembl")
        base_record_id = _nonnull(row.get("miRTarBase ID")) or "miRTarBase"
        pmid = _nonnull(row.get("References (PMID)"))
        assay = _nonnull(row.get("Experiments"))
        payload = {
            "source_record_id": f"{base_record_id}|row:{idx}|pmid:{pmid}|assay:{assay}",
            "original_mirna_name": mirna_name,
            "original_target_name": target_symbol,
            "original_target_id": entrez,
            "experiments": assay,
            "support_type": _nonnull(row.get("Support Type")),
            "pmid": pmid,
            "reject_reasons": ";".join(reasons),
        }
        if reasons or mirna_hit is None:
            rejected.append(payload)
            continue
        accepted.append(
            {
                "source": "miRTarBase",
                "source_dataset": "miRTarBase_MTI",
                "source_release": source_release,
                "source_record_id": payload["source_record_id"],
                "mirna_id": mirna_hit["id"],
                "mirna_name": mirna_hit["name"],
                "mirbase_mature_accession": mirna_hit["mirbase_mature_accession"],
                "mirbase_mature_name": mirna_hit["mirbase_mature_name"],
                "mirbase_precursor_accession": mirna_hit["mirbase_precursor_accession"],
                "mirna_product_type": "mature",
                "target_endpoint_level": "gene",
                "target_gene_id": target_ensg,
                "original_target_id": entrez,
                "original_target_name": target_symbol,
                "target_id_namespace": "NCBI Gene",
                "target_mapping_method": "BioMart_entrez_gene_xref" if entrez in entrez_to_ensg else "BioMart_unique_gene_symbol",
                "target_mapping_confidence": "exact" if entrez in entrez_to_ensg else "high_symbol_unique",
                "species_id": "NCBITaxon:9606",
                "species_name": "Homo sapiens",
                "assay": payload["experiments"],
                "support_type": payload["support_type"],
                "predicate": "validated_target",
                "evidence_type": "experimental_validated",
                "pmid": payload["pmid"],
                "confidence": payload["support_type"],
                "license_checked": True,
                "source_url": source_url,
            }
        )
    return pd.DataFrame(accepted, columns=TARGET_COLUMNS), pd.DataFrame(rejected)


def write_source_audit(path: str | Path, *, inputs: dict[str, Any], counts: dict[str, Any]) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Real-source staged miRNA ingestion audit; no canonical KG promotion.",
        "sources": [
            {
                "name": "miRBase miRNA.dat",
                "url": "https://mirbase.org/download/miRNA.dat",
                "approval_status": "approved",
                "license_checked": True,
                "license_note": "miRBase public download; cite miRBase. Terms require citation, no credential gate observed for miRNA.dat.",
                "schema_checked": True,
                "endpoint_policy": "catalog and precursor/mature source-native identifiers; not target evidence",
            },
            {
                "name": "Ensembl BioMart miRBase/RNAcentral xrefs",
                "url": BIOMART_URL,
                "approval_status": "approved",
                "license_checked": True,
                "license_note": "Ensembl BioMart public API; use only for staged mapping audit and preserve source dataset/retrieval date.",
                "schema_checked": True,
                "endpoint_policy": "ENST transcript to miRBase/RNAcentral aliases only when BioMart gives direct xrefs",
            },
            {
                "name": "miRTarBase 9.0 MTI XLSX",
                "url": "https://mirtarbase.cuhk.edu.cn/~miRTarBase/miRTarBase_2025/cache/download/9.0/miRTarBase_MTI.xlsx",
                "approval_status": "recommended",
                "license_checked": True,
                "license_note": "Public XLSX download responded without credentials; staged use only with source/citation retained; review before canonical promotion.",
                "schema_checked": True,
                "endpoint_policy": "gene-level human MTIs only; target endpoint is Entrez/gene symbol, so build mirna_targets_gene, not transcript edges",
            },
            {
                "name": "DIANA-TarBase v8",
                "url": "https://dianalab.e-ce.uth.gr/html/diana/web/index.php?r=tarbasev8%2Fdownloaddataform",
                "approval_status": "defer",
                "license_checked": False,
                "license_note": "Homepage/download-data form inspected; static bulk data URL not identified in this run. Defer ingestion until terms/direct export are confirmed.",
                "schema_checked": False,
                "endpoint_policy": "expected gene-level MTIs, but not ingested in this tranche",
            },
        ],
        "inputs": inputs,
        "counts": counts,
        "choice": "Use miRBase + Ensembl BioMart + miRTarBase 9.0 as first staged real source. Defer DIANA-TarBase until direct bulk export/licensing are confirmed.",
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mirbase-dat", required=True)
    parser.add_argument("--mirtarbase-xlsx", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--use-live-biomart", action="store_true")
    parser.add_argument("--biomart-mirbase-cache", default=None)
    parser.add_argument("--biomart-gene-cache", default=None)
    parser.add_argument("--gene-has-transcript", default=None, help="Canonical/staged gene_has_transcript parquet for conservative HGNC fallback mapping")
    parser.add_argument("--gene-nodes", default=None, help="Canonical/staged gene nodes parquet for conservative HGNC fallback mapping")
    args = parser.parse_args(argv)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    catalog, _ = parse_mirbase_dat(args.mirbase_dat)
    catalog_path = out / "mirbase_catalog.parquet"
    catalog[CATALOG_COLUMNS].to_parquet(catalog_path, index=False)

    mirbase_cache = Path(args.biomart_mirbase_cache) if args.biomart_mirbase_cache else out / "biomart_mirbase_xrefs.tsv"
    gene_cache = Path(args.biomart_gene_cache) if args.biomart_gene_cache else out / "biomart_gene_xrefs.tsv"
    if args.use_live_biomart or not mirbase_cache.exists():
        biomart_mirbase = biomart_query(
            [
                "ensembl_gene_id",
                "ensembl_transcript_id",
                "external_gene_name",
                "external_transcript_name",
                "transcript_biotype",
                "mirbase_id",
                "mirbase_accession",
                "mirbase_trans_name",
                "rnacentral",
            ],
            {"transcript_biotype": "miRNA"},
        )
        biomart_mirbase.to_csv(mirbase_cache, sep="\t", index=False)
    else:
        biomart_mirbase = pd.read_csv(mirbase_cache, sep="\t", dtype=str).fillna("")
    if args.use_live_biomart or not gene_cache.exists():
        gene_df = biomart_query(["ensembl_gene_id", "external_gene_name", "entrezgene_id"], timeout=180)
        gene_df.to_csv(gene_cache, sep="\t", index=False)
    else:
        gene_df = pd.read_csv(gene_cache, sep="\t", dtype=str).fillna("")

    mapping = build_biomart_mirbase_mapping(biomart_mirbase)
    mapping_method = "biomart_direct_xref"
    if mapping.empty and args.gene_has_transcript and args.gene_nodes:
        mapping = build_hgnc_mirbase_mapping(
            gene_has_transcript_path=args.gene_has_transcript,
            gene_nodes_path=args.gene_nodes,
            mirbase_catalog=catalog,
        )
        mapping_method = "canonical_HGNC_miRBase_fallback"
    mapping_path = out / "transcript_mirbase_mapping.parquet"
    mapping.to_parquet(mapping_path, index=False)

    targets, rejected_targets = normalise_mirtarbase(args.mirtarbase_xlsx, catalog, gene_df)
    targets_path = out / "mirtarbase_targets_gene_normalized.parquet"
    rejected_path = out / "mirtarbase_targets_rejected.parquet"
    targets.to_parquet(targets_path, index=False)
    rejected_targets.to_parquet(rejected_path, index=False)

    counts = {
        "mirbase_catalog_rows": int(len(catalog)),
        "mirbase_precursor_rows": int(catalog["mirna_product_type"].eq("precursor_hairpin").sum()),
        "mirbase_mature_rows": int(catalog["mirna_product_type"].eq("mature").sum()),
        "biomart_mirbase_rows": int(len(biomart_mirbase)),
        "transcript_mirbase_mapping_rows": int(len(mapping)),
        "transcript_mirbase_mapping_method": mapping_method,
        "mirtarbase_accepted_human_gene_rows": int(len(targets)),
        "mirtarbase_rejected_human_rows": int(len(rejected_targets)),
        "mirtarbase_unique_edges_before_builder": int(targets[["mirna_id", "target_gene_id"]].drop_duplicates().shape[0]) if not targets.empty else 0,
    }
    write_source_audit(
        out / "source_audit.json",
        inputs={
            "mirbase_dat": str(args.mirbase_dat),
            "mirtarbase_xlsx": str(args.mirtarbase_xlsx),
            "biomart_mirbase_cache": str(mirbase_cache),
            "biomart_gene_cache": str(gene_cache),
        },
        counts=counts,
    )
    (out / "prepare_summary.json").write_text(json.dumps({"outputs": {
        "catalog": str(catalog_path),
        "mapping": str(mapping_path),
        "targets": str(targets_path),
        "rejected_targets": str(rejected_path),
        "source_audit": str(out / "source_audit.json"),
    }, "counts": counts}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
