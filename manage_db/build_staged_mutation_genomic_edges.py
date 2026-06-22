"""Stage source-native mutation containment/consequence/overlap edges.

This builder is intentionally staged-only: it emits direct genomic
``mutation_in_gene`` and transcript-consequence ``mutation_affects_transcript``
from OpenTargets/Ensembl-VEP variant transcript consequences, plus bounded
``mutation_overlaps_enhancer`` for variants that already have downstream
association evidence in the current KG.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from manage_db import kg_evidence
from manage_db.credibility import Credibility
from manage_db.kg_schema import NodeType
from manage_db.kg_storage import EDGE_PARQUET_COLUMNS

OT_RELEASE = "26.03"
OT_OUTPUT = f"https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/{OT_RELEASE}/output"
ASSOCIATION_RELATIONS = (
    "mutation_associated_disease",
    "mutation_associated_phenotype",
    "mutation_affects_molecule_response",
)

EDGE_COLUMNS = [name for name, _ in EDGE_PARQUET_COLUMNS]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _list_ftp_parquets(dataset: str) -> list[str]:
    url = f"{OT_OUTPUT}/{dataset}/"
    try:
        html = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        return []
    return [url + name for name in re.findall(r'href="([^"]+\.parquet)"', html)]


def write_source_audit(stage_root: Path, variant_files: list[Path], kg_cache_root: Path) -> dict[str, object]:
    datasets = [
        "variant",
        "enhancer_to_gene",
        "evidence_eva",
        "evidence_eva_somatic",
        "evidence_gwas_credible_sets",
        "evidence_uniprot_variants",
        "pharmacogenomics",
        "credible_set",
        "so",
    ]
    audit: dict[str, object] = {
        "created_at": _now(),
        "release": f"OpenTargets Platform {OT_RELEASE}",
        "source_policy": {
            "mutation_in_gene": "OpenTargets variant transcriptConsequences targetId only; physical/genomic containment/consequence, no L2G/GWAS association rows.",
            "mutation_affects_transcript": "OpenTargets variant transcriptConsequences transcriptId only; ENST transcript-level consequences with Sequence Ontology IDs preserved.",
            "mutation_overlaps_enhancer": "Coordinate overlap against current enhancer interval nodes only for variants with existing disease/phenotype/drug-response KG evidence.",
        },
        "official_opentargets_ftp": {dataset: len(_list_ftp_parquets(dataset)) for dataset in datasets},
        "local_variant_files": [str(p) for p in variant_files],
        "local_kg_cache": {},
    }
    for rel in ASSOCIATION_RELATIONS:
        p = kg_cache_root / "edges" / f"{rel}.parquet"
        entry: dict[str, object] = {"path": str(p), "exists": p.exists()}
        if p.exists():
            entry["rows"] = pq.ParquetFile(p).metadata.num_rows
        audit["local_kg_cache"][f"edges/{rel}.parquet"] = entry
    for node in ("gene", "transcript", "mutation", "enhancer"):
        p = kg_cache_root / "nodes" / f"{node}.parquet"
        entry = {"path": str(p), "exists": p.exists()}
        if p.exists():
            entry["rows"] = pq.ParquetFile(p).metadata.num_rows
            entry["columns"] = pq.ParquetFile(p).schema_arrow.names
        audit["local_kg_cache"][f"nodes/{node}.parquet"] = entry
    (stage_root / "source_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True))
    return audit


def _scalar_list(value: object) -> list[object]:
    if value is None or value is pd.NA:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist"):
        out = value.tolist()
        return out if isinstance(out, list) else [out]
    return [value]


def _first_rs(rs_ids: object) -> str | None:
    for rs in _scalar_list(rs_ids):
        if rs:
            return str(rs)
    return None


def _consequence_ids(consequence: dict[str, object]) -> list[str]:
    vals = consequence.get("variantFunctionalConsequenceIds")
    return [str(x) for x in _scalar_list(vals) if x]


def _variant_coord(row: dict[str, object]) -> tuple[str | None, int | None]:
    chrom = row.get("chromosome")
    pos = row.get("position")
    if chrom is None or pos is None or pd.isna(pos):
        vid = str(row.get("variantId") or "")
        m = re.match(r"^(?:chr)?([^_]+)_(\d+)_", vid)
        if not m:
            return None, None
        return m.group(1), int(m.group(2))
    return str(chrom).removeprefix("chr"), int(pos)


def _edge(x_id: str, x_type: str, y_id: str, y_type: str, relation: str, display: str, source: str) -> dict[str, object]:
    return {
        "x_id": x_id,
        "x_type": x_type,
        "y_id": y_id,
        "y_type": y_type,
        "relation": relation,
        "display_relation": display,
        "source": source,
        "credibility": int(Credibility.ESTABLISHED_FACT),
    }


def _evidence(edge: dict[str, object], source_dataset: str, source_record_id: str, predicate: str, *, text: dict[str, object] | None = None, score: float | None = None, method: str = "source_native_builder") -> dict[str, object]:
    return {
        "relation": edge["relation"],
        "x_id": edge["x_id"],
        "x_type": edge["x_type"],
        "y_id": edge["y_id"],
        "y_type": edge["y_type"],
        "evidence_type": "database_record",
        "source": "OpenTargets",
        "source_dataset": source_dataset,
        "source_record_id": source_record_id,
        "evidence_score": score,
        "predicate": predicate,
        "text_span": json.dumps(text or {}, sort_keys=True),
        "extraction_method": method,
        "license": "OpenTargets Platform data",
        "release": OT_RELEASE,
        "created_at": _now(),
    }


def build_edges_from_variants(variant_table: pa.Table, supported_for_enhancer: set[str], enhancer_nodes: pd.DataFrame | None, max_variants: int | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame, dict[str, object]]:
    rows = variant_table.to_pylist()
    if max_variants is not None:
        rows = rows[:max_variants]

    edge_rows: dict[str, list[dict[str, object]]] = {"mutation_in_gene": [], "mutation_affects_transcript": [], "mutation_overlaps_enhancer": []}
    ev_rows: dict[str, list[dict[str, object]]] = {k: [] for k in edge_rows}
    mutation_rows: list[dict[str, object]] = []
    variant_positions: list[dict[str, object]] = []

    for row_idx, row in enumerate(rows):
        variant_id = row.get("variantId")
        if not isinstance(variant_id, str) or not variant_id:
            continue
        chrom, pos = _variant_coord(row)
        mutation_rows.append({
            "id": variant_id,
            "hgvs": row.get("hgvsId"),
            "clinvar_id": _first_rs(row.get("rsIds")),
            "gnomad_id": variant_id,
            "name": _first_rs(row.get("rsIds")) or row.get("hgvsId") or variant_id,
            "source": "OpenTargets/variant",
        })
        if chrom and pos:
            variant_positions.append({"variant_id": variant_id, "chromosome": chrom, "position": pos, "ref": row.get("referenceAllele"), "alt": row.get("alternateAllele")})
        for cons_idx, consequence in enumerate(_scalar_list(row.get("transcriptConsequences"))):
            if not isinstance(consequence, dict):
                continue
            cons_ids = _consequence_ids(consequence)
            gene_id = consequence.get("targetId")
            transcript_id = consequence.get("transcriptId")
            base_text = {
                "variant_id": variant_id,
                "chromosome": chrom,
                "position": pos,
                "reference_allele": row.get("referenceAllele"),
                "alternate_allele": row.get("alternateAllele"),
                "hgvs_id": row.get("hgvsId"),
                "consequence_ids": cons_ids,
                "impact": consequence.get("impact"),
                "biotype": consequence.get("biotype"),
                "is_ensembl_canonical": consequence.get("isEnsemblCanonical"),
                "distance_from_tss": consequence.get("distanceFromTss"),
                "distance_from_footprint": consequence.get("distanceFromFootprint"),
                "approved_symbol": consequence.get("approvedSymbol"),
            }
            if isinstance(gene_id, str) and gene_id.startswith("ENSG"):
                e = _edge(variant_id, NodeType.MUTATION.value, gene_id, NodeType.GENE.value, "mutation_in_gene", "in gene", "OpenTargets/variant transcriptConsequences")
                edge_rows["mutation_in_gene"].append(e)
                ev_rows["mutation_in_gene"].append(_evidence(e, "variant", f"variant:{variant_id}:tc:{cons_idx}:gene:{gene_id}", "variant_transcript_consequence_target_gene", text=base_text, score=consequence.get("consequenceScore")))
            if cons_ids and isinstance(transcript_id, str) and transcript_id.startswith("ENST"):
                e = _edge(variant_id, NodeType.MUTATION.value, transcript_id, NodeType.TRANSCRIPT.value, "mutation_affects_transcript", "affects transcript", "OpenTargets/variant transcriptConsequences")
                edge_rows["mutation_affects_transcript"].append(e)
                ev_rows["mutation_affects_transcript"].append(_evidence(e, "variant", f"variant:{variant_id}:tc:{cons_idx}:transcript:{transcript_id}", "variant_transcript_consequence", text={**base_text, "transcript_id": transcript_id}, score=consequence.get("consequenceScore")))

    if enhancer_nodes is not None and not enhancer_nodes.empty and variant_positions:
        vp = pd.DataFrame(variant_positions)
        vp = vp[vp["variant_id"].isin(supported_for_enhancer)]
        if not vp.empty:
            enh = enhancer_nodes.copy()
            enh["chromosome"] = enh["chromosome"].astype(str).str.removeprefix("chr")
            enh["start"] = pd.to_numeric(enh["start"], errors="coerce")
            enh["end"] = pd.to_numeric(enh["end"], errors="coerce")
            for chrom, variants_chr in vp.groupby("chromosome"):
                enh_chr = enh[enh["chromosome"] == str(chrom)]
                if enh_chr.empty:
                    continue
                for v in variants_chr.itertuples(index=False):
                    overlaps = enh_chr[(enh_chr["start"] <= int(v.position)) & (enh_chr["end"] >= int(v.position))]
                    for h in overlaps.itertuples(index=False):
                        e = _edge(v.variant_id, NodeType.MUTATION.value, str(h.id), NodeType.ENHANCER.value, "mutation_overlaps_enhancer", "overlaps enhancer", "OpenTargets/variant + current enhancer intervals")
                        edge_rows["mutation_overlaps_enhancer"].append(e)
                        text = {"variant_id": v.variant_id, "chromosome": chrom, "position": int(v.position), "reference_allele": v.ref, "alternate_allele": v.alt, "enhancer_id": str(h.id), "enhancer_start": int(h.start), "enhancer_end": int(h.end), "downstream_association_gate": True}
                        ev_rows["mutation_overlaps_enhancer"].append(_evidence(e, "variant+enhancer_interval", f"variant_enhancer_overlap:{v.variant_id}:{h.id}", "bounded_variant_overlaps_enhancer_interval", text=text, method="coordinate_overlap_after_downstream_association_gate"))

    edges = {rel: pd.DataFrame(rows).drop_duplicates(subset=["x_id", "y_id", "relation", "source"]) if rows else pd.DataFrame(columns=EDGE_COLUMNS) for rel, rows in edge_rows.items()}
    evidence = {rel: pd.DataFrame(rows) if rows else pd.DataFrame(columns=[name for name, _ in kg_evidence.EVIDENCE_PARQUET_COLUMNS]) for rel, rows in ev_rows.items()}
    nodes = pd.DataFrame(mutation_rows).drop_duplicates(subset=["id"]) if mutation_rows else pd.DataFrame(columns=["id", "hgvs", "clinvar_id", "gnomad_id", "name", "source"])
    summary = {"input_variants": len(rows), "supported_variants_for_enhancer_gate": len(supported_for_enhancer), "mutation_nodes": len(nodes), "edge_rows": {rel: len(df) for rel, df in edges.items()}, "evidence_rows": {rel: len(df) for rel, df in evidence.items()}}
    return edges, evidence, nodes, summary


def load_supported_variants(kg_cache_root: Path, candidate_variants: set[str]) -> set[str]:
    supported: set[str] = set()
    for rel in ASSOCIATION_RELATIONS:
        p = kg_cache_root / "edges" / f"{rel}.parquet"
        if not p.exists():
            continue
        table = pq.read_table(p, columns=["x_id"])
        ids = set(table.column("x_id").to_pylist())
        supported |= (ids & candidate_variants)
    return supported


def load_enhancer_slice(enhancer_path: Path, positions: pd.DataFrame, padding: int = 0) -> pd.DataFrame:
    if not enhancer_path.exists() or positions.empty:
        return pd.DataFrame(columns=["id", "chromosome", "start", "end"])
    pieces = []
    pf = pq.ParquetFile(enhancer_path)
    cols = [c for c in ["id", "chromosome", "start", "end"] if c in pf.schema_arrow.names]
    full = pq.read_table(enhancer_path, columns=cols).to_pandas()
    full["chromosome"] = full["chromosome"].astype(str).str.removeprefix("chr")
    full["start"] = pd.to_numeric(full["start"], errors="coerce")
    full["end"] = pd.to_numeric(full["end"], errors="coerce")
    for chrom, grp in positions.groupby("chromosome"):
        lo = int(grp["position"].min()) - padding
        hi = int(grp["position"].max()) + padding
        pieces.append(full[(full["chromosome"] == str(chrom)) & (full["start"] <= hi) & (full["end"] >= lo)])
    return pd.concat(pieces, ignore_index=True).drop_duplicates(subset=["id"]) if pieces else pd.DataFrame(columns=cols)


def write_outputs(stage_root: Path, edges: dict[str, pd.DataFrame], evidence: dict[str, pd.DataFrame], nodes: pd.DataFrame, summary: dict[str, object]) -> None:
    (stage_root / "edges").mkdir(parents=True, exist_ok=True)
    (stage_root / "evidence").mkdir(parents=True, exist_ok=True)
    (stage_root / "nodes").mkdir(parents=True, exist_ok=True)
    if not nodes.empty:
        pq.write_table(pa.Table.from_pandas(nodes, preserve_index=False), stage_root / "nodes" / "mutation.parquet")
    for rel, df in edges.items():
        df = df.reindex(columns=EDGE_COLUMNS)
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), stage_root / "edges" / f"{rel}.parquet")
        ev = evidence[rel]
        ev = kg_evidence._coerce_evidence_frame(ev, rel) if not ev.empty else ev.reindex(columns=[name for name, _ in kg_evidence.EVIDENCE_PARQUET_COLUMNS])
        pq.write_table(pa.Table.from_pandas(ev, preserve_index=False), stage_root / "evidence" / f"{rel}.parquet")
    (stage_root / "manifest.json").write_text(json.dumps({"created_at": _now(), **summary}, indent=2, sort_keys=True))


def validate_outputs(stage_root: Path, kg_cache_root: Path) -> dict[str, object]:
    out: dict[str, object] = {"relations": {}, "passed": True}
    endpoint_nodes = {
        "mutation": stage_root / "nodes" / "mutation.parquet",
        "gene": kg_cache_root / "nodes" / "gene.parquet",
        "transcript": kg_cache_root / "nodes" / "transcript.parquet",
        "enhancer": kg_cache_root / "nodes" / "enhancer.parquet",
    }
    node_sets = {k: set(pq.read_table(p, columns=["id"]).column("id").to_pylist()) for k, p in endpoint_nodes.items() if p.exists()}
    for rel in ("mutation_in_gene", "mutation_affects_transcript", "mutation_overlaps_enhancer"):
        ep = stage_root / "edges" / f"{rel}.parquet"
        vp = stage_root / "evidence" / f"{rel}.parquet"
        edges = pq.read_table(ep).to_pandas() if ep.exists() else pd.DataFrame(columns=EDGE_COLUMNS)
        ev = pq.read_table(vp).to_pandas() if vp.exists() else pd.DataFrame()
        edge_keys = set((edges["relation"] + "|" + edges["x_id"] + "|" + edges["y_id"]).astype(str)) if not edges.empty else set()
        ev_keys = set(ev["edge_key"].astype(str)) if not ev.empty else set()
        target_type = {"mutation_in_gene": "gene", "mutation_affects_transcript": "transcript", "mutation_overlaps_enhancer": "enhancer"}[rel]
        missing_x = sorted(set(edges["x_id"].astype(str)) - node_sets.get("mutation", set()))[:10] if not edges.empty else []
        missing_y = sorted(set(edges["y_id"].astype(str)) - node_sets.get(target_type, set()))[:10] if not edges.empty else []
        info = {"edges": len(edges), "evidence": len(ev), "edges_without_evidence": len(edge_keys - ev_keys), "evidence_without_edge": len(ev_keys - edge_keys), "missing_x_examples": missing_x, "missing_y_examples": missing_y}
        info["passed"] = not missing_x and not missing_y and info["edges_without_evidence"] == 0 and info["evidence_without_edge"] == 0
        out["relations"][rel] = info
        out["passed"] = out["passed"] and info["passed"]
    (stage_root / "validation.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant-file", action="append", type=Path, required=True)
    ap.add_argument("--kg-cache-root", type=Path, default=Path(".omoc/gcs-cache/kg-v2"))
    ap.add_argument("--stage-root", type=Path, required=True)
    ap.add_argument("--max-variants", type=int, default=25000)
    args = ap.parse_args(argv)

    args.stage_root.mkdir(parents=True, exist_ok=True)
    write_source_audit(args.stage_root, args.variant_file, args.kg_cache_root)
    table = pa.concat_tables([pq.read_table(p, columns=["variantId", "chromosome", "position", "referenceAllele", "alternateAllele", "hgvsId", "rsIds", "transcriptConsequences"]) for p in args.variant_file], promote_options="default")
    if args.max_variants:
        table = table.slice(0, args.max_variants)
    candidate_ids = set(table.column("variantId").to_pylist())
    supported = load_supported_variants(args.kg_cache_root, candidate_ids)
    pos = pd.DataFrame([{"variant_id": r.get("variantId"), "chromosome": _variant_coord(r)[0], "position": _variant_coord(r)[1]} for r in table.to_pylist() if r.get("variantId") in supported])
    enhancer_slice = load_enhancer_slice(args.kg_cache_root / "nodes" / "enhancer.parquet", pos.dropna()) if supported else pd.DataFrame()
    edges, evidence, nodes, summary = build_edges_from_variants(table, supported, enhancer_slice, max_variants=None)
    summary["enhancer_slice_rows"] = len(enhancer_slice)
    write_outputs(args.stage_root, edges, evidence, nodes, summary)
    validation = validate_outputs(args.stage_root, args.kg_cache_root)
    print(json.dumps({"stage_root": str(args.stage_root), "summary": summary, "validation": validation}, indent=2, sort_keys=True))
    return 0 if validation["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
