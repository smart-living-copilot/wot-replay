"""Reusable WoT Thing Description building blocks shared by all providers."""

import uuid

# Stable namespace UUID for deterministic TD id generation from device IDs
NAMESPACE = uuid.UUID("e8f5a3b1-7c2d-4f9e-b6a1-d3e8f5a3b17c")

URI_VARIABLES = {
    "from": {
        "type": "integer",
        "description": "Start time (Unix timestamp in milliseconds) for the history data",
    },
    "to": {
        "type": "integer",
        "description": "End time (Unix timestamp in milliseconds) for the history data",
    },
}


def td_id(device_id: str) -> str:
    return f"urn:uuid:{uuid.uuid5(NAMESPACE, device_id)}"


def base_td(device: dict) -> dict:
    td = {
        "@context": "https://www.w3.org/2022/wot/td/v1.1",
        "id": td_id(device["id"]),
        "@type": "Thing",
        "title": device["title"],
        "description": device["description"],
        "location": device["location"],
        "security": "nosec_sc",
        "securityDefinitions": {"nosec_sc": {"scheme": "nosec"}},
    }
    metadata = device.get("metadata")
    if metadata is not None:
        td["metadata"] = metadata
    return td
