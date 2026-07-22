from __future__ import annotations

import json
import subprocess
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from manage_db.viewer.cli import _validated_host, _viewer_url

ROOT = Path(__file__).resolve().parents[1]


def test_cli_never_allows_non_local_bind() -> None:
    assert _validated_host("127.0.0.1") == "127.0.0.1"
    assert _validated_host("localhost") == "127.0.0.1"
    for host in ("0.0.0.0", "::", "192.168.1.10", "example.com"):
        with pytest.raises(ValueError, match="127.0.0.1"):
            _validated_host(host)


def test_session_token_is_in_fragment_not_http_request_target() -> None:
    url = _viewer_url("127.0.0.1", 8765, "random-secret")
    parsed = urlsplit(url)
    assert parsed.query == ""
    assert parsed.path == "/"
    assert parsed.fragment == "token=random-secret"


def test_asgi_app_cannot_be_launched_without_hardened_cli() -> None:
    assert not hasattr(import_module("manage_db.viewer.app"), "app")


def test_one_command_fixture_smoke() -> None:
    completed = subprocess.run(
        ["uv", "run", "jouvence-viewer", "--fixture-smoke"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload == {
        "mode": "fixture-bundle",
        "snapshot_id": "fixture-v1",
        "status": "pass",
    }
