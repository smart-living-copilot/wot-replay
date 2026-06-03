"""ContextAct@A4H provider — daily-living sensor data from the Amiqual4Home
intelligent apartment (Lago et al., 2017).

The dataset is distributed as a single Mendeley zip. It is downloaded on demand
(see ``providers.download``) and read from disk; nothing is committed to the
repo. Measurement files are ``";"``-quoted triples with no header::

    "2016-11-14 17:57:07,174";"CO2_Cuisine";"512"

One Thing is generated per physical device (see ``catalog``); one property per
underlying sensor variable.
"""

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from providers import ProviderBase, register_provider
from providers.contextact_a4h.catalog import (
    build_devices,
    device_key,
    load_variables,
)
from providers.contextact_a4h.td import generate_device_td
from providers.download import ensure_dataset

DEFAULT_DATA_DIR = "providers/contextact_a4h/data"
DOWNLOAD_URL = "https://data.mendeley.com/public-api/zip/fcj2hmz5kb/download/3"
MONTHS = {"july": "July", "november": "November"}
BATCH_SIZE = 50_000


def _parse_ts(raw: str) -> int:
    """Parse 'yyyy-MM-dd HH:mm:ss,SSS' (comma = ms) into a UTC ms timestamp."""
    dt = datetime.fromisoformat(raw.replace(",", "."))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _parse_value(raw: str):
    """Numbers become floats; everything else (ON/OFF, OPEN/CLOSED, RGB) stays a string."""
    try:
        return float(raw)
    except ValueError:
        return raw


def _iso_to_ms(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class ContextActA4HProvider(ProviderBase):
    def fetch(self, config: dict, tmp_dir: Path) -> dict[str, dict]:
        data_dir = self._ensure_data(config)
        time_range = self._time_range(config)

        # Discover which sensor ids actually appear in the selected window.
        present: set[str] = set()
        for path in self._measurement_files(config, data_dir):
            for ts, sid, _ in self._iter_rows(path, time_range):
                if device_key(sid) is not None:
                    present.add(sid)

        variables = load_variables(data_dir / "Variable Description.xlsx")
        devices = build_devices(variables, present_ids=present)
        config["devices"] = devices

        n_props = sum(len(d["properties"]) for d in devices)
        print(f"Discovered {len(devices)} devices ({n_props} sensor variables)")
        return {}

    def bulk_import(self, config: dict, conn: sqlite3.Connection) -> int:
        data_dir = self._ensure_data(config)
        time_range = self._time_range(config)

        # sensor id -> device id, from devices populated by fetch().
        index: dict[str, str] = {}
        for d in config.get("devices", []):
            for p in d["properties"]:
                index[p["sensor_id"]] = d["id"]

        total = 0
        for path in self._measurement_files(config, data_dir):
            count = self._import_file(path, conn, index, time_range)
            total += count
            print(f"  {path.name}: {count} records")
        return total

    def _import_file(self, path, conn, index, time_range) -> int:
        count = 0
        batch: list[tuple[str, str, int, str]] = []
        for ts, sid, raw in self._iter_rows(path, time_range):
            device_id = index.get(sid)
            if device_id is None:
                continue
            value = json.dumps({"value": _parse_value(raw)})
            batch.append((device_id, sid, ts, value))
            if len(batch) >= BATCH_SIZE:
                count += self._flush(conn, batch)
                batch.clear()
        if batch:
            count += self._flush(conn, batch)
        return count

    @staticmethod
    def _flush(conn, batch) -> int:
        conn.executemany(
            "INSERT INTO readings (device_id, property, ts, value) VALUES (?, ?, ?, ?)",
            batch,
        )
        return len(batch)

    @staticmethod
    def _iter_rows(path: Path, time_range):
        """Yield (ts_ms, sensor_id, raw_value) from a measurement file."""
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            for row in reader:
                if len(row) < 3 or not row[0]:
                    continue
                try:
                    ts = _parse_ts(row[0])
                except ValueError:
                    continue
                if time_range and not (time_range[0] <= ts <= time_range[1]):
                    continue
                yield ts, row[1], row[2]

    def parse_readings(self, filepath, device_id, prop):
        raise NotImplementedError("contextact_a4h uses bulk_import")

    def generate_td(self, device: dict, replay_base_url: str) -> dict:
        return generate_device_td(device, replay_base_url)

    # --- config helpers ---
    @staticmethod
    def _data_dir(config: dict) -> Path:
        return Path(config.get("data_dir", DEFAULT_DATA_DIR))

    def _ensure_data(self, config: dict) -> Path:
        return ensure_dataset(
            self._data_dir(config),
            config.get("download_url", DOWNLOAD_URL),
            marker="README.txt",
            download=config.get("download", True),
        )

    @staticmethod
    def _measurement_files(config: dict, data_dir: Path) -> list[Path]:
        months = config.get("months") or ["november"]
        variant = str(config.get("variant", "change")).capitalize()
        files = []
        for month in months:
            name = MONTHS.get(str(month).lower())
            if name is None:
                raise ValueError(f"Unknown month '{month}' (expected july/november)")
            files.append(
                data_dir / "sensor measurements" / f"{name}_All_{variant}.csv.log"
            )
        return files

    @staticmethod
    def _time_range(config: dict) -> tuple[int, int] | None:
        from_str = config.get("from")
        to_str = config.get("to")
        if from_str is None and to_str is None:
            return None
        from_ms = _iso_to_ms(from_str) if from_str else 0
        to_ms = _iso_to_ms(to_str) if to_str else 2**63 - 1
        return (from_ms, to_ms)


register_provider("contextact_a4h", ContextActA4HProvider)
