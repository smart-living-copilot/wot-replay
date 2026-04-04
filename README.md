# WoT Replay

`wot-replay` serves offline versions of historical IoT data endpoints.
It replays a captured fixture window on a loop and exposes WoT Thing Descriptions
that point at the local replay server.

## Providers

Data is imported through provider plugins in `providers/`. Each provider handles
its own data format, device discovery, and Thing Description generation.

- **smartlivingnext** — Downloads data from the Smart Living Next API (REFIT, Dudopark).
- **shed_eu** — Imports household sensor data from the SHED-EU dataset (see [Data Sources](#data-sources)).
  One Thing Description is generated per room, with properties named by sensor type (e.g. `temperature`, `co2`).

## Configuration

Each provider has a `sources.yaml` in its directory (e.g. `providers/shed_eu/sources.yaml`).

### shed_eu

```yaml
provider: shed_eu
data_dir: providers/shed_eu

# Restrict to a range of household IDs (inclusive). Omit to load all.
# household_range: "1-10"

# Restrict to a time window. Omit to load all data.
# from: "2023-05-01T00:00:00Z"
# to: "2023-05-31T23:59:59Z"
```

### smartlivingnext

```yaml
provider: smartlivingnext
from: "2024-12-01T00:00:00Z"
to: "2024-12-31T23:59:59Z"
```

## Usage

### Build fixtures

Build the fixture database for a provider:

```bash
wot-replay build smartlivingnext
wot-replay build shed_eu --force-overwrite
```

Custom sources file and output path:

```bash
wot-replay build smartlivingnext -s my_sources.yaml -o my.db
```

### Serve

Start the replay server:

```bash
wot-replay serve
```

Options:

```bash
wot-replay serve --db fixtures.db --port 9000 --base-url http://localhost:9000
```

### Install

From GitHub:

```bash
pip install git+https://github.com/smart-living-copilot/wot-replay.git
```

For local development:

```bash
pip install -e .
```

## Data Sources

The **shed_eu** provider uses the SHED-EU dataset, licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/):

> Winterberger, S., An, D., Biallas, M., & Paice, A. (2024).
> *Smart Home environment data across 4 European countries* [Dataset].
> Zenodo. https://doi.org/10.5281/zenodo.14243471

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
