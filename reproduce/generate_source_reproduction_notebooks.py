"""Generate concise, offline source-reproduction notebooks from the inventory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nbformat

ROOT = Path(__file__).resolve().parents[1]
REPRODUCE = ROOT / "reproduce"
INVENTORY_PATH = REPRODUCE / "source_family_inventory.json"


@dataclass(frozen=True)
class NotebookGroup:
    title: str
    purpose: str
    source_ids: tuple[str, ...]
    demonstration: str


INDEX_DEMO = '''import json
import tempfile
from pathlib import Path

status_counts = __STATUS_COUNTS__
assert sum(status_counts.values()) == __SOURCE_COUNT__
assert status_counts["canonical"] == __CANONICAL_COUNT__
with tempfile.TemporaryDirectory() as tmp:
    summary_path = Path(tmp) / "source_inventory_summary.json"
    summary_path.write_text(json.dumps(status_counts, sort_keys=True))
    round_trip = json.loads(summary_path.read_text())
assert round_trip == status_counts
round_trip
'''

PROTEIN_DEMO = '''import json
import tempfile
from pathlib import Path

from manage_db.build_intact_protein_interactions import map_endpoint, parse_endpoint

raw_endpoints = ["uniprotkb:P00533", "ensembl:ENSP00000275493", "uniprotkb:NOT_IN_MAP"]
protein_map = {"P00533": "ENSP00000275493", "ENSP00000275493": "ENSP00000275493"}
parsed = [parse_endpoint(value) for value in raw_endpoints]
mapped = [map_endpoint(endpoint, protein_map) for endpoint in parsed]
assert mapped == ["ENSP00000275493", "ENSP00000275493", ""]
with tempfile.TemporaryDirectory() as tmp:
    result_path = Path(tmp) / "intact_mapping_demo.json"
    result_path.write_text(json.dumps({"accepted": mapped[:2], "rejected": raw_endpoints[2:]}))
    result = json.loads(result_path.read_text())
assert len(result["accepted"]) == 2 and len(result["rejected"]) == 1
result
'''

CELL_DEMO = '''import json
import tempfile
from pathlib import Path

from manage_db.build_staged_cell_line_assays import _parse_crispr_gene_column
from manage_db.build_textual_summary_features import parse_cellosaurus_obo

assert _parse_crispr_gene_column("TP53 (7157)") == ("TP53", "7157")
assert _parse_crispr_gene_column("malformed") is None
fixture = """format-version: 1.2
data-version: 56
! Licensing information: CC BY 4.0

[Term]
id: CVCL_0023
name: A-549
xref: DepMap:ACH-000681
comment: Human lung carcinoma cell line.
"""
with tempfile.TemporaryDirectory() as tmp:
    fixture_path = Path(tmp) / "cellosaurus.obo"
    fixture_path.write_text(fixture)
    records, header = parse_cellosaurus_obo(fixture_path)
    result_path = Path(tmp) / "cellosaurus_demo.json"
    result_path.write_text(json.dumps({"records": records, "header": header}))
    result = json.loads(result_path.read_text())
assert result["records"][0]["depmap_xrefs"] == ["ACH-000681"]
assert result["header"]["data-version"] == "56"
result
'''

FEATURE_DEMO = '''import json
import tempfile
from pathlib import Path

from manage_db.kg_molecule_fingerprint_features import fingerprint_sha256, molecule_fingerprint_schema

schema = molecule_fingerprint_schema()
required = {"node_id", "node_type", "on_bits", "radius", "n_bits", "fingerprint_sha256"}
assert required <= set(schema.names)
digest = fingerprint_sha256(
    [1, 7, 42],
    fingerprint_kind="morgan_binary",
    radius=2,
    n_bits=2048,
    use_chirality=True,
    use_bond_types=True,
)
assert len(digest) == 64
with tempfile.TemporaryDirectory() as tmp:
    result_path = Path(tmp) / "fingerprint_schema_demo.json"
    result_path.write_text(json.dumps({"columns": schema.names, "sha256": digest}))
    result = json.loads(result_path.read_text())
assert result["sha256"] == digest
{"column_count": len(result["columns"]), "sha256": digest}
'''

GROUPS: dict[str, NotebookGroup] = {
    "26_source_reproduction_index.ipynb": NotebookGroup(
        title="Jouvence source reproduction index",
        purpose="Canonical denominator, historical acquisition, and honest replay gaps for the base KG sources.",
        source_ids=("opentargets_26_03", "txgnn_legacy_sources", "encode_re2g", "gtex", "cellxgene"),
        demonstration=INDEX_DEMO,
    ),
    "27_source_native_protein_context_reproduction.ipynb": NotebookGroup(
        title="Source-native interactions and protein context",
        purpose="BioGRID, IntAct, HPA, UniProt, Reactome, ChEMBL, and the deferred miRNA lane.",
        source_ids=("biogrid_5_0_258", "intact_current", "hpa_25_1", "uniprotkb", "reactome_go", "chembl_protein_targets", "mirna_sources"),
        demonstration=PROTEIN_DEMO,
    ),
    "28_cell_line_pharmacology_clinical_reproduction.ipynb": NotebookGroup(
        title="Cell-line, pharmacology, and clinical context",
        purpose="DepMap, Project Score, GDSC, PRISM, Cellosaurus, and ClinicalTrials.gov.",
        source_ids=("depmap_ccle", "project_score", "gdsc", "prism_20q2", "cellosaurus", "clinicaltrials_gov"),
        demonstration=CELL_DEMO,
    ),
    "29_official_features_exports_reproduction.ipynb": NotebookGroup(
        title="Official node features and exports",
        purpose="Ensembl, HPO, RDKit, official textual-feature ontology sources, embeddings, PyG export, and the partial LaminDB status surface.",
        source_ids=("ensembl", "hpo_ontology", "rdkit_fingerprints", "cell_ontology", "uberon", "real_embeddings", "pyg_export", "lamindb_manifest"),
        demonstration=FEATURE_DEMO,
    ),
}


def _cell_id(index: int, source: str) -> str:
    return hashlib.sha256(f"{index}:{source}".encode()).hexdigest()[:12]


def _manual_command(command: str) -> str:
    return f"```text\n{command}\n```"


def _render_row(row: dict[str, Any]) -> str:
    outputs = "\n".join(f"  - `{value}`" for value in row["outputs"])
    fixture = "available" if row["bounded_fixture_available"] else "not available"
    return f'''<a id="{row["anchor"]}"></a>
## {row["source_dataset"]}

- **status:** `{row["status"]}` — {row["artifact_scope"]}
- **release/snapshot:** {row["release"]}
- **source and access:** {row["source_url"]} — {row["access_method"]}
- **licence/citation:** {row["license"]}
- **raw cache template:** `{row["cache_template"]}`
- **preprocessing entrypoint:** `{row["preprocessing_entrypoint"]}`
- **mapping:** {row["mapping_rules"]}
- **rejects/conflicts/evidence:** {row["rejection_rules"]}
- **validation evidence:** {row["validation_evidence"]}
- **bounded fixture:** {fixture}. {row["gap"]}

**Produced artifacts**
{outputs}

**Manual production/acquisition command (documentation only; never executed here)**

{_manual_command(row["historical_acquisition"])}
'''


def build_notebook(group: NotebookGroup, inventory: dict[str, Any]) -> nbformat.NotebookNode:
    by_id = {row["id"]: row for row in inventory["sources"]}
    rows = [by_id[source_id] for source_id in group.source_ids]
    statuses: dict[str, int] = {}
    for row in inventory["sources"]:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    demo = (
        group.demonstration.replace("__STATUS_COUNTS__", repr(dict(sorted(statuses.items()))))
        .replace("__SOURCE_COUNT__", str(len(inventory["sources"])))
        .replace("__CANONICAL_COUNT__", str(len(inventory["canonical_source_ids"])))
    )
    intro = f'''# {group.title}

{group.purpose}

This is explanatory reproduction plus a bounded local illustration—not a production runner. Production commands below are inert text. Code cells use only synthetic input, temporary directories, and pure tracked parsing/schema functions. They perform no shell, subprocess, network, cloud, GCS, LaminDB, canonical-path, or production-builder execution.

Status describes the accepted artifact, independently of replay completeness: `canonical`, `official`, `staged`, `deferred`, or `not_reproducible_yet`.
'''
    cells = [nbformat.v4.new_markdown_cell(intro)]
    if group.title.endswith("index"):
        canonical = ", ".join(f"`{value}`" for value in inventory["canonical_source_ids"])
        evidence = "\n".join(f"- `{path}`" for path in inventory["denominator_evidence"])
        cells.append(
            nbformat.v4.new_markdown_cell(
                f"## Reconciled denominator\n\nCanonical source families ({len(inventory['canonical_source_ids'])}): {canonical}.\n\nEvidence used to derive the denominator:\n{evidence}\n"
            )
        )
    for row in rows:
        cells.append(nbformat.v4.new_markdown_cell(_render_row(row)))
    cells.append(nbformat.v4.new_markdown_cell("## Bounded executable illustration\n\nThe following cell exercises real repository behavior on synthetic input and writes only inside a temporary directory."))
    cells.append(nbformat.v4.new_code_cell(demo))
    notebook = nbformat.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
    )
    for index, cell in enumerate(notebook.cells):
        cell.id = _cell_id(index, cell.source)
    return notebook


def main() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())
    assigned = {source_id for group in GROUPS.values() for source_id in group.source_ids}
    known = {row["id"] for row in inventory["sources"]}
    if assigned != known:
        raise SystemExit(f"inventory/group mismatch: missing={sorted(known - assigned)}, extra={sorted(assigned - known)}")
    for name, group in GROUPS.items():
        nbformat.write(build_notebook(group, inventory), REPRODUCE / name)


if __name__ == "__main__":
    main()
