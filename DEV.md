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
> namespace collision with the `zoneminder` package from zm-py (the dev extra installs it for the
> live tests).

### Optional: Install aiozoneminder from a local checkout

The integration talks to ZoneMinder through aiozoneminder. If you're developing aiozoneminder
changes alongside this integration, install it from your local clone:

```bash
pip install -e ../aiozoneminder
```

The `-e` flag means changes to your local aiozoneminder are picked up immediately without
reinstalling. To switch back to the pinned version, `pip install -e '.[dev]'` again.

### Live tests against a real ZoneMinder

`tests/e2e/` sets the integration up against a running ZoneMinder (e.g. a zm-holodeck stack)
and compares it with what zm-py reads from the same server. Any zm-py can be the reference: the
pinned release, a local checkout with uncommitted edits, or any pip requirement. See [tests/e2e/README.md](tests/e2e/README.md).

```bash
./scripts/e2e-holodeck.sh --zm-py local --write
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
