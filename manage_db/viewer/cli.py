"""Command line entry point for the hardened local Jouvence viewer."""

from __future__ import annotations

import argparse
import json
import secrets
import tempfile
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app
from .bundle import BundleError, FIXTURE_DATA, build_fixture_bundle, open_viewer_bundle


def _validated_host(host: str) -> str:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("jouvence-viewer binds only to 127.0.0.1")
    return "127.0.0.1"


def _viewer_url(host: str, port: int, token: str) -> str:
    """Keep the bootstrap token in a fragment, never in the HTTP request line."""

    return f"http://{host}:{port}/#token={token}"


def _fixture_smoke() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="jouvence-viewer-smoke-") as directory:
        root = build_fixture_bundle(Path(directory) / "bundle")
        source = open_viewer_bundle(str(root))
        expected = ("gene", "ENSG00000012048")
        if expected not in source.NODES:
            raise BundleError("fixture bundle smoke could not resolve BRCA1")
        return {
            "mode": "fixture-bundle",
            "snapshot_id": source.snapshot_id,
            "status": "pass",
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve a read-only Jouvence viewer bundle on localhost.")
    parser.add_argument("--data-root", help="Local viewer-bundle path or reviewed gs:// viewer-bundle URI.")
    parser.add_argument("--billing-project", help="Your consumer project for GCS requester-pays charges.")
    parser.add_argument("--manifest-sha256", help="Independently published SHA-256 of a reviewed GCS viewer manifest.")
    parser.add_argument("--cache-root", help="Optional bounded immutable GCS bundle cache directory.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host; only 127.0.0.1/localhost are accepted.")
    parser.add_argument("--port", default=8765, type=int, help="Local port to bind.")
    parser.add_argument("--open", action="store_true", help="Open the viewer in the default browser.")
    parser.add_argument("--fixture-smoke", action="store_true", help="Build, verify, query, and remove a no-cloud fixture bundle, then exit.")
    args = parser.parse_args(argv)
    if args.fixture_smoke:
        print(json.dumps(_fixture_smoke(), sort_keys=True))
        return
    try:
        host = _validated_host(args.host)
        source = (
            open_viewer_bundle(
                args.data_root,
                billing_project=args.billing_project,
                cache_root=args.cache_root,
                expected_manifest_sha256=args.manifest_sha256,
            )
            if args.data_root
            else FIXTURE_DATA
        )
    except (BundleError, ValueError) as exc:
        parser.error(str(exc))
    token = secrets.token_urlsafe(32)
    app = create_app(data_source=source, session_token=token)
    # A fragment is available to browser JavaScript but is never sent in the
    # HTTP request line, so the session token cannot appear in access logs.
    url = _viewer_url(host, args.port, token)
    print(
        f"Jouvence viewer: {source.mode} · {source.snapshot_id} · cache={source.cache_status}\n"
        f"Local URL: {url}\n"
        "Google credentials remain in this host process and are never sent to the browser.",
        flush=True,
    )
    if source.requester_pays_warning:
        print(source.requester_pays_warning)
    if args.open:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
