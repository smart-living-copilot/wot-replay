"""Smart Living Next provider — fetches IoT data from the SLN API."""

import json
from pathlib import Path

from providers import ProviderBase, register_provider
from providers.smartlivingnext.fetch import download_all
from providers.smartlivingnext.td import GENERATORS


class SmartLivingNextProvider(ProviderBase):
    def fetch(self, config: dict, tmp_dir: Path) -> dict[str, dict]:
        return download_all(config, tmp_dir)

    def parse_readings(
        self, filepath: Path, device_id: str, prop: str
    ) -> list[tuple[str, str, int, str]]:
        with open(filepath) as f:
            records = json.load(f)

        if not isinstance(records, list):
            return []

        rows = []
        for record in records:
            ts = record.get("ts")
            if ts is None:
                continue
            value_obj = {k: v for k, v in record.items() if k != "ts"}
            rows.append((device_id, prop, int(ts), json.dumps(value_obj)))
        return rows

    def generate_td(self, device: dict, replay_base_url: str) -> dict:
        device_type = device["type"]
        generator = GENERATORS.get(device_type)
        if generator is None:
            raise ValueError(f"Unknown device type: {device_type}")
        return generator(device, replay_base_url)


register_provider("smartlivingnext", SmartLivingNextProvider)
