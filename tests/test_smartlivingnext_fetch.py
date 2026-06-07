import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.smartlivingnext import fetch


class SmartLivingNextFetchTestCase(unittest.TestCase):
    def test_download_all_prints_record_count_and_timestamp_range(self) -> None:
        config = {
            "base_url": "https://example.test",
            "from": "2026-06-01T00:00:00Z",
            "to": "2026-06-30T23:59:59Z",
            "devices": [
                {
                    "id": "meter-1",
                    "title": "Real Smart Meter",
                    "properties": ["1-0%3A14.7.0%2A255"],
                }
            ],
        }
        records = [
            {"ts": 1780358400000, "1-0:14.7.0*255": 50.0},
            {"ts": 1780272000000, "1-0:14.7.0*255": 49.9},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with (
                patch.object(fetch, "download_property", return_value=records),
                patch.object(fetch.time, "sleep"),
                contextlib.redirect_stdout(output),
            ):
                manifest = fetch.download_all(config, Path(tmp))

        self.assertEqual(
            manifest,
            {
                "meter-1_1-0%3A14.7.0%2A255.json": {
                    "device_id": "meter-1",
                    "property": "1-0%3A14.7.0%2A255",
                }
            },
        )
        self.assertIn(
            "OK (2 records, min=2026-06-01T00:00:00Z, max=2026-06-02T00:00:00Z)",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
