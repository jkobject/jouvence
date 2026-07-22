"""FastAPI app for the fixture-backed Phase 1 viewer."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import fixture

MAX_SEARCH_LIMIT = 25
MAX_EDGE_LIMIT = 50
MAX_EVIDENCE_LIMIT = 100
MAX_FEATURE_LIMIT = 100
MAX_PUTATIVE_LIMIT = 25
LONG_RANGE_PER_TYPE_LIMIT = 5
VALID_NODE_TYPES = {node.node_type for node in fixture.NODES.values()}
DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"


class Meta(BaseModel):
    snapshot_id: str = fixture.SNAPSHOT_ID
    data_mode: str = fixture.DATA_MODE
    bundle_version: str = fixture.BUNDLE_VERSION
    truncated: bool = False
    next_cursor: str | None = None


class SearchItem(BaseModel):
    node_type: str
    node_id: str
    display_name: str
    description: str
    matched_alias: str
    alias_kind: str
    source: str
    rank: int


class SearchResponse(BaseModel):
    meta: Meta
    results: list[SearchItem]


class NodeResponse(BaseModel):
    meta: Meta
    node: dict[str, Any]


class RowsResponse(BaseModel):
    meta: Meta
    rows: list[dict[str, Any]]


class ExportRequest(BaseModel):
    node_type: str
    node_id: str
    trail: list[dict[str, str]] = Field(default_factory=list, max_length=50)
    format: Literal["markdown", "csv", "html"] = "markdown"


def _meta(*, truncated: bool = False, next_cursor: str | None = None) -> Meta:
    return Meta(truncated=truncated, next_cursor=next_cursor)


def _bounded_limit(limit: int, maximum: int) -> int:
    if not 1 <= int(limit) <= maximum:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {maximum}")
    return int(limit)


def _cursor_index(cursor: str | None) -> int:
    if cursor in (None, ""):
        return 0
    if not str(cursor).isdigit():
        raise HTTPException(status_code=422, detail="cursor must be a non-negative integer string")
    return int(cursor)


def _node_or_404(node_type: str, node_id: str) -> fixture.Node:
    if node_type.strip().lower() not in VALID_NODE_TYPES:
        raise HTTPException(status_code=404, detail="unknown node type")
    node = fixture.NODES.get(fixture.node_key(node_type, node_id))
    if node is None:
        raise HTTPException(status_code=404, detail="unknown node")
    return node


def _node_payload(node: fixture.Node) -> dict[str, Any]:
    return {
        "node_type": node.node_type,
        "node_id": node.node_id,
        "display_name": node.display_name,
        "description": node.description,
        "source": node.source,
        "aliases": list(node.aliases),
        "attributes": node.attributes,
        "external_links": [
            _external_link(alias["value"], alias["kind"])
            for alias in node.aliases
            if alias["kind"] == "external_id"
        ],
    }


def _external_link(value: str, kind: str) -> dict[str, str]:
    if value.startswith("HGNC:"):
        url = f"https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{value}"
    elif value.startswith("CHEMBL"):
        url = f"https://www.ebi.ac.uk/chembl/compound_report_card/{value}/"
    elif value.startswith("EFO:"):
        url = f"https://www.ebi.ac.uk/ols4/ontologies/efo/classes/{value.replace(':', '_')}"
    elif value.startswith("HP:"):
        url = f"https://hpo.jax.org/browse/term/{value}"
    else:
        url = f"https://www.ncbi.nlm.nih.gov/search/all/?term={value}"
    return {"label": value, "kind": kind, "url": url}


def _with_neighbor(edge: dict[str, Any], anchor_type: str, anchor_id: str) -> dict[str, Any]:
    if edge["x_type"] == anchor_type and edge["x_id"] == anchor_id:
        neighbor_type, neighbor_id, anchor_role = edge["y_type"], edge["y_id"], "x"
    else:
        neighbor_type, neighbor_id, anchor_role = edge["x_type"], edge["x_id"], "y"
    neighbor = fixture.NODES.get((neighbor_type, neighbor_id))
    return {
        **edge,
        "anchor_role": anchor_role,
        "neighbor_type": neighbor_type,
        "neighbor_id": neighbor_id,
        "neighbor_name": neighbor.display_name if neighbor else neighbor_id,
        "row_kind": edge.get("kind", "observed"),
    }


def _matches_anchor(row: dict[str, Any], node_type: str, node_id: str) -> bool:
    return (row.get("x_type") == node_type and row.get("x_id") == node_id) or (
        row.get("y_type") == node_type and row.get("y_id") == node_id
    )


def _page(rows: list[dict[str, Any]], limit: int, cursor: str | None) -> tuple[list[dict[str, Any]], Meta]:
    start = _cursor_index(cursor)
    stop = start + limit
    selected = rows[start:stop]
    next_cursor = str(stop) if stop < len(rows) else None
    return selected, _meta(truncated=next_cursor is not None, next_cursor=next_cursor)


def create_app(static_docs_root: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Jouvence-Graph fixture viewer API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://127.0.0.1:8000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    docs_root = static_docs_root or DOCS_ROOT
    if docs_root.exists():
        app.mount("/static", StaticFiles(directory=docs_root), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        viewer = docs_root / "viewer.html"
        if viewer.exists():
            html = viewer.read_text()
            return (
                html.replace('href="viewer.css"', 'href="/static/viewer.css"')
                .replace('src="viewer-data/fixture.js"', 'src="/static/viewer-data/fixture.js"')
                .replace('src="viewer.js"', 'src="/static/viewer.js"')
                .replace('href="site.css"', 'href="/static/site.css"')
            )
        return "<h1>Jouvence-Graph viewer</h1>"

    @app.get("/api/session")
    def session() -> dict[str, Any]:
        return {
            "meta": _meta(),
            "source": {"mode": fixture.DATA_MODE, "label": "Deterministic fixture", "localhost_only": True},
            "snapshot": {"snapshot_id": fixture.SNAPSHOT_ID, "bundle_version": fixture.BUNDLE_VERSION},
            "capabilities": ["search", "dossier", "features", "edges", "evidence", "long_range", "putative", "export"],
        }

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query(..., min_length=1, max_length=120),
        types: str | None = Query(default=None),
        limit: int = Query(default=10),
    ) -> SearchResponse:
        limit = _bounded_limit(limit, MAX_SEARCH_LIMIT)
        allowed = {item.strip().lower() for item in types.split(",")} if types else VALID_NODE_TYPES
        if not allowed.issubset(VALID_NODE_TYPES):
            raise HTTPException(status_code=422, detail="types contains an unsupported node type")
        needle = q.strip().lower()
        candidates: list[tuple[int, SearchItem]] = []
        for node in fixture.NODES.values():
            if node.node_type not in allowed:
                continue
            aliases = [
                {"kind": "canonical_id", "value": node.node_id, "source": node.source},
                {"kind": "display_name", "value": node.display_name, "source": node.source},
                *node.aliases,
            ]
            for alias in aliases:
                value = alias["value"]
                hay = value.lower()
                if hay == needle:
                    score = 0
                elif hay.startswith(needle):
                    score = 1
                elif needle in hay:
                    score = 2
                else:
                    continue
                candidates.append(
                    (
                        score,
                        SearchItem(
                            node_type=node.node_type,
                            node_id=node.node_id,
                            display_name=node.display_name,
                            description=node.description,
                            matched_alias=value,
                            alias_kind=alias["kind"],
                            source=alias["source"],
                            rank=score,
                        ),
                    )
                )
                break
        ordered = [item for _, item in sorted(candidates, key=lambda pair: (pair[0], pair[1].node_type, pair[1].display_name.lower()))]
        return SearchResponse(meta=_meta(truncated=len(ordered) > limit), results=ordered[:limit])

    @app.get("/api/nodes/{node_type}/{node_id}", response_model=NodeResponse)
    def node(node_type: str, node_id: str) -> NodeResponse:
        return NodeResponse(meta=_meta(), node=_node_payload(_node_or_404(node_type, node_id)))

    @app.get("/api/nodes/{node_type}/{node_id}/features", response_model=RowsResponse)
    def features(node_type: str, node_id: str, limit: int = Query(default=100)) -> RowsResponse:
        _node_or_404(node_type, node_id)
        limit = _bounded_limit(limit, MAX_FEATURE_LIMIT)
        rows = [row for row in fixture.FEATURE_ROWS if row["node_type"] == node_type and row["node_id"] == node_id]
        return RowsResponse(meta=_meta(truncated=len(rows) > limit), rows=rows[:limit])

    @app.get("/api/nodes/{node_type}/{node_id}/edges", response_model=RowsResponse)
    def edges(node_type: str, node_id: str, limit: int = Query(default=50), cursor: str | None = None) -> RowsResponse:
        node = _node_or_404(node_type, node_id)
        limit = _bounded_limit(limit, MAX_EDGE_LIMIT)
        rows = [_with_neighbor(row, node.node_type, node.node_id) for row in fixture.EDGE_ROWS if _matches_anchor(row, node.node_type, node.node_id)]
        selected, meta = _page(rows, limit, cursor)
        return RowsResponse(meta=meta, rows=selected)

    @app.get("/api/edges/{edge_key}/evidence", response_model=RowsResponse)
    def edge_evidence(edge_key: str, limit: int = Query(default=100), cursor: str | None = None) -> RowsResponse:
        limit = _bounded_limit(limit, MAX_EVIDENCE_LIMIT)
        rows = [row for row in fixture.EVIDENCE_ROWS if row["edge_key"] == edge_key]
        selected, meta = _page(rows, limit, cursor)
        return RowsResponse(meta=meta, rows=selected)

    @app.get("/api/nodes/{node_type}/{node_id}/evidence", response_model=RowsResponse)
    def node_evidence(node_type: str, node_id: str, limit: int = Query(default=100), cursor: str | None = None) -> RowsResponse:
        node = _node_or_404(node_type, node_id)
        limit = _bounded_limit(limit, MAX_EVIDENCE_LIMIT)
        rows = [row for row in fixture.EVIDENCE_ROWS if _matches_anchor(row, node.node_type, node.node_id)]
        selected, meta = _page(rows, limit, cursor)
        return RowsResponse(meta=meta, rows=selected)

    @app.get("/api/nodes/{node_type}/{node_id}/long-range", response_model=RowsResponse)
    def long_range(node_type: str, node_id: str, target_type: str | None = None) -> RowsResponse:
        node = _node_or_404(node_type, node_id)
        rows = [row for row in fixture.LONG_RANGE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id]
        if target_type:
            if target_type not in VALID_NODE_TYPES | {"phenotype"}:
                raise HTTPException(status_code=422, detail="unsupported target_type")
            rows = [row for row in rows if row["target_type"] == target_type]
        rows = sorted(rows, key=lambda row: (row["target_type"], row["rank"]))
        truncated = False
        capped: list[dict[str, Any]] = []
        for endpoint in sorted({row["target_type"] for row in rows}):
            endpoint_rows = [row for row in rows if row["target_type"] == endpoint]
            capped.extend(endpoint_rows[:LONG_RANGE_PER_TYPE_LIMIT])
            truncated = truncated or len(endpoint_rows) > LONG_RANGE_PER_TYPE_LIMIT
        return RowsResponse(meta=_meta(truncated=truncated), rows=capped)

    @app.get("/api/nodes/{node_type}/{node_id}/putative", response_model=RowsResponse)
    def putative(node_type: str, node_id: str, limit: int = Query(default=25)) -> RowsResponse:
        node = _node_or_404(node_type, node_id)
        limit = _bounded_limit(limit, MAX_PUTATIVE_LIMIT)
        rows = [row for row in fixture.PUTATIVE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id]
        return RowsResponse(meta=_meta(truncated=len(rows) > limit), rows=rows[:limit])

    @app.post("/api/export")
    def export(request: ExportRequest) -> Response:
        node = _node_or_404(request.node_type, request.node_id)
        dossier = _full_dossier(node)
        trail = [_trail_row(step) for step in request.trail]
        if request.format == "markdown":
            return Response(_markdown_export(dossier, trail), media_type="text/markdown")
        if request.format == "html":
            return Response(_html_export(dossier, trail), media_type="text/html")
        return Response(_csv_zip_export(dossier, trail), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=jouvence-viewer-export.zip"})

    return app


def _full_dossier(node: fixture.Node) -> dict[str, Any]:
    node_payload = _node_payload(node)
    edges = [_with_neighbor(row, node.node_type, node.node_id) for row in fixture.EDGE_ROWS if _matches_anchor(row, node.node_type, node.node_id)]
    return {
        "meta": _meta().model_dump(),
        "node": node_payload,
        "features": [row for row in fixture.FEATURE_ROWS if row["node_type"] == node.node_type and row["node_id"] == node.node_id],
        "edges": edges,
        "evidence": [row for row in fixture.EVIDENCE_ROWS if _matches_anchor(row, node.node_type, node.node_id)],
        "long_range": [row for row in fixture.LONG_RANGE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id],
        "putative_links": [row for row in fixture.PUTATIVE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id],
    }


def _trail_row(step: dict[str, str]) -> dict[str, str]:
    try:
        node = _node_or_404(step.get("node_type", ""), step.get("node_id", ""))
    except HTTPException:
        return {"node_type": step.get("node_type", "unknown"), "node_id": step.get("node_id", "unknown"), "display_name": step.get("display_name", "Unknown"), "via": step.get("via", "unknown")}
    return {"node_type": node.node_type, "node_id": node.node_id, "display_name": node.display_name, "via": step.get("via", "linked node")}


def _markdown_export(dossier: dict[str, Any], trail: list[dict[str, str]]) -> str:
    node = dossier["node"]
    lines = [
        "---",
        f"snapshot_id: {fixture.SNAPSHOT_ID}",
        f"data_mode: {fixture.DATA_MODE}",
        f"node_type: {node['node_type']}",
        f"node_id: {node['node_id']}",
        "ranker_versions: [fixture_path_ranker:v1]",
        "---",
        "",
        f"# {node['display_name']}",
        "",
        node["description"],
        "",
        "## Identity",
        f"- Canonical ID: `{node['node_id']}`",
        f"- Type: `{node['node_type']}`",
        f"- Source: {node['source']}",
        "",
        "## Features",
    ]
    lines.extend(f"- {row['feature_kind']} / {row['feature_key']}: {row['value']} ({row['epistemic_kind']}; {row['source']})" for row in dossier["features"])
    lines.append("\n## Direct observed edges")
    lines.extend(f"- observed `{row['relation']}` → {row['neighbor_name']} ({row['neighbor_type']}:{row['neighbor_id']}); score={row['score']}" for row in dossier["edges"])
    lines.append("\n## Evidence")
    lines.extend(f"- observed `{row['relation']}` {row['source']} / {row['predicate']} / {row['source_record_id']} / score={row['evidence_score']}" for row in dossier["evidence"])
    lines.append("\n## Long-range ranked connections")
    lines.extend(f"- ranked {row['target_type']}:{row['target_id']} {row['target_name']} score={row['score']} path={row['support_path']} caveat={row['caveats']}" for row in dossier["long_range"])
    lines.append("\n## Putative inferred links")
    lines.extend(f"- inferred {row['target_type']}:{row['target_id']} {row['target_name']} ({row['policy_class']}) template={row['template_id']} caveat={row['leakage_caveat']}" for row in dossier["putative_links"])
    lines.append("\n## Navigation trail")
    lines.extend(f"{index}. {row['display_name']} ({row['node_type']}:{row['node_id']}) — {row['via']}" for index, row in enumerate(trail, start=1))
    return "\n".join(lines) + "\n"


def _html_export(dossier: dict[str, Any], trail: list[dict[str, str]]) -> str:
    markdown = _markdown_export(dossier, trail)
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<!doctype html><title>Jouvence-Graph export</title><pre>{escaped}</pre>"


def _csv_zip_export(dossier: dict[str, Any], trail: list[dict[str, str]]) -> bytes:
    tables = {
        "node.csv": [dossier["node"]],
        "features.csv": dossier["features"],
        "edges.csv": dossier["edges"],
        "evidence.csv": dossier["evidence"],
        "long_range.csv": dossier["long_range"],
        "putative_links.csv": dossier["putative_links"],
        "history.csv": trail,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"snapshot_id": fixture.SNAPSHOT_ID, "data_mode": fixture.DATA_MODE, "row_kinds": ["observed", "ranked", "inferred"]}, indent=2))
        for name, rows in tables.items():
            archive.writestr(name, _csv_text(rows))
    return buffer.getvalue()


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "\n"
    fields = sorted({key for row in rows for key in row})
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


app = create_app()
