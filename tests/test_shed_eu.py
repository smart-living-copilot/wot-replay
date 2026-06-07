import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from providers.shed_eu import ShedEuProvider
from providers.shed_eu.td import generate_room_td
from providers.db import create_schema


REPLAY_BASE_URL = "https://replay.example.test"


def _write_csv(path: Path, header: list[str], rows: list[list[str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


class ShedEuFetchTestCase(unittest.TestCase):
    """Test that fetch() discovers rooms from CSV data."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.provider = ShedEuProvider()

    def tearDown(self):
        self._tmp.cleanup()

    def test_fetch_discovers_rooms_and_sensors(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-16T10:33:34.167000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24.8",
                    "24.8",
                    "24.8",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "5",
                    "CH",
                    "bedroom",
                    "co2",
                    "400",
                    "420",
                    "440",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "7",
                    "DK",
                    "kitchen",
                    "humidity",
                    "50",
                    "55",
                    "60",
                ],
            ],
        )
        _write_csv(
            self.data_dir / "event_data" / "event_data.csv",
            ["datetime_utc", "id", "country", "room", "sensor", "value"],
            [
                [
                    "2023-05-30T13:30:02.403000000",
                    "7",
                    "DK",
                    "kitchen",
                    "movement",
                    "on",
                ],
            ],
        )

        config = {"data_dir": str(self.data_dir)}
        self.provider.fetch(config, Path(self._tmp.name) / "unused")

        devices = config["devices"]
        # 2 rooms: bedroom (household 5 CH), kitchen (household 7 DK)
        self.assertEqual(len(devices), 2)

        # Bedroom in household 5 CH
        bedroom = next(d for d in devices if d["id"] == "shed-eu-5-CH-bedroom")
        self.assertEqual(bedroom["location"]["country"], "CH")
        self.assertEqual(bedroom["location"]["room"], "bedroom")
        self.assertIn("temperature", bedroom["periodic_sensors"])
        self.assertIn("co2", bedroom["periodic_sensors"])
        self.assertEqual(bedroom["event_sensors"], [])

        # Kitchen in household 7 DK
        kitchen = next(d for d in devices if d["id"] == "shed-eu-7-DK-kitchen")
        self.assertIn("humidity", kitchen["periodic_sensors"])
        self.assertIn("movement", kitchen["event_sensors"])

    def test_fetch_with_household_range(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-16T10:33:34.167000000",
                    "3",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24.8",
                    "24.8",
                    "24.8",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "5",
                    "CH",
                    "bedroom",
                    "co2",
                    "400",
                    "420",
                    "440",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "7",
                    "DK",
                    "kitchen",
                    "humidity",
                    "50",
                    "55",
                    "60",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "12",
                    "DK",
                    "kitchen",
                    "humidity",
                    "50",
                    "55",
                    "60",
                ],
            ],
        )

        config = {"data_dir": str(self.data_dir), "household_range": "3-7"}
        self.provider.fetch(config, Path(self._tmp.name) / "unused")

        device_ids = {d["id"] for d in config["devices"]}
        self.assertIn("shed-eu-3-CH-bedroom", device_ids)
        self.assertIn("shed-eu-5-CH-bedroom", device_ids)
        self.assertIn("shed-eu-7-DK-kitchen", device_ids)
        self.assertNotIn("shed-eu-12-DK-kitchen", device_ids)

    def test_fetch_with_time_range(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-10T10:00:00.000000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24",
                    "24",
                    "24",
                ],
                [
                    "2023-05-20T10:00:00.000000000",
                    "5",
                    "CH",
                    "bedroom",
                    "co2",
                    "400",
                    "420",
                    "440",
                ],
            ],
        )

        config = {
            "data_dir": str(self.data_dir),
            "from": "2023-05-15T00:00:00Z",
            "to": "2023-05-31T23:59:59Z",
        }
        self.provider.fetch(config, Path(self._tmp.name) / "unused")

        devices = config["devices"]
        self.assertEqual(len(devices), 1)
        # Only the co2 sensor (May 20) is in range, not temperature (May 10)
        self.assertIn("co2", devices[0]["periodic_sensors"])
        self.assertNotIn("temperature", devices[0]["periodic_sensors"])


class ShedEuBulkImportTestCase(unittest.TestCase):
    """Test that bulk_import() correctly inserts readings into the DB."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.provider = ShedEuProvider()

    def tearDown(self):
        self._tmp.cleanup()

    def test_bulk_import_inserts_periodic_and_event_rows(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-16T10:33:34.167000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24.8",
                    "24.8",
                    "24.8",
                ],
                [
                    "2023-05-16T10:38:36.475000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24.9",
                    "24.9",
                    "24.9",
                ],
            ],
        )
        _write_csv(
            self.data_dir / "event_data" / "event_data.csv",
            ["datetime_utc", "id", "country", "room", "sensor", "value"],
            [
                [
                    "2023-05-30T13:30:02.403000000",
                    "7",
                    "DK",
                    "kitchen",
                    "movement",
                    "on",
                ],
            ],
        )

        config = {"data_dir": str(self.data_dir)}
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        total = self.provider.bulk_import(config, conn)
        self.assertEqual(total, 3)

        # Check periodic rows — device_id now includes room
        rows = conn.execute(
            "SELECT * FROM readings WHERE device_id = 'shed-eu-5-CH-bedroom' ORDER BY ts"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["property"], "temperature")
        value = json.loads(rows[0]["value"])
        self.assertAlmostEqual(value["average_value"], 24.8)

        # Check event row
        rows = conn.execute(
            "SELECT * FROM readings WHERE device_id = 'shed-eu-7-DK-kitchen'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["property"], "movement")
        value = json.loads(rows[0]["value"])
        self.assertEqual(value["value"], "on")

        conn.close()

    def test_bulk_import_respects_household_range(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-16T10:33:34.167000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24.8",
                    "24.8",
                    "24.8",
                ],
                [
                    "2023-05-16T10:33:34.176000000",
                    "7",
                    "DK",
                    "kitchen",
                    "humidity",
                    "50",
                    "55",
                    "60",
                ],
            ],
        )

        config = {"data_dir": str(self.data_dir), "household_range": "5-5"}
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        total = self.provider.bulk_import(config, conn)
        self.assertEqual(total, 1)

        rows = conn.execute("SELECT device_id FROM readings").fetchall()
        self.assertEqual(rows[0]["device_id"], "shed-eu-5-CH-bedroom")

        conn.close()

    def test_bulk_import_respects_time_range(self):
        _write_csv(
            self.data_dir / "periodic_data_monthly_csv" / "periodic_data_2023_05.csv",
            [
                "datetime_utc",
                "id",
                "country",
                "room",
                "sensor",
                "min_value",
                "average_value",
                "max_value",
            ],
            [
                [
                    "2023-05-10T10:00:00.000000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "24",
                    "24",
                    "24",
                ],
                [
                    "2023-05-20T10:00:00.000000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "25",
                    "25",
                    "25",
                ],
                [
                    "2023-05-25T10:00:00.000000000",
                    "5",
                    "CH",
                    "bedroom",
                    "temperature",
                    "26",
                    "26",
                    "26",
                ],
            ],
        )

        config = {
            "data_dir": str(self.data_dir),
            "from": "2023-05-15T00:00:00Z",
            "to": "2023-05-22T00:00:00Z",
        }
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)

        total = self.provider.bulk_import(config, conn)
        self.assertEqual(total, 1)

        rows = conn.execute("SELECT * FROM readings").fetchall()
        value = json.loads(rows[0]["value"])
        self.assertAlmostEqual(value["average_value"], 25.0)

        conn.close()


class ShedEuTdTestCase(unittest.TestCase):
    """Test TD generation for a SHED EU room."""

    def test_room_td_has_periodic_and_event_properties(self):
        device = {
            "id": "shed-eu-7-DK-kitchen",
            "type": "room",
            "provider": "shed_eu",
            "title": "Kitchen — Household 7 (DK)",
            "description": "Room 'kitchen' in SHED EU household 7, DK",
            "location": {"country": "DK", "household_id": "7", "room": "kitchen"},
            "metadata": {"household_id": "7", "country": "DK", "room": "kitchen"},
            "periodic_sensors": ["co2", "temperature"],
            "event_sensors": ["movement"],
        }

        td = generate_room_td(device, REPLAY_BASE_URL)

        # Basic TD structure
        self.assertEqual(td["title"], "Kitchen — Household 7 (DK)")
        self.assertEqual(td["@context"], "https://www.w3.org/2022/wot/td/v1.1")

        # Periodic property — key is just sensor name
        temp = td["properties"]["temperature"]
        self.assertEqual(temp["unit"], "°C")
        self.assertTrue(temp["readOnly"])
        self.assertIn("min_value", temp["properties"])
        self.assertIn("average_value", temp["properties"])
        self.assertIn("max_value", temp["properties"])
        self.assertEqual(
            temp["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/shed-eu-7-DK-kitchen/temperature/latest?includeTimestamps=true",
        )

        # Event property
        movement = td["properties"]["movement"]
        self.assertIn("value", movement["properties"])
        self.assertEqual(
            movement["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/shed-eu-7-DK-kitchen/movement/latest?includeTimestamps=true",
        )

        # History actions
        self.assertIn("get_temperature_history", td["actions"])
        self.assertIn("get_movement_history", td["actions"])

        action = td["actions"]["get_temperature_history"]
        self.assertEqual(
            action["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/shed-eu-7-DK-kitchen/temperature{{?from,to}}",
        )
        self.assertIn("uriVariables", action)

    def test_td_generation_via_provider_dispatch(self):
        """Test that td_generator.generate_td routes to shed_eu correctly."""
        import td_generator

        device = {
            "id": "shed-eu-5-CH-bedroom",
            "type": "room",
            "provider": "shed_eu",
            "title": "Bedroom — Household 5 (CH)",
            "description": "Room 'bedroom' in SHED EU household 5, CH",
            "location": {"country": "CH", "household_id": "5", "room": "bedroom"},
            "metadata": {"household_id": "5", "country": "CH", "room": "bedroom"},
            "periodic_sensors": ["temperature"],
            "event_sensors": [],
        }

        td = td_generator.generate_td(device, REPLAY_BASE_URL)
        self.assertEqual(td["title"], "Bedroom — Household 5 (CH)")
        self.assertIn("temperature", td["properties"])


if __name__ == "__main__":
    unittest.main()
