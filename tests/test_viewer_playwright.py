from __future__ import annotations

import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

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
        [sys.executable, "-m", "uvicorn", "manage_db.viewer.app:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        import urllib.request

        for _ in range(80):
            try:
                with urllib.request.urlopen(f"{BASE}/api/session", timeout=0.25) as response:
                    if response.status == 200:
                        yield BASE
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

    page.locator("#global-search").fill("TP53")
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
    expect(page.get_by_role("link", name="Access the full database locally")).to_have_attribute(
        "href", "getting-started-data.md"
    )
    assert any(url.endswith("/viewer-data/manifest.json") for url in responses)
    assert any("/viewer-data/entities/gene--ENSG00000012048.json" in url for url in responses)
    expect(page.locator("#connections-list")).not_to_contain_text("gefitinib")
    expect(page.locator("#long-range-grid")).to_contain_text("gefitinib")


def test_static_exports_contain_dossier_trail_and_row_kinds(page: Page, static_server: str, tmp_path: Path) -> None:
    page.goto(f"{static_server}/viewer.html")
    page.locator(".js-node-link", has_text="breast carcinoma").first.click()
    expect(page.locator("#history-count")).to_have_text("2 nodes")

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
        manifest = archive.read("manifest.json").decode()
        assert all(kind in manifest for kind in ("observed", "ranked", "inferred"))
        history = archive.read("history.csv").decode()
        assert "Search start" in history
        assert "breast carcinoma" in history
        assert "disease_associated_gene" in history
