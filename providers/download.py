"""Shared helper to optionally download and unpack a dataset archive.

Some datasets are distributed as a downloadable archive (e.g. a Mendeley
dataset zip) rather than checked into the repository. Providers for those
datasets can call :func:`ensure_dataset` during ``fetch`` to obtain the data
on demand.

The download is *optional*: if the data already exists locally (detected via
``marker``), nothing is fetched. This keeps repeat builds fast and lets users
point ``data_dir`` at a pre-downloaded copy with no network access at all.
"""

import shutil
import tempfile
import zipfile
from pathlib import Path

CHUNK_SIZE = 1 << 20  # 1 MiB


def _has_data(data_dir: Path, marker: str | None) -> bool:
    """True if *data_dir* already holds the dataset.

    With a ``marker`` (a path relative to ``data_dir``) we check for that
    specific file/dir; otherwise any non-empty directory counts.
    """
    if not data_dir.exists():
        return False
    if marker:
        return (data_dir / marker).exists()
    return any(data_dir.iterdir())


def _download(url: str, dest: Path) -> None:
    """Stream *url* to *dest*, showing coarse progress."""
    import requests

    print(f"Downloading {url} ...")
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(f"\r  {done >> 20} / {total >> 20} MiB ({pct}%)", end="")
        print()


def _extract_zip(archive: Path, data_dir: Path) -> None:
    print(f"Extracting {archive.name} -> {data_dir} ...")
    data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(data_dir)


def ensure_dataset(
    data_dir: Path | str,
    download_url: str | None,
    *,
    marker: str | None = None,
    download: bool = True,
    force: bool = False,
) -> Path:
    """Ensure the dataset is available under *data_dir*, downloading if needed.

    Parameters
    ----------
    data_dir:
        Directory the data should live in.
    download_url:
        URL of a ``.zip`` archive to fetch. If ``None``, no download is
        attempted.
    marker:
        Path (relative to ``data_dir``) used to detect an existing copy.
    download:
        Set ``False`` to disable downloading entirely (offline / pre-fetched).
    force:
        Re-download and re-extract even if the data already exists.

    Returns the resolved ``data_dir``. Raises ``FileNotFoundError`` if the data
    is missing and cannot be downloaded.
    """
    data_dir = Path(data_dir)

    if not force and _has_data(data_dir, marker):
        print(f"Using existing dataset at {data_dir}")
        return data_dir

    if not download or not download_url:
        raise FileNotFoundError(
            f"No dataset found at {data_dir} and downloading is disabled. "
            "Set 'download_url' (and 'download: true') in sources.yaml, or "
            "place the data there manually."
        )

    with tempfile.TemporaryDirectory(prefix="wot-replay-dl-") as tmp:
        archive = Path(tmp) / "dataset.zip"
        _download(download_url, archive)
        if force and data_dir.exists():
            shutil.rmtree(data_dir)
        _extract_zip(archive, data_dir)

    return data_dir
