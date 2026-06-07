import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from providers.contextact_a4h import ContextActA4HProvider
from providers.contextact_a4h.catalog import (
    Variable,
    build_devices,
    device_key,
    sensor_to_device,
)
from providers.contextact_a4h.td import generate_device_td
from providers.db import create_schema

REPLAY_BASE_URL = "https://replay.example.test"


def _vars():
    # A small, representative slice of the real catalog.
    return [
        Variable(
            "Puissance_Frigo", "Power Sensor", "Fridge Power", "Double", "W", "Kitchen"
        ),
        Variable(
            "Tension_Frigo",
            "Tension Sensor",
            "Fridge Voltage",
            "Double",
            "V",
            "Kitchen",
        ),
        Variable(
            "CO2_Cuisine", "Carbon Dioxide Meter", "CO2 Kitchen", "", "ppm", "Kitchen"
        ),
        Variable(
            "Temperature_Cuisine",
            "Temperature Sensor",
            "Temp Kitchen",
            "Double",
            "°C",
            "Kitchen",
        ),
        Variable(
            "C3",
            "Contact Sensor",
            "Fridge Door Opening",
            "Binary",
            "OPEN-CLOSED",
            "Kitchen",
        ),
        Variable(
            "current_activity", "ACTIVITY", "Self-annotated Activity", "String", "", ""
        ),
    ]


class CatalogTestCase(unittest.TestCase):
    def test_device_key_groups_and_excludes(self):
        self.assertEqual(device_key("Puissance_Frigo"), "meter:Frigo")
        self.assertEqual(device_key("Tension_Frigo"), "meter:Frigo")
        self.assertEqual(device_key("CO2_Cuisine"), "env:Cuisine")
        self.assertEqual(
            device_key("Eau_Chaude_Douche_Total"), "water:Eau_Chaude_Douche"
        )
        self.assertEqual(device_key("C3"), "single:C3")
        self.assertIsNone(device_key("current_activity"))

    def test_build_devices_groups_variables(self):
        devices = build_devices(_vars())
        by_id = {d["id"]: d for d in devices}

        # Fridge meter groups power + voltage into one Thing.
        meter = by_id["a4h-meter-frigo"]
        self.assertEqual(meter["title"], "Fridge Energy Meter")
        self.assertEqual(meter["location"], {"room": "Kitchen"})
        self.assertEqual(
            {p["sensor_id"] for p in meter["properties"]},
            {"Puissance_Frigo", "Tension_Frigo"},
        )

        # Environment node groups CO2 + temperature.
        env = by_id["a4h-env-cuisine"]
        self.assertEqual(
            {p["sensor_id"] for p in env["properties"]},
            {"CO2_Cuisine", "Temperature_Cuisine"},
        )
        # Blank "Variable Type" on a CO2 meter still resolves to numeric.
        co2 = next(p for p in env["properties"] if p["sensor_id"] == "CO2_Cuisine")
        self.assertEqual(co2["json_type"], "number")

        # Contact sensor is its own single-property device.
        self.assertEqual(len(by_id["a4h-single-c3"]["properties"]), 1)

        # current_activity is excluded entirely.
        self.assertNotIn("current_activity", sensor_to_device(devices))

    def test_present_ids_filter(self):
        devices = build_devices(_vars(), present_ids={"CO2_Cuisine"})
        ids = {d["id"] for d in devices}
        self.assertEqual(ids, {"a4h-env-cuisine"})
        self.assertEqual(len(devices[0]["properties"]), 1)


class BulkImportTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        # README marker lets _ensure_data treat the dir as pre-downloaded.
        (self.data_dir / "README.txt").write_text("marker")
        meas = self.data_dir / "sensor measurements"
        meas.mkdir()
        (meas / "November_All_Change.csv.log").write_text(
            '"2016-11-14 17:57:07,174";"CO2_Cuisine";"512.5"\n'
            '"2016-11-14 17:58:00,000";"C3";"OPEN"\n'
            '"2016-11-20 10:00:00,000";"CO2_Cuisine";"480"\n'
        )
        self.provider = ContextActA4HProvider()
        self.devices = build_devices(_vars())

    def tearDown(self):
        self._tmp.cleanup()

    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        return conn

    def test_bulk_import_parses_values(self):
        config = {
            "data_dir": str(self.data_dir),
            "download": False,
            "devices": self.devices,
        }
        conn = self._conn()
        total = self.provider.bulk_import(config, conn)
        self.assertEqual(total, 3)

        co2 = conn.execute(
            "SELECT value FROM readings WHERE device_id='a4h-env-cuisine' AND property='CO2_Cuisine' ORDER BY ts"
        ).fetchall()
        self.assertEqual(json.loads(co2[0]["value"]), {"value": 512.5})

        contact = conn.execute(
            "SELECT value FROM readings WHERE property='C3'"
        ).fetchone()
        self.assertEqual(json.loads(contact["value"]), {"value": "OPEN"})
        conn.close()

    def test_bulk_import_respects_time_range(self):
        config = {
            "data_dir": str(self.data_dir),
            "download": False,
            "devices": self.devices,
            "from": "2016-11-14T00:00:00Z",
            "to": "2016-11-15T00:00:00Z",
        }
        conn = self._conn()
        total = self.provider.bulk_import(config, conn)
        self.assertEqual(total, 2)  # the Nov 20 row is excluded
        conn.close()


class TdTestCase(unittest.TestCase):
    def test_generate_td_and_dispatch(self):
        device = next(d for d in build_devices(_vars()) if d["id"] == "a4h-env-cuisine")
        device["provider"] = "contextact_a4h"

        td = generate_device_td(device, REPLAY_BASE_URL)
        self.assertEqual(td["@context"], "https://www.w3.org/2022/wot/td/v1.1")
        self.assertIn("CO2_Cuisine", td["properties"])
        self.assertEqual(
            td["properties"]["CO2_Cuisine"]["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/a4h-env-cuisine/CO2_Cuisine/latest?includeTimestamps=true",
        )
        self.assertIn("get_CO2_Cuisine_history", td["actions"])

        # Routes correctly through the central dispatcher.
        import td_generator

        td2 = td_generator.generate_td(device, REPLAY_BASE_URL)
        self.assertEqual(td2["title"], td["title"])


if __name__ == "__main__":
    unittest.main()
