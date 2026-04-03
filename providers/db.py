"""Reusable SQLite helpers shared by all providers.

The schema (readings + devices) is the stable contract between providers
and the replay server.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from providers import ProviderBase


def parse_iso_to_ms(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def create_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            device_id TEXT NOT NULL,
            property  TEXT NOT NULL,
            ts        INTEGER NOT NULL,
            value     TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id   TEXT PRIMARY KEY,
            definition  TEXT NOT NULL
        )
    """)


def import_readings(
    conn: sqlite3.Connection,
    provider: ProviderBase,
    filepath: Path,
    device_id: str,
    prop: str,
) -> int:
    rows = provider.parse_readings(filepath, device_id, prop)
    conn.executemany(
        "INSERT INTO readings (device_id, property, ts, value) VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def import_devices(conn: sqlite3.Connection, config: dict) -> int:
    devices = config.get("devices", [])
    for device in devices:
        conn.execute(
            "INSERT INTO devices (device_id, definition) VALUES (?, ?)",
            (device["id"], json.dumps(device)),
        )
    return len(devices)


def build_db(
    provider: ProviderBase,
    config: dict,
    manifest: dict[str, dict],
    tmp_dir: Path,
    db_path: Path,
):
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    device_count = import_devices(conn, config)
    print(f"\nImported {device_count} device definitions")

    bulk_count = provider.bulk_import(config, conn)
    if bulk_count is not None:
        total_rows = bulk_count
    else:
        total_rows = 0
        for filename, meta in manifest.items():
            filepath = tmp_dir / filename
            if not filepath.exists():
                print(f"  Skipping {filename} (file not found)")
                continue

            device_id = meta["device_id"]
            prop = meta["property"]
            count = import_readings(conn, provider, filepath, device_id, prop)
            total_rows += count
            print(f"  {filename}: {count} records")

    print("\nCreating indexes ...")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_lookup
        ON readings (device_id, property, ts)
    """)

    conn.commit()
    conn.close()

    print(f"Done. {total_rows} readings + {device_count} devices -> {db_path}")
