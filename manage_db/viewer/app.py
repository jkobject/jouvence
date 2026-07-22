"""Read-only localhost API for fixture or immutable viewer-bundle data."""

from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import fixture
from .bundle import FIXTURE_DATA

MAX_SEARCH_LIMIT = 25
MAX_EDGE_LIMIT = 50
DEFAULT_EVIDENCE_LIMIT = 10
MAX_EVIDENCE_LIMIT = 50
MAX_FEATURE_LIMIT = 100
MAX_PUTATIVE_LIMIT = 25
LONG_RANGE_PER_TYPE_LIMIT = 5
MAX_LONG_RANGE_ROWS = 20
MAX_EXPORT_REQUEST_BYTES = 64 * 1024
MAX_EXPORT_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_API_RESPONSE_BYTES = 16 * 1024 * 1024
DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"


class Meta(BaseModel):
    snapshot_id: str
    data_mode: str
    bundle_version: str
    truncated: bool = False
    next_cursor: str | None = None


class EvidenceMeta(Meta):
    total: int
    returned: int


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


class EvidenceRowsResponse(BaseModel):
    meta: EvidenceMeta
    rows: list[dict[str, Any]]


class TrailStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: str = Field(min_length=1, max_length=32)
    node_id: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=512)
    via: str = Field(min_length=1, max_length=512)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: str = Field(min_length=1, max_length=32)
    node_id: str = Field(min_length=1, max_length=256)
    trail: list[TrailStep] = Field(default_factory=list, max_length=50)
    format: Literal["markdown", "csv", "html"] = "markdown"


def _meta(data: Any, *, truncated: bool = False, next_cursor: str | None = None) -> Meta:
    return Meta(
        snapshot_id=data.snapshot_id,
        data_mode=data.mode,
        bundle_version=data.bundle_version,
        truncated=truncated,
        next_cursor=next_cursor,
    )


def _evidence_meta(
    data: Any,
    *,
    total: int,
    returned: int,
    truncated: bool = False,
    next_cursor: str | None = None,
) -> EvidenceMeta:
    return EvidenceMeta(
        snapshot_id=data.snapshot_id,
        data_mode=data.mode,
        bundle_version=data.bundle_version,
        truncated=truncated,
        next_cursor=next_cursor,
        total=total,
        returned=returned,
    )


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


def _node_or_404(data: Any, valid_node_types: set[str], node_type: str, node_id: str) -> fixture.Node:
    if node_type.strip().lower() not in valid_node_types:
        raise HTTPException(status_code=404, detail="unknown node type")
    node = data.NODES.get(data.node_key(node_type, node_id))
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


def _with_neighbor(data: Any, edge: dict[str, Any], anchor_type: str, anchor_id: str) -> dict[str, Any]:
    if edge["x_type"] == anchor_type and edge["x_id"] == anchor_id:
        neighbor_type, neighbor_id, anchor_role = edge["y_type"], edge["y_id"], "x"
    else:
        neighbor_type, neighbor_id, anchor_role = edge["x_type"], edge["x_id"], "y"
    neighbor = data.NODES.get((neighbor_type, neighbor_id))
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


def _evidence_sort_key(row: dict[str, Any]) -> str:
    """Return the immutable, content-derived order used by evidence cursors."""

    return json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _page(data: Any, rows: list[dict[str, Any]], limit: int, cursor: str | None) -> tuple[list[dict[str, Any]], Meta]:
    start = _cursor_index(cursor)
    stop = start + limit
    selected = rows[start:stop]
    next_cursor = str(stop) if stop < len(rows) else None
    return selected, _meta(data, truncated=next_cursor is not None, next_cursor=next_cursor)


def _evidence_page(
    data: Any,
    rows: list[dict[str, Any]],
    limit: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], EvidenceMeta]:
    start = _cursor_index(cursor)
    stop = start + limit
    selected = rows[start:stop]
    next_cursor = str(stop) if stop < len(rows) else None
    return selected, _evidence_meta(
        data,
        truncated=next_cursor is not None,
        next_cursor=next_cursor,
        total=len(rows),
        returned=len(selected),
    )


def _capped_long_range(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    truncated = False
    capped: list[dict[str, Any]] = []
    for endpoint in sorted({row["target_type"] for row in rows}):
        endpoint_rows = [row for row in rows if row["target_type"] == endpoint]
        remaining = MAX_LONG_RANGE_ROWS - len(capped)
        if remaining <= 0:
            truncated = True
            break
        capped.extend(endpoint_rows[: min(LONG_RANGE_PER_TYPE_LIMIT, remaining)])
        truncated = truncated or len(endpoint_rows) > LONG_RANGE_PER_TYPE_LIMIT
    truncated = truncated or len(capped) < len(rows)
    return capped, truncated


def create_app(
    static_docs_root: Path | None = None,
    *,
    data_source: Any | None = None,
    session_token: str | None = None,
) -> FastAPI:
    if not isinstance(session_token, str) or not 8 <= len(session_token) <= 256:
        raise ValueError("a non-empty local session token is required")
    data = data_source or FIXTURE_DATA
    evidence_rows = sorted(data.EVIDENCE_ROWS, key=_evidence_sort_key)
    valid_node_types = {node.node_type for node in data.NODES.values()}
    app = FastAPI(
        title="Jouvence-Graph local viewer API",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"],
    )

    @app.middleware("http")
    async def local_request_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme != "http" or parsed_origin.hostname not in {"127.0.0.1", "localhost"}:
                return JSONResponse(status_code=403, content={"detail": "non-local origin rejected"})
        if request.url.path.startswith("/api"):
            if request.headers.get("x-jouvence-session") != session_token:
                return JSONResponse(status_code=401, content={"detail": "invalid local session"})
        if request.method == "POST" and request.url.path == "/api/export":
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "invalid content length"})
                if declared_length < 0 or declared_length > MAX_EXPORT_REQUEST_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "export request too large"})
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_EXPORT_REQUEST_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "export request too large"})
                body.extend(chunk)
            request._body = bytes(body)
        response = await call_next(request)
        if not request.url.path.startswith("/api"):
            return response
        body = bytearray()
        async for chunk in response.body_iterator:
            if len(body) + len(chunk) > MAX_API_RESPONSE_BYTES:
                return JSONResponse(status_code=413, content={"detail": "API response too large"})
            body.extend(chunk)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=bytes(body),
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    @app.exception_handler(Exception)
    async def sanitized_error(_request: Request, _error: Exception):
        return JSONResponse(status_code=500, content={"detail": "internal viewer error"})

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
                .replace('href="index.html"', 'href="/static/index.html"')
                .replace('href="viewer-install.html"', 'href="/static/viewer-install.html"')
                .replace('href="viewer-proposal.md"', 'href="/static/viewer-proposal.md"')
            )
        return "<h1>Jouvence-Graph viewer</h1>"

    @app.get("/api/session")
    def session() -> dict[str, Any]:
        return {
            "meta": _meta(data),
            "source": {
                "mode": data.mode,
                "label": data.label,
                "localhost_only": True,
                "credential_transport": "host-only",
                "requester_pays_warning": data.requester_pays_warning,
            },
            "snapshot": {"snapshot_id": data.snapshot_id, "bundle_version": data.bundle_version},
            "cache": {"status": data.cache_status, "bounded": True},
            "capabilities": ["search", "dossier", "features", "edges", "evidence", "long_range", "putative", "export"],
        }

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query(..., min_length=1, max_length=120),
        types: str | None = Query(default=None),
        limit: int = Query(default=10),
    ) -> SearchResponse:
        limit = _bounded_limit(limit, MAX_SEARCH_LIMIT)
        allowed = {item.strip().lower() for item in types.split(",")} if types else valid_node_types
        if not allowed.issubset(valid_node_types):
            raise HTTPException(status_code=422, detail="types contains an unsupported node type")
        needle = q.strip().lower()
        candidates: list[tuple[int, SearchItem]] = []
        for node in data.NODES.values():
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
        return SearchResponse(meta=_meta(data, truncated=len(ordered) > limit), results=ordered[:limit])

    @app.get("/api/nodes/{node_type}/{node_id}", response_model=NodeResponse)
    def node(node_type: str, node_id: str) -> NodeResponse:
        selected = _node_or_404(data, valid_node_types, node_type, node_id)
        return NodeResponse(meta=_meta(data), node=_node_payload(selected))

    @app.get("/api/nodes/{node_type}/{node_id}/features", response_model=RowsResponse)
    def features(node_type: str, node_id: str, limit: int = Query(default=100)) -> RowsResponse:
        _node_or_404(data, valid_node_types, node_type, node_id)
        limit = _bounded_limit(limit, MAX_FEATURE_LIMIT)
        rows = [row for row in data.FEATURE_ROWS if row["node_type"] == node_type and row["node_id"] == node_id]
        return RowsResponse(meta=_meta(data, truncated=len(rows) > limit), rows=rows[:limit])

    @app.get("/api/nodes/{node_type}/{node_id}/edges", response_model=RowsResponse)
    def edges(node_type: str, node_id: str, limit: int = Query(default=50), cursor: str | None = None) -> RowsResponse:
        node = _node_or_404(data, valid_node_types, node_type, node_id)
        limit = _bounded_limit(limit, MAX_EDGE_LIMIT)
        rows = [_with_neighbor(data, row, node.node_type, node.node_id) for row in data.EDGE_ROWS if _matches_anchor(row, node.node_type, node.node_id)]
        selected, meta = _page(data, rows, limit, cursor)
        return RowsResponse(meta=meta, rows=selected)

    @app.get("/api/edges/{edge_key}/evidence", response_model=EvidenceRowsResponse)
    def edge_evidence(
        edge_key: str,
        limit: int = Query(default=DEFAULT_EVIDENCE_LIMIT),
        cursor: str | None = None,
    ) -> EvidenceRowsResponse:
        limit = _bounded_limit(limit, MAX_EVIDENCE_LIMIT)
        rows = [row for row in evidence_rows if row["edge_key"] == edge_key]
        selected, meta = _evidence_page(data, rows, limit, cursor)
        return EvidenceRowsResponse(meta=meta, rows=selected)

    @app.get("/api/nodes/{node_type}/{node_id}/evidence", response_model=EvidenceRowsResponse)
    def node_evidence(
        node_type: str,
        node_id: str,
        limit: int = Query(default=DEFAULT_EVIDENCE_LIMIT),
        cursor: str | None = None,
    ) -> EvidenceRowsResponse:
        node = _node_or_404(data, valid_node_types, node_type, node_id)
        limit = _bounded_limit(limit, MAX_EVIDENCE_LIMIT)
        rows = [row for row in evidence_rows if _matches_anchor(row, node.node_type, node.node_id)]
        selected, meta = _evidence_page(data, rows, limit, cursor)
        return EvidenceRowsResponse(meta=meta, rows=selected)

    @app.get("/api/nodes/{node_type}/{node_id}/long-range", response_model=RowsResponse)
    def long_range(node_type: str, node_id: str, target_type: str | None = None) -> RowsResponse:
        node = _node_or_404(data, valid_node_types, node_type, node_id)
        rows = [row for row in data.LONG_RANGE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id]
        if target_type:
            if target_type not in valid_node_types | {"phenotype"}:
                raise HTTPException(status_code=422, detail="unsupported target_type")
            rows = [row for row in rows if row["target_type"] == target_type]
        rows = sorted(rows, key=lambda row: (row["target_type"], row["rank"]))
        capped, truncated = _capped_long_range(rows)
        return RowsResponse(meta=_meta(data, truncated=truncated), rows=capped)

    @app.get("/api/nodes/{node_type}/{node_id}/putative", response_model=RowsResponse)
    def putative(node_type: str, node_id: str, limit: int = Query(default=25)) -> RowsResponse:
        node = _node_or_404(data, valid_node_types, node_type, node_id)
        limit = _bounded_limit(limit, MAX_PUTATIVE_LIMIT)
        rows = [row for row in data.PUTATIVE_ROWS if row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id]
        return RowsResponse(meta=_meta(data, truncated=len(rows) > limit), rows=rows[:limit])

    @app.post("/api/export")
    def export(request: ExportRequest) -> Response:
        node = _node_or_404(data, valid_node_types, request.node_type, request.node_id)
        dossier = _full_dossier(data, node, evidence_rows=evidence_rows)
        trail = [_trail_row(data, valid_node_types, step) for step in request.trail]
        if request.format == "markdown":
            return Response(
                _bounded_export_payload(_markdown_export(data, dossier, trail)),
                media_type="text/markdown",
            )
        if request.format == "html":
            return Response(
                _bounded_export_payload(_html_export(data, dossier, trail)),
                media_type="text/html",
            )
        return Response(
            _bounded_export_payload(_csv_zip_export(data, dossier, trail)),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=jouvence-viewer-export.zip"},
        )

    return app


def _bounded_matches(
    rows: list[dict[str, Any]],
    predicate: Any,
    maximum: int,
) -> tuple[list[dict[str, Any]], bool]:
    selected: list[dict[str, Any]] = []
    truncated = False
    for row in rows:
        if not predicate(row):
            continue
        if len(selected) < maximum:
            selected.append(row)
        else:
            truncated = True
    return selected, truncated


def _bounded_long_range_matches(
    rows: list[dict[str, Any]],
    node: fixture.Node,
) -> tuple[list[dict[str, Any]], bool]:
    by_target: dict[str, list[dict[str, Any]]] = {}
    truncated = False
    selected_count = 0
    for row in rows:
        if row["anchor_type"] != node.node_type or row["anchor_id"] != node.node_id:
            continue
        if selected_count >= MAX_LONG_RANGE_ROWS:
            truncated = True
            continue
        selected = by_target.get(row["target_type"])
        if selected is None:
            selected = by_target.setdefault(row["target_type"], [])
        if len(selected) < LONG_RANGE_PER_TYPE_LIMIT:
            selected.append(row)
            selected_count += 1
        else:
            truncated = True
    return [row for target in sorted(by_target) for row in by_target[target]], truncated


def _full_dossier(
    data: Any,
    node: fixture.Node,
    *,
    evidence_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    node_payload = _node_payload(node)
    raw_edges, edges_truncated = _bounded_matches(
        data.EDGE_ROWS,
        lambda row: _matches_anchor(row, node.node_type, node.node_id),
        MAX_EDGE_LIMIT,
    )
    edges = [
        _with_neighbor(data, row, node.node_type, node.node_id)
        for row in raw_edges
    ]
    features, features_truncated = _bounded_matches(
        data.FEATURE_ROWS,
        lambda row: row["node_type"] == node.node_type and row["node_id"] == node.node_id,
        MAX_FEATURE_LIMIT,
    )
    ordered_evidence = (
        evidence_rows
        if evidence_rows is not None
        else sorted(data.EVIDENCE_ROWS, key=_evidence_sort_key)
    )
    evidence, evidence_truncated = _bounded_matches(
        ordered_evidence,
        lambda row: _matches_anchor(row, node.node_type, node.node_id),
        MAX_EVIDENCE_LIMIT,
    )
    evidence_total = sum(
        1 for row in ordered_evidence if _matches_anchor(row, node.node_type, node.node_id)
    )
    long_range, long_range_truncated = _bounded_long_range_matches(data.LONG_RANGE_ROWS, node)
    putative, putative_truncated = _bounded_matches(
        data.PUTATIVE_ROWS,
        lambda row: row["anchor_type"] == node.node_type and row["anchor_id"] == node.node_id,
        MAX_PUTATIVE_LIMIT,
    )
    truncated = any(
        (features_truncated, edges_truncated, evidence_truncated, long_range_truncated, putative_truncated)
    )
    return {
        "meta": _meta(data, truncated=truncated).model_dump(),
        "node": node_payload,
        "features": features,
        "edges": edges,
        "evidence": evidence,
        "evidence_meta": _evidence_meta(
            data,
            truncated=evidence_truncated,
            total=evidence_total,
            returned=len(evidence),
        ).model_dump(),
        "long_range": long_range,
        "putative_links": putative,
    }


def _trail_row(data: Any, valid_node_types: set[str], step: TrailStep) -> dict[str, str]:
    try:
        node = _node_or_404(data, valid_node_types, step.node_type, step.node_id)
    except HTTPException as exc:
        raise HTTPException(status_code=422, detail="unknown trail node") from exc
    return {"node_type": node.node_type, "node_id": node.node_id, "display_name": node.display_name, "via": step.via}


def _markdown_export(data: Any, dossier: dict[str, Any], trail: list[dict[str, str]]) -> str:
    node = dossier["node"]
    ranker_versions = sorted(
        {
            f"{row['ranker_id']}:{row['ranker_version']}"
            for row in dossier["long_range"]
        }
    )
    lines = [
        "---",
        f"snapshot_id: {data.snapshot_id}",
        f"data_mode: {data.mode}",
        f"node_type: {node['node_type']}",
        f"node_id: {node['node_id']}",
        f"ranker_versions: {json.dumps(ranker_versions)}",
        f"evidence_total: {dossier['evidence_meta']['total']}",
        f"evidence_returned: {dossier['evidence_meta']['returned']}",
        f"evidence_truncated: {str(dossier['evidence_meta']['truncated']).lower()}",
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
    lines.append(
        "Evidence export: bounded summary — "
        f"{dossier['evidence_meta']['returned']} of {dossier['evidence_meta']['total']} rows; "
        f"truncated: {str(dossier['evidence_meta']['truncated']).lower()}."
    )
    lines.extend(f"- observed `{row['relation']}` {row['source']} / {row['predicate']} / {row['source_record_id']} / score={row['evidence_score']}" for row in dossier["evidence"])
    lines.append("\n## Long-range ranked connections")
    lines.extend(f"- ranked {row['target_type']}:{row['target_id']} {row['target_name']} score={row['score']} path={row['support_path']} caveat={row['caveats']}" for row in dossier["long_range"])
    lines.append("\n## Putative inferred links")
    lines.extend(f"- inferred {row['target_type']}:{row['target_id']} {row['target_name']} ({row['policy_class']}) template={row['template_id']} caveat={row['leakage_caveat']}" for row in dossier["putative_links"])
    lines.append("\n## Navigation trail")
    lines.extend(f"{index}. {row['display_name']} ({row['node_type']}:{row['node_id']}) — {row['via']}" for index, row in enumerate(trail, start=1))
    return "\n".join(lines) + "\n"


def _html_export(data: Any, dossier: dict[str, Any], trail: list[dict[str, str]]) -> str:
    markdown = _markdown_export(data, dossier, trail)
    evidence_meta = dossier["evidence_meta"]
    payload = {
        "contract": "bounded-v1",
        "snapshot_id": data.snapshot_id,
        "evidence_total": evidence_meta["total"],
        "evidence_returned": evidence_meta["returned"],
        "evidence_truncated": evidence_meta["truncated"],
        "markdown": markdown,
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        '<meta name="jouvence-viewer-print-contract" content="bounded-v1">'
        "<title>Jouvence-Graph export</title></head>"
        '<body data-jouvence-print-contract="bounded-v1" '
        f'data-snapshot-id="{html.escape(data.snapshot_id, quote=True)}">'
        '<script id="jouvence-print-payload" type="application/json">'
        f"{payload_json}</script></body></html>"
    )


def _csv_zip_export(data: Any, dossier: dict[str, Any], trail: list[dict[str, str]]) -> bytes:
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
        ranker_versions = sorted(
            {
                f"{row['ranker_id']}:{row['ranker_version']}"
                for row in dossier["long_range"]
            }
        )
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "snapshot_id": data.snapshot_id,
                    "data_mode": data.mode,
                    "row_kinds": ["observed", "ranked", "inferred"],
                    "ranker_versions": ranker_versions,
                    "evidence": {
                        "scope": "bounded-summary",
                        "total": dossier["evidence_meta"]["total"],
                        "returned": dossier["evidence_meta"]["returned"],
                        "truncated": dossier["evidence_meta"]["truncated"],
                    },
                },
                indent=2,
            ),
        )
        uncompressed_bytes = 0
        for name, rows in tables.items():
            payload = _csv_text(rows)
            uncompressed_bytes += len(payload.encode("utf-8"))
            if uncompressed_bytes > MAX_EXPORT_RESPONSE_BYTES:
                raise HTTPException(status_code=413, detail="export response too large")
            archive.writestr(name, payload)
    return buffer.getvalue()


def _bounded_export_payload(payload: str | bytes) -> str | bytes:
    size = len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)
    if size > MAX_EXPORT_RESPONSE_BYTES:
        raise HTTPException(status_code=413, detail="export response too large")
    return payload


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "\n"
    fields = sorted({key for row in rows for key in row})
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
