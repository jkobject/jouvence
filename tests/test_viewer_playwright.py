from __future__ import annotations

import json
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
STATIC_PORT = 8767
STATIC_BASE = f"http://127.0.0.1:{STATIC_PORT}"


@pytest.fixture(scope="module")
def viewer_server() -> Iterator[str]:
    proc = subprocess.Popen(
        ["uv", "run", "jouvence-viewer", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        import urllib.request

        launch_url = ""
        for _ in range(80):
            if not launch_url and proc.stdout:
                line = proc.stdout.readline()
                if line.startswith("Local URL: "):
                    launch_url = line.removeprefix("Local URL: ").strip()
            try:
                with urllib.request.urlopen(BASE, timeout=0.25) as response:
                    if response.status == 200 and launch_url:
                        yield launch_url
                        return
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(proc.stdout.read() if proc.stdout else "viewer server exited")
                time.sleep(0.1)
        raise RuntimeError("viewer server did not become ready")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def static_server() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(STATIC_PORT), "--bind", "127.0.0.1", "--directory", str(ROOT / "docs")],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        import urllib.request

        for _ in range(80):
            try:
                with urllib.request.urlopen(f"{STATIC_BASE}/viewer.html", timeout=0.25) as response:
                    if response.status == 200:
                        yield STATIC_BASE
                        return
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(proc.stdout.read() if proc.stdout else "static server exited")
                time.sleep(0.1)
        raise RuntimeError("static server did not become ready")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(params=[(1280, 900), (390, 844)], ids=["desktop", "mobile"])
def page(viewer_server: str, request):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": request.param[0], "height": request.param[1]}, accept_downloads=True)
        page = context.new_page()
        yield page
        browser.close()


def test_search_link_history_and_exports(page: Page, viewer_server: str) -> None:
    page.goto(viewer_server)
    expect(page.locator("#entity-name")).to_have_text("BRCA1")
    expect(page.locator("#source-button")).to_contain_text("Deterministic fixture")
    expect(page.locator("#mode-status")).to_have_text("fixture")
    expect(page.locator("#snapshot-status")).to_have_text("fixture-v1")
    expect(page.locator("#cache-status")).to_have_text("in-memory")
    expect(page.locator("#cost-warning")).to_contain_text("read-only")

    page.reload()
    expect(page.locator("#source-button")).to_contain_text("Deterministic fixture")
    expect(page.locator("#mode-status")).to_have_text("fixture")

    page.locator("#global-search").fill("TP53")
    expect(page.locator("[data-search-index='0']")).to_contain_text("TP53")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator("#entity-name")).to_have_text("TP53")
    expect(page.locator("#history-count")).to_have_text("1 node")

    page.locator("#global-search").fill("BRCA1")
    page.locator("[data-search-index='0']").click()
    expect(page.locator("#entity-name")).to_have_text("BRCA1")
    expect(page.locator("#history-count")).to_have_text("1 node")

    page.locator(".js-node-link", has_text="breast carcinoma").first.click()
    expect(page.locator("#entity-name")).to_have_text("breast carcinoma")
    expect(page.locator("#history-count")).to_have_text("2 nodes")

    page.locator(".history-step").first.click()
    expect(page.locator("#entity-name")).to_have_text("BRCA1")
    expect(page.locator("#history-count")).to_have_text("1 node")

    with page.expect_download() as download_info:
        page.locator("[data-export='markdown']").click()
    assert download_info.value.suggested_filename.endswith(".md")

    with page.expect_download() as csv_download:
        page.locator("[data-export='csv']").click()
    assert csv_download.value.suggested_filename.endswith(".zip")


def test_immediate_keyboard_search_is_deterministic(page: Page, viewer_server: str) -> None:
    page.goto(viewer_server)

    search = page.locator("#global-search")
    for expected in ("TP53", "BRCA1") * 5:
        search.fill(expected)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        expect(page.locator("#entity-name")).to_have_text(expected)


def test_stale_search_response_cannot_replace_newer_results(page: Page, viewer_server: str) -> None:
    page.add_init_script(
        """
        const realFetch = window.fetch.bind(window);
        window.fetch = (resource, options) => {
          const url = String(resource);
          const delay = url.includes('/api/search?') && url.includes('q=TP53') ? 250 : 0;
          return new Promise(resolve => setTimeout(() => resolve(realFetch(resource, options)), delay));
        };
        """
    )
    page.goto(viewer_server)

    search = page.locator("#global-search")
    search.fill("TP53")
    search.fill("EGFR")
    expect(page.locator("#search-results")).to_contain_text("EGFR")
    page.wait_for_timeout(350)
    expect(page.locator("#search-results")).to_contain_text("EGFR")
    expect(page.locator("#search-results")).not_to_contain_text("TP53")


def test_queued_keyboard_action_is_abandoned_when_query_changes(page: Page, viewer_server: str) -> None:
    page.add_init_script(
        """
        const realFetch = window.fetch.bind(window);
        window.fetch = (resource, options) => {
          const url = String(resource);
          const delay = url.includes('/api/search?') && url.includes('q=TP53') ? 250 : 0;
          return new Promise(resolve => setTimeout(() => resolve(realFetch(resource, options)), delay));
        };
        """
    )
    page.goto(viewer_server)

    search = page.locator("#global-search")
    search.fill("TP53")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    search.fill("EGFR")
    expect(page.locator("#search-results")).to_contain_text("EGFR")
    page.wait_for_timeout(350)
    expect(page.locator("#entity-name")).to_have_text("BRCA1")


def test_backend_unavailable_static_fallback_and_missing_search_state(page: Page) -> None:
    page.goto((ROOT / "docs" / "viewer.html").as_uri())
    expect(page.locator("#source-button")).to_contain_text("Embedded fixture fallback")
    page.locator("#global-search").fill("no-such-node")
    expect(page.locator("#search-results")).to_contain_text("No fixture match")


def test_relative_static_bundle_loads_and_preserves_semantics(page: Page, static_server: str) -> None:
    responses: list[str] = []
    page.on("response", lambda response: responses.append(response.url))
    page.goto(f"{static_server}/viewer.html")

    expect(page.locator("#source-button")).to_contain_text("Static fixture bundle")
    expect(page.get_by_role("link", name="Full-data installation guide")).to_have_attribute(
        "href", "viewer-install.html"
    )
    assert any(url.endswith("/viewer-data/manifest.json") for url in responses)
    assert any("/viewer-data/entities/gene--ENSG00000012048.json" in url for url in responses)
    expect(page.locator("#connections-list")).not_to_contain_text("gefitinib")
    expect(page.locator("#long-range-grid")).to_contain_text("gefitinib")
    expect(page.locator("#evidence-scope")).to_contain_text("Static top-evidence summary")


def test_local_evidence_reports_counts_and_loads_all_bounded_pages(page: Page, viewer_server: str) -> None:
    rows = [
        {
            "edge_key": "fixture:edge:brca1-disease",
            "relation": "disease_associated_gene",
            "x_id": "ENSG00000012048",
            "x_type": "gene",
            "y_id": "EFO:0000305",
            "y_type": "disease",
            "source": "test",
            "source_dataset": "pagination",
            "source_record_id": f"record-{index:03d}",
            "paper_id": f"PMID:{index}",
            "predicate": "associated_with",
            "evidence_score": 0.9,
            "row_kind": "observed",
        }
        for index in range(12)
    ]

    def evidence_route(route) -> None:
        params = parse_qs(urlsplit(route.request.url).query)
        start = int(params.get("cursor", ["0"])[0])
        selected = rows[start : start + 10]
        stop = start + len(selected)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "meta": {
                        "snapshot_id": "fixture-v1",
                        "data_mode": "fixture",
                        "bundle_version": "viewer-fixture-schema-v1",
                        "truncated": stop < len(rows),
                        "next_cursor": str(stop) if stop < len(rows) else None,
                        "total": len(rows),
                        "returned": len(selected),
                    },
                    "rows": selected,
                }
            ),
        )

    page.route("**/api/nodes/gene/ENSG00000012048/evidence*", evidence_route)
    page.goto(viewer_server)

    expect(page.locator("#evidence-scope")).to_contain_text("Complete local evidence")
    expect(page.locator("#evidence-state")).to_have_text("Returned 10 of 12 · more available")
    expect(page.locator("#stat-evidence")).to_have_text("12")
    expect(page.locator("#evidence-body tr")).to_have_count(10)
    expect(page.locator("#load-more-evidence")).to_be_visible()

    page.locator("#load-more-evidence").click()

    expect(page.locator("#evidence-state")).to_have_text("Returned 12 of 12 · complete")
    expect(page.locator("#evidence-body tr")).to_have_count(12)
    expect(page.locator("#load-more-evidence")).to_be_hidden()


def test_stale_evidence_page_cannot_append_after_navigation(page: Page, viewer_server: str) -> None:
    rows = [
        {
            "edge_key": "fixture:edge:brca1-disease",
            "relation": "disease_associated_gene",
            "x_id": "ENSG00000012048",
            "x_type": "gene",
            "y_id": "EFO:0000305",
            "y_type": "disease",
            "source": "stale-source",
            "source_dataset": "pagination",
            "source_record_id": f"stale-record-{index:03d}",
            "paper_id": f"STALE:{index}",
            "predicate": "associated_with",
            "evidence_score": 0.1,
            "row_kind": "observed",
        }
        for index in range(12)
    ]
    target_rows = [
        {
            **row,
            "edge_key": "fixture:edge:tp53-disease",
            "x_id": "ENSG00000141510",
            "source_record_id": f"target-record-{index:03d}",
            "paper_id": f"TARGET:{index}",
        }
        for index, row in enumerate(rows)
    ]

    page.add_init_script(
        """
        const realFetch = window.fetch.bind(window);
        window.fetch = (resource, options) => {
          const url = String(resource);
          const isNextPage = url.includes('cursor=10');
          const delay = url.includes('/ENSG00000012048/evidence') && isNextPage
            ? 500
            : (url.includes('/ENSG00000141510/evidence') && isNextPage ? 1000 : 0);
          return delay
            ? new Promise(resolve => setTimeout(() => resolve(realFetch(resource, options)), delay))
            : realFetch(resource, options);
        };
        """
    )

    def evidence_route(route) -> None:
        params = parse_qs(urlsplit(route.request.url).query)
        start = int(params.get("cursor", ["0"])[0])
        available = target_rows if "ENSG00000141510" in route.request.url else rows
        selected = available[start : start + 10]
        stop = start + len(selected)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "meta": {
                        "snapshot_id": "fixture-v1",
                        "data_mode": "fixture",
                        "bundle_version": "viewer-fixture-schema-v1",
                        "truncated": stop < len(available),
                        "next_cursor": str(stop) if stop < len(available) else None,
                        "total": len(available),
                        "returned": len(selected),
                    },
                    "rows": selected,
                }
            ),
        )

    page.route("**/api/nodes/gene/*/evidence*", evidence_route)
    page.goto(viewer_server)
    expect(page.locator("#load-more-evidence")).to_be_visible()

    page.evaluate("document.querySelector('#load-more-evidence').click()")
    page.evaluate("document.querySelector('[data-node-id=\"ENSG00000141510\"]').click()")
    expect(page.locator("#entity-name")).to_have_text("TP53")
    expect(page.locator("#load-more-evidence")).to_be_visible()
    page.evaluate("document.querySelector('#load-more-evidence').click()")
    page.wait_for_timeout(600)

    expect(page.locator("#entity-name")).to_have_text("TP53")
    expect(page.locator("#evidence-body")).not_to_contain_text("stale-record-010")
    expect(page.locator("#load-more-evidence")).to_be_disabled()

    page.wait_for_timeout(500)
    expect(page.locator("#evidence-state")).to_have_text("Returned 12 of 12 · complete")
    expect(page.locator("#evidence-body")).to_contain_text("TARGET:11")


def test_static_exports_contain_dossier_trail_and_row_kinds(page: Page, static_server: str, tmp_path: Path) -> None:
    page.goto(f"{static_server}/viewer.html")
    page.locator(".js-node-link", has_text="breast carcinoma").first.click()
    expect(page.locator("#history-count")).to_have_text("2 nodes")
    static_dossier = json.loads(
        (ROOT / "docs" / "viewer-data" / "entities" / "disease--EFO_0000305.json").read_text()
    )

    with page.expect_download() as markdown_download:
        page.locator("[data-export='markdown']").click()
    markdown = tmp_path / markdown_download.value.suggested_filename
    markdown_download.value.save_as(markdown)
    text = markdown.read_text()
    assert markdown.name == "breast-carcinoma-dossier.md"
    assert "## Features" in text
    assert "## Direct observed edges" in text
    assert "## Long-range ranked connections" in text
    assert "## Putative inferred links" in text
    assert "## Navigation trail" in text
    assert "Evidence export: bounded summary" in text
    assert "evidence_total:" in text
    assert "evidence_returned:" in text
    assert "evidence_truncated:" in text
    assert all(kind in text for kind in ("observed", "ranked", "inferred"))
    assert "breast carcinoma (disease:EFO:0000305) — disease_associated_gene" in text

    page.evaluate("window.__printCalled = false; window.print = () => { window.__printCalled = true; }")
    page.locator("[data-export='pdf']").click()
    assert page.evaluate("window.__printCalled") is True

    pdf_path = tmp_path / "breast-carcinoma-dossier.pdf"
    page.pdf(path=pdf_path, print_background=True)
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert pdf_path.stat().st_size > 10_000

    with page.expect_download() as csv_download:
        page.locator("[data-export='csv']").click()
    archive_path = tmp_path / csv_download.value.suggested_filename
    csv_download.value.save_as(archive_path)
    assert archive_path.name == "breast-carcinoma-dossier.zip"
    assert archive_path.read_bytes().startswith(b"PK")
    with zipfile.ZipFile(archive_path) as archive:
        expected = {
            "node.csv",
            "features.csv",
            "edges.csv",
            "evidence.csv",
            "long_range.csv",
            "putative_links.csv",
            "history.csv",
            "manifest.json",
        }
        assert expected.issubset(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert all(kind in manifest["row_kinds"] for kind in ("observed", "ranked", "inferred"))
        assert manifest["evidence"] == {
            "scope": "bounded-summary",
            "total": static_dossier["evidence_meta"]["total"],
            "returned": static_dossier["evidence_meta"]["returned"],
            "truncated": static_dossier["evidence_meta"]["truncated"],
        }
        history = archive.read("history.csv").decode()
        assert "Search start" in history
        assert "breast carcinoma" in history
        assert "disease_associated_gene" in history
