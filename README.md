# Data Replay

`data-replay` serves offline versions of historical IoT data endpoints.
It replays a captured fixture window on a loop and exposes WoT Thing Descriptions
that point at the local replay server.

## Providers

Data is imported through provider plugins in `providers/`. Each provider handles
its own data format, device discovery, and Thing Description generation.

- **smartlivingnext** — Downloads data from the Smart Living Next API (REFIT, Dudopark).
- **shed_eu** — Imports household sensor data from local CSV files. One Thing Description
  is generated per room, with properties named by sensor type (e.g. `temperature`, `co2`).

## Files

- `build_fixtures.py` — Downloads/imports data and builds `fixtures.db`
- `replay_server.py` — FastAPI server that replays history and `/latest` responses
- `td_generator.py` — Routes to provider-specific TD generators
- `providers/` — Provider plugins (data import + TD generation)

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

## Build Fixtures

Build the fixture database for a provider:

```bash
python build_fixtures.py -p shed_eu --force-overwrite
python build_fixtures.py -p smartlivingnext --force-overwrite
```

You can also point to a custom sources file:

```bash
python build_fixtures.py -s my_sources.yaml -o my.db
```

The generated `fixtures.db` is ignored in git.

## Run

Run the service with Docker Compose from the repo root:

```bash
docker compose up data-replay
```

The service reads its database path and public base URL from environment
variables configured in Compose.

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
