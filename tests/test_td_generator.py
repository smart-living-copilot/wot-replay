import unittest

import td_generator


REPLAY_BASE_URL = "https://replay.example.test"


class TdGeneratorTestCase(unittest.TestCase):
    def test_power_smart_meter_types_include_power_contract(self) -> None:
        for device_type in ("smart_meter", "refit_smart_meter"):
            with self.subTest(device_type=device_type):
                device = {
                    "id": "wYDLYqAj21FIAoMm2zUz",
                    "type": device_type,
                    "provider": "smartlivingnext",
                    "title": "Smart Meter House 5",
                    "description": "Smart electricity meter measuring power consumption for a residential household",
                    "location": {"building": "REFIT", "house": "5"},
                    "metadata": {
                        "device_id": "wYDLYqAj21FIAoMm2zUz",
                        "manufacturer": "Unknown",
                        "model": "Smart Meter",
                        "dataset": "REFIT Electrical Load Measurements",
                    },
                    "properties": ["power"],
                }

                td = td_generator.generate_td(device, REPLAY_BASE_URL)

                self.assertEqual(td["metadata"], device["metadata"])
                self.assertEqual(td["properties"]["power"]["unit"], "W")
                self.assertEqual(
                    td["properties"]["power"]["forms"][0]["href"],
                    f"{REPLAY_BASE_URL}/api/history/{device['id']}/power/latest?includeTimestamps=true",
                )
                self.assertEqual(
                    td["actions"]["get_power_history"]["description"],
                    "Retrieve historical power consumption readings for a given time range",
                )

    def test_multisensor_td_preserves_metadata_and_original_action_wording(
        self,
    ) -> None:
        device = {
            "id": "5u7xysVleBeim3fcamZf",
            "type": "multisensor",
            "provider": "smartlivingnext",
            "title": "Kitchen Multisensor",
            "description": "Environmental multisensor monitoring temperature, humidity, CO2, light, and motion in the kitchen",
            "location": {
                "building": "Dudopark",
                "apartment": "1",
                "room": "Kitchen",
            },
            "metadata": {
                "device_id": "A81758FFFE0528A8",
                "manufacturer": "Unknown",
                "model": "Multisensor",
                "firmware_version": "1.0.0",
                "installation_date": "2024-01-01",
            },
            "properties": ["Temperature", "CO2", "Humidity", "Light", "Motion"],
        }

        td = td_generator.generate_td(device, REPLAY_BASE_URL)

        self.assertEqual(td["metadata"], device["metadata"])
        self.assertEqual(
            td["actions"]["get_temperature_history"]["description"],
            "Retrieve historical temperature readings for a given time range",
        )
        self.assertEqual(
            td["actions"]["get_co2_history"]["description"],
            "Retrieve historical CO2 readings for a given time range",
        )
        self.assertEqual(
            td["actions"]["get_light_history"]["description"],
            "Retrieve historical light level readings for a given time range",
        )
        self.assertEqual(
            td["actions"]["get_motion_history"]["description"],
            "Retrieve historical motion detection counts for a given time range",
        )
        self.assertEqual(td["properties"]["co2"]["unit"], "ppm")
        self.assertEqual(
            td["properties"]["motion"]["properties"]["value"]["type"], "integer"
        )

    def test_smart_plug_types_use_power_history_contract(self) -> None:
        for device_type in ("smart plug", "smart_plug"):
            with self.subTest(device_type=device_type):
                device = {
                    "id": "NeVdzhWbFWHjDoQIg5jf",
                    "type": device_type,
                    "provider": "smartlivingnext",
                    "title": "Kitchen Smart Plug 1",
                    "description": "Smart plug measuring power consumption in the kitchen",
                    "location": {
                        "building": "Dudopark",
                        "apartment": "1",
                        "room": "Kitchen",
                    },
                    "metadata": {
                        "device_id": "NeVdzhWbFWHjDoQIg5jf",
                        "manufacturer": "Unknown",
                        "model": "Smart Plug",
                    },
                    "properties": ["power"],
                }

                td = td_generator.generate_td(device, REPLAY_BASE_URL)

                self.assertEqual(td["metadata"], device["metadata"])
                self.assertEqual(td["properties"]["power"]["unit"], "W")
                self.assertEqual(
                    td["actions"]["get_power_history"]["forms"][0]["href"],
                    f"{REPLAY_BASE_URL}/api/history/{device['id']}/power{{?from,to}}",
                )

    def test_obis_smart_meter_td_exposes_only_configured_obis_properties(self) -> None:
        device = {
            "id": "F8QiOaIWy7tSP0WjqpIh",
            "type": "obis_smart_meter",
            "provider": "smartlivingnext",
            "title": "Real Smart Meter",
            "description": "Real smart electricity meter exposing OBIS measurements",
            "location": {"building": "Smart Living Next"},
            "metadata": {
                "device_id": "F8QiOaIWy7tSP0WjqpIh",
                "manufacturer": "Unknown",
                "model": "Smart Meter",
            },
            "properties": [
                "1-0%3A14.7.0%2A255",
                "1-0%3A16.7.0%2A255",
            ],
        }

        td = td_generator.generate_td(device, REPLAY_BASE_URL)

        self.assertEqual(td["metadata"], device["metadata"])
        self.assertNotIn("power", td["properties"])
        self.assertNotIn("get_power_history", td["actions"])
        self.assertIn("obis_1_0_14_7_0_255", td["properties"])
        self.assertEqual(td["properties"]["obis_1_0_14_7_0_255"]["unit"], "Hz")
        self.assertEqual(
            td["properties"]["obis_1_0_14_7_0_255"]["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/{device['id']}/1-0%3A14.7.0%2A255/latest?includeTimestamps=true",
        )
        self.assertEqual(
            td["actions"]["get_obis_1_0_16_7_0_255_history"]["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/{device['id']}/1-0%3A16.7.0%2A255{{?from,to}}",
        )
        self.assertIn(
            "1-0:14.7.0*255",
            td["properties"]["obis_1_0_14_7_0_255"]["properties"],
        )

    def test_thermostat_td_includes_metadata_and_state_schema(self) -> None:
        device = {
            "id": "Kj8hViu74Ewjrp1PH26G",
            "type": "thermostat",
            "provider": "smartlivingnext",
            "title": "Living Room Left Thermostat",
            "description": "Smart thermostat controlling heating in the Living Room (Left) with temperature setpoint, valve position, and various operating modes",
            "location": {
                "building": "Dudopark",
                "apartment": "1",
                "room": "Living Room",
            },
            "metadata": {
                "device_id": "Kj8hViu74Ewjrp1PH26G",
                "manufacturer": "Unknown",
                "model": "Thermostat",
                "firmware_version": "1.0.0",
                "installation_date": "2024-01-01",
            },
            "properties": ["DATA%2010"],
        }

        td = td_generator.generate_td(device, REPLAY_BASE_URL)

        self.assertEqual(td["metadata"], device["metadata"])
        self.assertEqual(td["properties"]["state"]["readOnly"], True)
        self.assertEqual(
            td["properties"]["state"]["properties"]["DATA 10"]["encoded"],
            "swsb-data10",
        )
        self.assertEqual(
            td["actions"]["get_state_history"]["forms"][0]["href"],
            f"{REPLAY_BASE_URL}/api/history/{device['id']}/DATA%2010{{?from,to}}",
        )


if __name__ == "__main__":
    unittest.main()
