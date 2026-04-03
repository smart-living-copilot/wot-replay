"""SHED EU provider — imports household sensor data from CSV files.

Data consists of two CSV types:
  - periodic_data_*.csv: 5-minute aggregates (min/avg/max) for temperature,
    co2, humidity, ambient_light, voc per room.
  - event_data.csv: discrete events (movement on, door open/close) per room.

One device (Thing Description) is created per room within each household.
Properties are named by sensor type (e.g. ``temperature``, ``movement``).
"""

import csv
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from providers import ProviderBase, register_provider
from providers.shed_eu.td import generate_room_td

BATCH_SIZE = 50_000


def _iso_to_ms(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _device_id(household_id: str, country: str, room: str) -> str:
    return f"shed-eu-{household_id}-{country}-{room}"


def _parse_household_range(range_str: str) -> tuple[int, int]:
    """Parse a range string like '1-10' into (start, end) inclusive."""
    parts = range_str.split("-", 1)
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    val = int(parts[0])
    return val, val


def _ts_in_range(ts_ms: int, time_range: tuple[int, int] | None) -> bool:
    if time_range is None:
        return True
    return time_range[0] <= ts_ms <= time_range[1]


def _household_in_range(
    household_id: str, household_range: tuple[int, int] | None
) -> bool:
    if household_range is None:
        return True
    try:
        hid = int(household_id)
    except ValueError:
        return False
    return household_range[0] <= hid <= household_range[1]


class ShedEuProvider(ProviderBase):
    def fetch(self, config: dict, tmp_dir: Path) -> dict[str, dict]:
        """Scan CSVs to discover rooms and populate config['devices']."""
        data_dir = self._data_dir(config)
        household_range = self._household_range(config)
        time_range = self._time_range(config)

        # Discover all (household_id, country, room) → {periodic: {sensor}, event: {sensor}}
        rooms: dict[tuple[str, str, str], dict[str, set[str]]] = defaultdict(
            lambda: {"periodic": set(), "event": set()}
        )

        # Scan periodic CSVs
        for csv_path in sorted(data_dir.glob("periodic_data_monthly_csv/*.csv")):
            self._scan_csv(
                csv_path, rooms, kind="periodic",
                household_range=household_range, time_range=time_range,
            )

        # Scan event CSV
        event_csv = data_dir / "event_data" / "event_data.csv"
        if event_csv.exists():
            self._scan_csv(
                event_csv, rooms, kind="event",
                household_range=household_range, time_range=time_range,
            )

        # Build device entries — one per room
        devices = []
        for (hid, country, room), sensors in sorted(rooms.items()):
            devices.append(
                {
                    "id": _device_id(hid, country, room),
                    "type": "room",
                    "title": f"{room.replace('_', ' ').title()} — Household {hid} ({country})",
                    "description": f"Room '{room}' in SHED EU household {hid}, {country}",
                    "location": {
                        "country": country,
                        "household_id": hid,
                        "room": room,
                    },
                    "metadata": {
                        "household_id": hid,
                        "country": country,
                        "room": room,
                    },
                    "periodic_sensors": sorted(sensors["periodic"]),
                    "event_sensors": sorted(sensors["event"]),
                }
            )

        config["devices"] = devices
        n_households = len(
            {(d["metadata"]["household_id"], d["metadata"]["country"]) for d in devices}
        )
        print(f"Discovered {len(devices)} rooms across {n_households} households")
        return {}

    def _scan_csv(
        self,
        csv_path: Path,
        rooms: dict,
        kind: str,
        household_range: tuple[int, int] | None = None,
        time_range: tuple[int, int] | None = None,
    ):
        """Read a CSV to collect unique (household, country, room, sensor) combos."""
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            id_idx = header.index("id")
            country_idx = header.index("country")
            room_idx = header.index("room")
            sensor_idx = header.index("sensor")
            dt_idx = header.index("datetime_utc") if time_range else None

            for row in reader:
                if not _household_in_range(row[id_idx], household_range):
                    continue
                if time_range and not _ts_in_range(
                    _iso_to_ms(row[dt_idx]), time_range
                ):
                    continue
                key = (row[id_idx], row[country_idx], row[room_idx])
                rooms[key][kind].add(row[sensor_idx])

    def bulk_import(self, config: dict, conn: sqlite3.Connection) -> int:
        """Stream CSV files directly into the readings table."""
        data_dir = self._data_dir(config)
        household_range = self._household_range(config)
        time_range = self._time_range(config)
        total = 0

        # Import periodic data
        for csv_path in sorted(data_dir.glob("periodic_data_monthly_csv/*.csv")):
            count = self._import_periodic_csv(
                csv_path, conn, household_range, time_range
            )
            total += count
            print(f"  {csv_path.name}: {count} records")

        # Import event data
        event_csv = data_dir / "event_data" / "event_data.csv"
        if event_csv.exists():
            count = self._import_event_csv(
                event_csv, conn, household_range, time_range
            )
            total += count
            print(f"  event_data.csv: {count} records")

        return total

    def _import_periodic_csv(
        self,
        csv_path: Path,
        conn: sqlite3.Connection,
        household_range: tuple[int, int] | None = None,
        time_range: tuple[int, int] | None = None,
    ) -> int:
        count = 0
        batch: list[tuple[str, str, int, str]] = []

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            dt_idx = header.index("datetime_utc")
            id_idx = header.index("id")
            country_idx = header.index("country")
            room_idx = header.index("room")
            sensor_idx = header.index("sensor")
            min_idx = header.index("min_value")
            avg_idx = header.index("average_value")
            max_idx = header.index("max_value")

            for row in reader:
                if not _household_in_range(row[id_idx], household_range):
                    continue
                device = _device_id(row[id_idx], row[country_idx], row[room_idx])
                prop = row[sensor_idx]
                ts = _iso_to_ms(row[dt_idx])
                if not _ts_in_range(ts, time_range):
                    continue
                value = json.dumps(
                    {
                        "min_value": float(row[min_idx]),
                        "average_value": float(row[avg_idx]),
                        "max_value": float(row[max_idx]),
                    }
                )
                batch.append((device, prop, ts, value))

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        "INSERT INTO readings (device_id, property, ts, value) "
                        "VALUES (?, ?, ?, ?)",
                        batch,
                    )
                    count += len(batch)
                    batch.clear()

        if batch:
            conn.executemany(
                "INSERT INTO readings (device_id, property, ts, value) "
                "VALUES (?, ?, ?, ?)",
                batch,
            )
            count += len(batch)

        return count

    def _import_event_csv(
        self,
        csv_path: Path,
        conn: sqlite3.Connection,
        household_range: tuple[int, int] | None = None,
        time_range: tuple[int, int] | None = None,
    ) -> int:
        count = 0
        batch: list[tuple[str, str, int, str]] = []

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            dt_idx = header.index("datetime_utc")
            id_idx = header.index("id")
            country_idx = header.index("country")
            room_idx = header.index("room")
            sensor_idx = header.index("sensor")
            val_idx = header.index("value")

            for row in reader:
                if not _household_in_range(row[id_idx], household_range):
                    continue
                device = _device_id(row[id_idx], row[country_idx], row[room_idx])
                prop = row[sensor_idx]
                ts = _iso_to_ms(row[dt_idx])
                if not _ts_in_range(ts, time_range):
                    continue
                value = json.dumps({"value": row[val_idx]})
                batch.append((device, prop, ts, value))

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        "INSERT INTO readings (device_id, property, ts, value) "
                        "VALUES (?, ?, ?, ?)",
                        batch,
                    )
                    count += len(batch)
                    batch.clear()

        if batch:
            conn.executemany(
                "INSERT INTO readings (device_id, property, ts, value) "
                "VALUES (?, ?, ?, ?)",
                batch,
            )
            count += len(batch)

        return count

    def parse_readings(
        self, filepath: Path, device_id: str, prop: str
    ) -> list[tuple[str, str, int, str]]:
        raise NotImplementedError("shed_eu uses bulk_import")

    def generate_td(self, device: dict, replay_base_url: str) -> dict:
        return generate_room_td(device, replay_base_url)

    @staticmethod
    def _data_dir(config: dict) -> Path:
        return Path(config.get("data_dir", "providers/shed_eu"))

    @staticmethod
    def _household_range(config: dict) -> tuple[int, int] | None:
        range_str = config.get("household_range")
        if range_str is None:
            return None
        return _parse_household_range(str(range_str))

    @staticmethod
    def _time_range(config: dict) -> tuple[int, int] | None:
        from_str = config.get("from")
        to_str = config.get("to")
        if from_str is None and to_str is None:
            return None
        from_ms = _iso_to_ms(from_str) if from_str else 0
        to_ms = _iso_to_ms(to_str) if to_str else float("inf")
        return (from_ms, int(to_ms))


register_provider("shed_eu", ShedEuProvider)
