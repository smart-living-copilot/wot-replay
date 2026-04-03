"""Provider framework for pluggable data sources.

Each provider knows how to fetch raw data, parse it into readings rows,
and generate WoT Thing Descriptions for its device types.
"""

import importlib
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path


class ProviderBase(ABC):
    @abstractmethod
    def fetch(self, config: dict, tmp_dir: Path) -> dict[str, dict]:
        """Download / read raw data into *tmp_dir*.

        Returns a manifest mapping filename -> {"device_id": ..., "property": ...}.
        Providers that use ``bulk_import`` may return an empty dict here.
        """

    @abstractmethod
    def parse_readings(
        self, filepath: Path, device_id: str, prop: str
    ) -> list[tuple[str, str, int, str]]:
        """Parse a single raw file into (device_id, property, ts, value_json) rows."""

    def bulk_import(self, config: dict, conn: sqlite3.Connection) -> int | None:
        """Directly import all readings into the DB, bypassing fetch/parse.

        Return the total row count, or ``None`` to fall back to the default
        manifest-based flow (fetch → parse_readings per file).
        """
        return None

    @abstractmethod
    def generate_td(self, device: dict, replay_base_url: str) -> dict:
        """Return a WoT Thing Description dict for *device*."""


_PROVIDERS: dict[str, type[ProviderBase]] = {}


def register_provider(name: str, cls: type[ProviderBase]):
    _PROVIDERS[name] = cls


def load_provider(name: str) -> ProviderBase:
    """Instantiate the provider registered under *name*, auto-importing if needed."""
    if name not in _PROVIDERS:
        importlib.import_module(f"providers.{name}")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(_PROVIDERS) or '(none)'}"
        )
    return cls()
