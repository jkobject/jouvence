from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def viewer_server() -> str:
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


def test_backend_unavailable_static_fallback_and_missing_search_state(page: Page) -> None:
    page.goto((ROOT / "docs" / "viewer.html").as_uri())
    expect(page.locator("#source-button")).to_contain_text("Demo fallback")
    page.locator("#global-search").fill("no-such-node")
    expect(page.locator("#search-results")).to_contain_text("No fixture match")
