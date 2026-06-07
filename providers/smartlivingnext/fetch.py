"""Download historical IoT data from the Smart Living Next API."""

from datetime import datetime, timezone
import json
import time
from pathlib import Path

import requests

from providers.db import parse_iso_to_ms


def download_property(
    base_url: str, device_id: str, prop: str, from_ms: int, to_ms: int
) -> list:
    url = f"{base_url}/api/history/{device_id}/{prop}"
    headers = {"Accept": "application/json"}
    resp = requests.get(
        url, params={"from": from_ms, "to": to_ms}, headers=headers, timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def _format_ts(ts_ms: int | float) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _record_range(records: list) -> str:
    timestamps = []
    for record in records:
        if not isinstance(record, dict):
            continue
        ts = record.get("ts")
        if ts is None:
            continue
        try:
            timestamps.append(float(ts))
        except (TypeError, ValueError):
            continue

    if not timestamps:
        return "no timestamps"

    return f"min={_format_ts(min(timestamps))}, max={_format_ts(max(timestamps))}"


def download_all(config: dict, tmp_dir: Path) -> dict[str, dict]:
    """Download all device properties, returns manifest mapping filename -> metadata."""
    base_url = config["base_url"].rstrip("/")
    from_ms = parse_iso_to_ms(config["from"])
    to_ms = parse_iso_to_ms(config["to"])

    devices = config["devices"]
    total = sum(len(d["properties"]) for d in devices)
    done = 0
    manifest = {}

    for device in devices:
        device_id = device["id"]
        title = device.get("title", device_id)

        for prop in device["properties"]:
            done += 1
            safe_prop = prop.replace("%20", "_").replace("/", "_")
            filename = f"{device_id}_{safe_prop}.json"
            out_file = tmp_dir / filename

            print(
                f"[{done}/{total}] {title} / {prop} ... ",
                end="",
                flush=True,
            )

            try:
                data = download_property(base_url, device_id, prop, from_ms, to_ms)
                with open(out_file, "w") as f:
                    json.dump(data, f)
                manifest[filename] = {"device_id": device_id, "property": prop}
                print(f"OK ({len(data)} records, {_record_range(data)})")
            except Exception as e:
                print(f"FAILED: {e}")

            time.sleep(0.5)

    return manifest
