#!/usr/bin/env python3
"""Download historical IoT data and build fixtures.db.

Reads a sources.yaml for the chosen provider, downloads data, then imports
everything into a SQLite database (fixtures.db).

Usage:
    python build_fixtures.py                                    # defaults: smartlivingnext
    python build_fixtures.py --provider smartlivingnext
    python build_fixtures.py -s custom_sources.yaml -o my.db
    python build_fixtures.py --force-overwrite
"""

import argparse
import sys
import tempfile
from pathlib import Path

import yaml

from providers import load_provider
from providers.db import build_db


def main():
    parser = argparse.ArgumentParser(
        description="Download IoT history data and build fixtures.db"
    )
    parser.add_argument(
        "-p",
        "--provider",
        default="smartlivingnext",
        help="Provider name (default: smartlivingnext)",
    )
    parser.add_argument(
        "-s",
        "--sources",
        default=None,
        help="Path to sources.yaml (default: providers/<provider>/sources.yaml)",
    )
    parser.add_argument(
        "-o", "--output", default="fixtures.db", help="Output SQLite database"
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Overwrite existing fixtures.db",
    )
    args = parser.parse_args()

    provider = load_provider(args.provider)

    sources_path = Path(
        args.sources
        if args.sources
        else Path(__file__).parent / "providers" / args.provider / "sources.yaml"
    )
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

        # Inject provider name into device definitions (fetch may have populated them)
        provider_name = config.get("provider", args.provider)
        for device in config.get("devices", []):
            device.setdefault("provider", provider_name)

        if db_path.exists():
            db_path.unlink()

        build_db(provider, config, manifest, tmp_dir, db_path)


if __name__ == "__main__":
    main()
