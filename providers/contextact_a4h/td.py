"""WoT Thing Description generator for ContextAct@A4H devices.

One Thing per physical device; one property (plus a history action) per
underlying sensor variable.
"""

from providers.td_common import URI_VARIABLES, base_td


def _property_td(prop: dict, device_id: str, server_base: str) -> dict:
    sid = prop["sensor_id"]
    value_schema = {"type": prop["json_type"]}
    if prop.get("unit"):
        value_schema["unit"] = prop["unit"]
    td_prop = {
        "description": prop["description"],
        "type": "object",
        "readOnly": True,
        "forms": [
            {
                "op": ["readproperty"],
                "href": f"{server_base}/api/history/{device_id}/{sid}/latest?includeTimestamps=true",
                "contentType": "application/json",
            }
        ],
        "properties": {
            "ts": {
                "type": "integer",
                "description": "Unix timestamp in milliseconds",
            },
            "value": value_schema,
        },
    }
    if prop.get("unit"):
        td_prop["unit"] = prop["unit"]
    return td_prop


def _history_action(prop: dict, device_id: str, server_base: str) -> dict:
    sid = prop["sensor_id"]
    value_schema = {"type": prop["json_type"]}
    if prop.get("unit"):
        value_schema["unit"] = prop["unit"]
    action = {
        "description": f"Retrieve historical {prop['description']} readings for a given time range",
        "safe": True,
        "idempotent": True,
        "forms": [
            {
                "op": "invokeaction",
                "href": f"{server_base}/api/history/{device_id}/{sid}{{?from,to}}",
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
                    "value": value_schema,
                },
            },
        },
        "uriVariables": URI_VARIABLES,
    }
    if prop.get("unit"):
        action["unit"] = prop["unit"]
    return action


def generate_device_td(device: dict, replay_base_url: str) -> dict:
    device_id = device["id"]
    server_base = replay_base_url.rstrip("/")
    td = base_td(device)

    td_properties = {}
    td_actions = {}
    for prop in device["properties"]:
        sid = prop["sensor_id"]
        td_properties[sid] = _property_td(prop, device_id, server_base)
        td_actions[f"get_{sid}_history"] = _history_action(prop, device_id, server_base)

    td["properties"] = td_properties
    td["actions"] = td_actions
    return td
