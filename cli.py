#!/usr/bin/env python3
"""wot-replay CLI — build fixture databases and serve replay data."""

import argparse
import sys
import tempfile
from pathlib import Path


def _resolve_sources(provider: str, sources: str | None) -> Path:
    if sources:
        return Path(sources)
    return Path(__file__).parent / "providers" / provider / "sources.yaml"


def cmd_build(args):
    import yaml

    from providers import load_provider
    from providers.db import build_db

    provider = load_provider(args.provider)
    sources_path = _resolve_sources(args.provider, args.sources)

    if not sources_path.exists():
        print(f"Error: {sources_path} not found", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.output)
    if db_path.exists() and not args.force_overwrite:
        print(
            f"Error: {db_path} already exists. Use --force-overwrite to replace it.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(sources_path) as f:
        config = yaml.safe_load(f)

    with tempfile.TemporaryDirectory(prefix="wot-replay-") as tmp:
        tmp_dir = Path(tmp)

        print(f"Fetching data to {tmp_dir} ...\n")
        manifest = provider.fetch(config, tmp_dir)

        provider_name = config.get("provider", args.provider)
        for device in config.get("devices", []):
            device.setdefault("provider", provider_name)

        if db_path.exists():
            db_path.unlink()

        build_db(provider, config, manifest, tmp_dir, db_path)


def cmd_serve(args):
    import os

    import uvicorn

    os.environ.setdefault("DB_PATH", args.db)
    os.environ.setdefault("REPLAY_BASE_URL", args.base_url)

    uvicorn.run(
        "replay_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="wot-replay",
        description="Build and serve offline WoT replay data",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- build ---
    build_parser = sub.add_parser("build", help="Build fixture database")
    build_parser.add_argument(
        "provider",
        help="Provider name (e.g. smartlivingnext, shed_eu)",
    )
    build_parser.add_argument(
        "-s",
        "--sources",
        default=None,
        help="Path to sources.yaml (default: providers/<provider>/sources.yaml)",
    )
    build_parser.add_argument(
        "-o",
        "--output",
        default="fixtures.db",
        help="Output SQLite database (default: fixtures.db)",
    )
    build_parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Overwrite existing database",
    )
    build_parser.set_defaults(func=cmd_build)

    # --- serve ---
    serve_parser = sub.add_parser("serve", help="Start the replay server")
    serve_parser.add_argument(
        "--db",
        default="fixtures.db",
        help="Path to fixtures.db (default: fixtures.db)",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Port (default: 9000)",
    )
    serve_parser.add_argument(
        "--base-url",
        default="http://localhost:9000",
        help="Public base URL for Thing Descriptions",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
