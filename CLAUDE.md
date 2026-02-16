# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ha-zoneminder is a standalone HACS-compatible custom integration for ZoneMinder in Home Assistant. It is extracted from the core HA integration (`homeassistant/components/zoneminder/`) to enable independent development, bug fixes, and modernization without being constrained by HA core's contribution process.

The integration uses the same `zoneminder` domain — when installed, it overrides the built-in core integration.

## Commands

### Setup
```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### Run all QA checks
```bash
tox
```

### Run tests only
```bash
tox -e py314
# or directly:
.venv/bin/pytest tests -v
```

### Run linting
```bash
tox -e lint
# or directly:
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

### Run type checking
```bash
tox -e typing
```

### Fix lint issues
```bash
.venv/bin/ruff check --fix custom_components tests
.venv/bin/ruff format custom_components tests
```

## Architecture

### Directory Layout
- `custom_components/zoneminder/` — the integration source (installed into HA's config dir)
- `tests/` — pytest test suite using `pytest-homeassistant-custom-component`

### Key Files
- `__init__.py` — YAML config schema, `async_setup()` entry point, ZM client creation
- `camera.py` — MJPEG camera entities (one per ZM monitor)
- `sensor.py` — Monitor status, event count, and run state sensors
- `switch.py` — Monitor function toggle (on/off state)
- `binary_sensor.py` — Server availability sensor
- `services.py` — `set_run_state` service
- `manifest.json` — Integration metadata (version, requirements, codeowners)

### Testing
- Tests use `pytest-homeassistant-custom-component` which provides the `hass` fixture and HA test infrastructure
- The `auto_enable_custom_integrations` autouse fixture in `conftest.py` ensures HA's loader picks up `custom_components/zoneminder/` instead of the built-in integration
- All patch targets use `custom_components.zoneminder.*` (not `homeassistant.components.zoneminder.*`)
- `from pytest_homeassistant_custom_component.common import async_fire_time_changed` replaces the core `tests.common` import
- 77 passing tests, 12 xfailed (known bugs documented with BUG-XX markers)

## Code Style

- **Ruff** for linting and formatting (line-length=100, target-version=py314)
- **mypy** for type checking
- Python 3.14+ only
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`

## Dependencies

- Runtime: `zm-py==0.5.5.dev5`, `homeassistant`
- Test: `pytest-homeassistant-custom-component` (pulls in HA core + test fixtures)
