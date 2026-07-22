"""Command line entry point for the local fixture viewer."""

from __future__ import annotations

import argparse
import webbrowser

import uvicorn


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the Jouvence-Graph fixture viewer on localhost.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host; only 127.0.0.1/localhost are accepted in Phase 1.")
    parser.add_argument("--port", default=8765, type=int, help="Local port to bind.")
    parser.add_argument("--open", action="store_true", help="Open the viewer in the default browser.")
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Phase 1 viewer only binds to 127.0.0.1/localhost")
    url = f"http://{args.host}:{args.port}/"
    if args.open:
        webbrowser.open(url)
    uvicorn.run("manage_db.viewer.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
