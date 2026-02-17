# Developer Guide

## Setup

Create and activate a virtual environment, then install the project with dev dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'
pip install tox
```

This installs the project in editable mode along with all dev tools (pytest, ruff, mypy, tox,
etc.) as defined in `pyproject.toml` under `[project.optional-dependencies] dev`.

> **Note:** The `[tool.hatch.build.targets.wheel] packages` setting must point to
> `["custom_components"]` (not `["custom_components/zoneminder"]`). This ensures the editable
> install adds `custom_components` to `sys.path` as `custom_components.zoneminder`, avoiding a
> namespace collision with the `zoneminder` package from zm-py.

### Optional: Install zm-py from a local checkout

If you're developing zm-py changes alongside this integration, install it from your local clone
instead of PyPI:

```bash
pip install -e ../ha-zm-py
```

This assumes the `ha-zm-py` repo is checked out as a sibling directory (the default layout in
the monorepo superproject). The `-e` flag means changes to your local zm-py are picked up
immediately without reinstalling.

To switch back to the PyPI version:

```bash
pip install 'zm-py==0.5.5.dev13'
```

## Running Tests

### Full QA suite (lint + type check + tests)

```bash
tox
```

### Tests only

```bash
tox -e py314
# or directly:
pytest tests -v
```

### Single test file or test

```bash
pytest tests/test_camera.py -v
pytest tests/test_sensor.py::test_specific_case -v
```

### Linting

```bash
tox -e lint
# or directly:
ruff check custom_components tests
ruff format --check custom_components tests
```

Auto-fix lint issues:

```bash
ruff check --fix custom_components tests
ruff format custom_components tests
```

### Type checking

```bash
tox -e typing
```

## Architecture Diagrams

Draw.io source files in `docs/` — open with [draw.io](https://app.diagrams.net/) or the
VS Code extension:

- [Component Architecture](docs/architecture.drawio) — stack overview: HA Core, ha-zoneminder, zm-py, ZoneMinder Server
- [Coordinator Data Flow](docs/data-flow.drawio) — read/write paths through ZmDataUpdateCoordinator
- [Config Flow](docs/config-flow.drawio) — user setup, YAML import, reconfigure, and options flow
