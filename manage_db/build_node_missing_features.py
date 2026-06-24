"""Stage missing node feature tables accepted by source audit.

Accepted scope for this builder:
- ``molecule_fingerprint`` from ``nodes/molecule.parquet.smiles`` using RDKit
  Morgan radius=2, nBits=2048, chirality-aware sparse sorted on-bit indices.
- Optional ``gene_genomic_interval`` coordinate precursor from a reviewed GTF/GFF
  plus explicit mapping/direct KG IDs. This emits coordinates only, not raw gene
  sequence, promoter sequence, or transcript-derived sequence.

The builder writes only under the provided staging root and optional staging GCS
mirror. It never writes canonical ``kg/v2/features`` and never creates
``edges/`` or ``evidence/`` objects.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import shutil
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from . import kg_gene_interval_features as gif
from . import kg_molecule_fingerprint_features as mff
from .kg_schema import NodeType
from .kg_storage import open_kg_root, read_nodes

_ENSEMBL_VERSION_RE = re.compile(r"^(ENS[A-Z]*G[0-9]+)(?:\.\d+)?$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_version(value: str) -> str:
    token = str(value or "").strip()
    match = _ENSEMBL_VERSION_RE.match(token)
    return match.group(1) if match else token.split(".", 1)[0] if token.startswith("ENS") else token


def _copy_local_tree_to_gcs(local_root: str | os.PathLike[str], gcs_root_uri: str) -> None:
    if not gcs_root_uri.startswith("gs://"):
        raise ValueError(f"remote_output_root_uri must be gs://..., got {gcs_root_uri}")
    import fsspec

    fs, remote_path = fsspec.core.url_to_fs(gcs_root_uri.rstrip("/"))
    base = Path(local_root)
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        target = f"{remote_path.rstrip('/')}/{rel}"
        parent = os.path.dirname(target)
        if parent:
            fs.makedirs(parent, exist_ok=True)
        with open(path, "rb") as src, fs.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)


def _read_node_table(kg_root_uri: str, node_type: str, columns: list[str] | None = None) -> pd.DataFrame:
    root = open_kg_root(kg_root_uri)
    if columns is None:
        return read_nodes(root, node_type)
    internal = root._node_internal(node_type)
    available = pq.ParquetFile(internal, filesystem=root.fs).schema_arrow.names
    selected = [col for col in columns if col in available]
    return read_nodes(root, node_type, columns=selected)


def _rdkit_version() -> str:
    import rdkit

    return str(rdkit.__version__)


def _mol_from_smiles(smiles: str):
    from rdkit import Chem

    return Chem.MolFromSmiles(smiles, sanitize=True)


def _canonical_smiles(mol: Any) -> str:
    from rdkit import Chem

    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)


def _component_count(mol: Any) -> int:
    from rdkit import Chem

    return len(Chem.GetMolFrags(mol, asMols=False, sanitizeFrags=False))


def _morgan_on_bits(
    mol: Any,
    *,
    radius: int,
    n_bits: int,
    use_chirality: bool,
    use_bond_types: bool,
) -> list[int]:
    from rdkit.Chem import rdFingerprintGenerator

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=radius,
        fpSize=n_bits,
        includeChirality=use_chirality,
        useBondTypes=use_bond_types,
    )
    return sorted(int(bit) for bit in generator.GetFingerprint(mol).GetOnBits())


def rows_from_molecule_nodes(
    molecule_nodes: pd.DataFrame,
    *,
    kg_root_uri: str,
    source_release: str,
    created_at: str,
    radius: int = 2,
    n_bits: int = 2048,
    use_chirality: bool = True,
    use_bond_types: bool = True,
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if "id" not in molecule_nodes.columns:
        raise ValueError("nodes/molecule.parquet must contain id")
    if "smiles" not in molecule_nodes.columns:
        raise ValueError("nodes/molecule.parquet must contain smiles for molecule_fingerprint")
    selected = molecule_nodes.copy()
    if max_rows is not None:
        selected = selected.head(max_rows)
    rdkit_version = _rdkit_version()
    rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, str]] = []
    missing_smiles = 0
    invalid_smiles = 0
    empty_fingerprints = 0
    multi_component = 0
    for _, node in selected.iterrows():
        node_id = str(node.get("id", "")).strip()
        smiles = str(node.get("smiles", "") or "").strip()
        inchikey = str(node.get("inchikey", "") or "").strip()
        if not smiles or smiles.lower() in {"nan", "none", "<na>"}:
            missing_smiles += 1
            continue
        mol = _mol_from_smiles(smiles)
        if mol is None:
            invalid_smiles += 1
            invalid_rows.append({"node_id": node_id, "input_smiles": smiles, "invalid_smiles_reason": "rdkit_parse_failed"})
            continue
        on_bits = _morgan_on_bits(
            mol,
            radius=radius,
            n_bits=n_bits,
            use_chirality=use_chirality,
            use_bond_types=use_bond_types,
        )
        if not on_bits:
            empty_fingerprints += 1
            invalid_rows.append({"node_id": node_id, "input_smiles": smiles, "invalid_smiles_reason": "empty_all_zero_fingerprint"})
            continue
        components = _component_count(mol)
        multi_component += int(components > 1)
        rows.append(
            {
                "feature_table": mff.MOLECULE_FINGERPRINT_TABLE,
                "node_id": node_id,
                "node_type": NodeType.MOLECULE.value,
                "fingerprint_kind": "morgan_binary",
                "fingerprint_format": "sparse_on_bits_uint16_list",
                "on_bits": on_bits,
                "n_bits": n_bits,
                "radius": radius,
                "use_chirality": use_chirality,
                "use_bond_types": use_bond_types,
                "input_smiles": smiles,
                "canonical_smiles_rdkit": _canonical_smiles(mol),
                "input_smiles_field": "nodes/molecule.parquet.smiles",
                "inchikey": inchikey,
                "source": "ChEMBL/OpenTargets",
                "source_dataset": "KG molecule node metadata derived from OpenTargets/ChEMBL structure fields",
                "source_record_id": node_id,
                "source_release": source_release,
                "rdkit_version": rdkit_version,
                "invalid_smiles_policy": "skip_with_report",
                "salt_mixture_policy": "fingerprint_input_as_is_record_component_count",
                "component_count": components,
                "provenance": f"{kg_root_uri.rstrip('/')}/nodes/molecule.parquet::smiles",
                "license": "ChEMBL CC BY-SA 3.0 / OpenTargets CC BY 4.0 with upstream attribution",
                "citation": "ChEMBL and Open Targets drug molecule metadata.",
                "created_at": created_at,
            }
        )
    stats = {
        "source_records_seen": int(len(selected)),
        "missing_smiles": int(missing_smiles),
        "invalid_smiles": int(invalid_smiles),
        "empty_fingerprints_skipped": int(empty_fingerprints),
        "multi_component_rows": int(multi_component),
        "rdkit_version": rdkit_version,
        "fingerprint_parameters": {
            "fingerprint_kind": "morgan_binary",
            "radius": radius,
            "n_bits": n_bits,
            "use_chirality": use_chirality,
            "use_bond_types": use_bond_types,
            "fingerprint_format": "sparse_on_bits_uint16_list",
        },
    }
    return pd.DataFrame(rows), pd.DataFrame(invalid_rows), stats


def _parse_gtf_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for item in raw.rstrip(";").split(";"):
        item = item.strip()
        if not item:
            continue
        if " " in item:
            key, value = item.split(" ", 1)
            attrs[key] = value.strip().strip('"')
        elif "=" in item:
            key, value = item.split("=", 1)
            attrs[key] = value.strip().strip('"')
    return attrs


def _iter_gene_gtf(path: str | os.PathLike[str]) -> Iterator[dict[str, Any]]:
    gtf_path = Path(path)
    opener = gzip.open if gtf_path.suffix == ".gz" else open
    with opener(gtf_path, "rt", encoding="utf-8", errors="replace") as handle:  # type: ignore[arg-type]
        reader = csv.reader((line for line in handle if line.strip() and not line.startswith("#")), delimiter="\t")
        for fields in reader:
            if len(fields) < 9 or fields[2] != "gene":
                continue
            attrs = _parse_gtf_attributes(fields[8])
            source_gene_id = attrs.get("gene_id") or attrs.get("ID") or attrs.get("gene") or ""
            if source_gene_id.startswith("gene:"):
                source_gene_id = source_gene_id.split(":", 1)[1]
            yield {
                "chromosome": fields[0],
                "start_1based": int(fields[3]),
                "end_1based": int(fields[4]),
                "strand": fields[6] if fields[6] in {"+", "-"} else ".",
                "source_record_id": _strip_version(source_gene_id),
                "raw_source_record_id": source_gene_id,
            }


def _load_gene_id_map(path: str | os.PathLike[str] | None) -> dict[str, str]:
    if path is None:
        return {}
    mapping = pd.read_csv(path)
    required = {"source_gene_id", "node_id"}
    if not required <= set(mapping.columns):
        raise ValueError(f"gene id map must contain columns {sorted(required)}")
    result: dict[str, str] = {}
    for _, row in mapping.iterrows():
        source_gene_id = _strip_version(str(row["source_gene_id"]))
        node_id = str(row["node_id"]).strip()
        if source_gene_id and node_id:
            result[source_gene_id] = node_id
    return result


def rows_from_gene_gtf(
    *,
    gtf_path: str | os.PathLike[str],
    gene_nodes: pd.DataFrame,
    gene_id_map_csv: str | os.PathLike[str] | None,
    reference_build: str,
    source: str,
    source_dataset: str,
    source_release: str,
    created_at: str,
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    endpoint_ids = set(gene_nodes["id"].astype(str))
    explicit_map = _load_gene_id_map(gene_id_map_csv)
    direct_ids = {_strip_version(node_id): str(node_id) for node_id in endpoint_ids}
    rows: list[dict[str, Any]] = []
    seen = 0
    unmapped = 0
    for record in _iter_gene_gtf(gtf_path):
        seen += 1
        source_record_id = record["source_record_id"]
        node_id = explicit_map.get(source_record_id) or direct_ids.get(source_record_id)
        if node_id is None:
            unmapped += 1
            continue
        rows.append(
            {
                "feature_table": gif.GENE_INTERVAL_TABLE,
                "node_id": node_id,
                "node_type": NodeType.GENE.value,
                "sequence_kind": "genomic_locus_coordinates_only",
                "chromosome": record["chromosome"],
                "start_1based": record["start_1based"],
                "end_1based": record["end_1based"],
                "strand": record["strand"],
                "reference_build": reference_build,
                "source": source,
                "source_dataset": source_dataset,
                "source_record_id": source_record_id,
                "source_release": source_release,
                "provenance": f"{gtf_path}::gene feature raw_id={record['raw_source_record_id']}",
                "license": "EMBL-EBI open data / attribution",
                "citation": f"{source} gene annotation {source_release}",
                "created_at": created_at,
            }
        )
        if max_rows is not None and len(rows) >= max_rows:
            break
    stats = {
        "source_records_seen": seen,
        "source_records_unmapped": unmapped,
        "gene_id_map_csv": str(gene_id_map_csv) if gene_id_map_csv else None,
        "reference_build": reference_build,
    }
    return pd.DataFrame(rows), stats


def stage_node_missing_features(
    *,
    kg_root_uri: str,
    output_root_uri: str,
    source_release: str,
    created_at: str | None = None,
    remote_output_root_uri: str | None = None,
    build_molecule_fingerprint: bool = True,
    gene_gtf: str | None = None,
    gene_id_map_csv: str | None = None,
    gene_reference_build: str = "GRCh38",
    gene_source: str = "Ensembl",
    gene_source_dataset: str | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    created_at = created_at or _utc_now()
    output_root = open_kg_root(output_root_uri)
    report: dict[str, Any] = {
        "staging_only": True,
        "canonical_promotion": False,
        "edges_written": False,
        "evidence_written": False,
        "raw_gene_sequence_written": False,
        "created_at": created_at,
        "kg_root_uri": kg_root_uri,
        "output_root_uri": output_root_uri,
        "tables": {},
    }
    reports_dir = Path(output_root_uri) / "reports" if "://" not in output_root_uri else None
    if reports_dir is not None:
        reports_dir.mkdir(parents=True, exist_ok=True)

    if build_molecule_fingerprint:
        molecule_nodes = _read_node_table(kg_root_uri, "molecule", ["id", "smiles", "inchikey"])
        endpoint = set(molecule_nodes["id"].astype(str))
        rows, invalid_rows, stats = rows_from_molecule_nodes(
            molecule_nodes,
            kg_root_uri=kg_root_uri,
            source_release=source_release,
            created_at=created_at,
            max_rows=max_rows,
        )
        if len(rows):
            validation = mff.write_molecule_fingerprints(output_root, rows, endpoint_node_ids=endpoint)
            report["tables"][mff.MOLECULE_FINGERPRINT_TABLE] = {
                **validation.to_dict(),
                **stats,
                "path": mff.molecule_fingerprint_path(output_root),
            }
        else:
            report["tables"][mff.MOLECULE_FINGERPRINT_TABLE] = {**stats, "rows": 0, "reason": "No valid SMILES rows emitted"}
        if reports_dir is not None:
            invalid_rows.to_csv(reports_dir / "molecule_fingerprint_invalid_smiles.csv", index=False)
            mff.source_policy_audit().to_csv(reports_dir / "molecule_fingerprint_source_policy.csv", index=False)

    if gene_gtf is not None:
        gene_nodes = _read_node_table(kg_root_uri, "gene")
        endpoint = set(gene_nodes["id"].astype(str))
        rows, stats = rows_from_gene_gtf(
            gtf_path=gene_gtf,
            gene_nodes=gene_nodes,
            gene_id_map_csv=gene_id_map_csv,
            reference_build=gene_reference_build,
            source=gene_source,
            source_dataset=gene_source_dataset or f"{gene_source} gene annotation GTF/GFF",
            source_release=source_release,
            created_at=created_at,
            max_rows=max_rows,
        )
        if len(rows):
            validation = gif.write_gene_intervals(output_root, rows, endpoint_node_ids=endpoint)
            report["tables"][gif.GENE_INTERVAL_TABLE] = {
                **validation.to_dict(),
                **stats,
                "path": gif.gene_interval_path(output_root),
            }
        else:
            report["tables"][gif.GENE_INTERVAL_TABLE] = {**stats, "rows": 0, "reason": "No mapped gene coordinate rows emitted"}
        if reports_dir is not None:
            gif.source_policy_audit().to_csv(reports_dir / "gene_interval_source_policy.csv", index=False)
    else:
        report["tables"][gif.GENE_INTERVAL_TABLE] = {
            "rows": 0,
            "reason": "No reviewed GTF/GFF coordinate source supplied; raw gene_sequence remains deferred.",
            "deferred": True,
        }

    if reports_dir is not None:
        (reports_dir / "node_missing_features_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    if remote_output_root_uri is not None:
        _copy_local_tree_to_gcs(output_root_uri, remote_output_root_uri)
        report["remote_output_root_uri"] = {"path": remote_output_root_uri}
    return report


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-root", required=True, help="Read-only KG root containing nodes/*.parquet")
    parser.add_argument("--output-root", required=True, help="Staging root to write features/*.parquet and reports/*")
    parser.add_argument("--source-release", required=True, help="KG/source release label for node structure fields")
    parser.add_argument("--created-at", help="ISO ingestion timestamp; defaults to now UTC")
    parser.add_argument("--remote-output-root", help="Optional gs:// staging root to mirror local output")
    parser.add_argument("--skip-molecule-fingerprint", action="store_true")
    parser.add_argument("--gene-gtf", help="Optional reviewed Ensembl/GENCODE GTF/GFF source for gene_genomic_interval")
    parser.add_argument("--gene-id-map-csv", help="Optional CSV with source_gene_id,node_id columns for GTF-to-KG mapping")
    parser.add_argument("--gene-reference-build", default="GRCh38")
    parser.add_argument("--gene-source", default="Ensembl")
    parser.add_argument("--gene-source-dataset")
    parser.add_argument("--max-rows", type=int, help="Debug/test row cap applied before validation")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = stage_node_missing_features(
        kg_root_uri=args.kg_root,
        output_root_uri=args.output_root,
        source_release=args.source_release,
        created_at=args.created_at,
        remote_output_root_uri=args.remote_output_root,
        build_molecule_fingerprint=not args.skip_molecule_fingerprint,
        gene_gtf=args.gene_gtf,
        gene_id_map_csv=args.gene_id_map_csv,
        gene_reference_build=args.gene_reference_build,
        gene_source=args.gene_source,
        gene_source_dataset=args.gene_source_dataset,
        max_rows=args.max_rows,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
