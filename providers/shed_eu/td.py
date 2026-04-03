"""WoT Thing Description generator for SHED EU rooms."""

from providers.td_common import URI_VARIABLES, base_td

PERIODIC_SENSOR_META = {
    "temperature": {"desc": "Room temperature", "unit": "°C"},
    "co2": {"desc": "CO2 concentration", "unit": "ppm"},
    "humidity": {"desc": "Relative humidity", "unit": "%"},
    "ambient_light": {"desc": "Ambient light level", "unit": "lx"},
    "voc": {"desc": "Volatile organic compounds level", "unit": "ppb"},
}

EVENT_SENSOR_META = {
    "movement": {"desc": "Motion detection event", "value_type": "string"},
    "door": {"desc": "Door open/close event", "value_type": "string"},
}


def _periodic_property(device_id: str, sensor: str, server_base: str) -> dict:
    meta = PERIODIC_SENSOR_META.get(sensor, {"desc": sensor, "unit": ""})
    return {
        "description": meta["desc"],
        "type": "object",
        "unit": meta["unit"],
        "readOnly": True,
        "forms": [
            {
                "op": ["readproperty"],
                "href": f"{server_base}/api/history/{device_id}/{sensor}/latest?includeTimestamps=true",
                "contentType": "application/json",
            }
        ],
        "properties": {
            "ts": {
                "type": "integer",
                "description": "Unix timestamp in milliseconds",
            },
            "min_value": {"type": "number", "unit": meta["unit"]},
            "average_value": {"type": "number", "unit": meta["unit"]},
            "max_value": {"type": "number", "unit": meta["unit"]},
        },
    }


def _event_property(device_id: str, sensor: str, server_base: str) -> dict:
    meta = EVENT_SENSOR_META.get(sensor, {"desc": sensor, "value_type": "string"})
    return {
        "description": meta["desc"],
        "type": "object",
        "readOnly": True,
        "forms": [
            {
                "op": ["readproperty"],
                "href": f"{server_base}/api/history/{device_id}/{sensor}/latest?includeTimestamps=true",
                "contentType": "application/json",
            }
        ],
        "properties": {
            "ts": {
                "type": "integer",
                "description": "Unix timestamp in milliseconds",
            },
            "value": {"type": meta["value_type"]},
        },
    }


def _history_action(
    device_id: str,
    sensor: str,
    description: str,
    output_props: dict,
    server_base: str,
) -> dict:
    return {
        "description": description,
        "safe": True,
        "idempotent": True,
        "forms": [
            {
                "op": "invokeaction",
                "href": f"{server_base}/api/history/{device_id}/{sensor}{{?from,to}}",
                "contentType": "application/json",
                "htv:methodName": "GET",
            }
        ],
        "output": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ts": {
                        "type": "integer",
                        "description": "Unix timestamp in milliseconds",
                    },
                    **output_props,
                },
            },
        },
        "uriVariables": URI_VARIABLES,
    }


def generate_room_td(device: dict, replay_base_url: str) -> dict:
    device_id = device["id"]
    server_base = replay_base_url.rstrip("/")
    td = base_td(device)

    td_properties = {}
    td_actions = {}

    for sensor in device.get("periodic_sensors", []):
        meta = PERIODIC_SENSOR_META.get(sensor, {"desc": sensor, "unit": ""})

        td_properties[sensor] = _periodic_property(device_id, sensor, server_base)
        td_actions[f"get_{sensor}_history"] = _history_action(
            device_id,
            sensor,
            f"Retrieve historical {sensor} readings",
            {
                "min_value": {"type": "number", "unit": meta["unit"]},
                "average_value": {"type": "number", "unit": meta["unit"]},
                "max_value": {"type": "number", "unit": meta["unit"]},
            },
            server_base,
        )

    for sensor in device.get("event_sensors", []):
        meta = EVENT_SENSOR_META.get(sensor, {"desc": sensor, "value_type": "string"})

        td_properties[sensor] = _event_property(device_id, sensor, server_base)
        td_actions[f"get_{sensor}_history"] = _history_action(
            device_id,
            sensor,
            f"Retrieve historical {sensor} events",
            {"value": {"type": meta["value_type"]}},
            server_base,
        )

    td["properties"] = td_properties
    td["actions"] = td_actions
    return td
