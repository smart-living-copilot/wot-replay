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
- **contextact_a4h** — Imports the ContextAct@A4H smart-apartment dataset (see [Data Sources](#data-sources)).
  The dataset is downloaded on demand from Mendeley. Its ~370 measured variables are grouped into one
  Thing Description per physical device (~159 devices), each exposing one property per underlying sensor
  (e.g. an environment node with `CO2_Cuisine`, `Temperature_Cuisine`, `Humidite_Cuisine`).

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

### contextact_a4h

```yaml
provider: contextact_a4h
data_dir: providers/contextact_a4h/data
download_url: https://data.mendeley.com/public-api/zip/fcj2hmz5kb/download/3
download: true                # set false to use a pre-downloaded copy in data_dir
months: [november]            # july and/or november (2016)
variant: change               # "change" (on value change) or "update" (every update)

# Optional finer time window:
# from: "2016-11-01T00:00:00Z"
# to: "2016-11-21T23:59:59Z"
```

The dataset (~220 MB extracted) is fetched once from Mendeley and cached under `data_dir`;
that directory is git-ignored. Subsequent builds reuse it.

## Usage

### Build fixtures

Build the fixture database for a provider:

```bash
wot-replay build smartlivingnext
wot-replay build shed_eu --force-overwrite
wot-replay build contextact_a4h          # downloads the dataset on first run
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

The **contextact_a4h** provider uses the ContextAct@A4H dataset, licensed under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/):

> Lago, P., Lang, F., Roncancio, C., Jiménez-Guarín, C., Mateescu, R., & Bonnefond, N. (2017).
> *The ContextAct@A4H Real-Life Dataset of Daily-Living Activities.* In Modeling and Using Context
> (CONTEXT 2017), LNCS vol. 10257. Springer, Cham. Dataset: https://doi.org/10.17632/fcj2hmz5kb.3

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
