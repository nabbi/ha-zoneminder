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
- `docs/` — architecture diagrams (`.drawio`) and usage guide

### Key Files
- `__init__.py` — YAML config schema, `async_setup()` entry point, ZM client creation
- `config_flow.py` — Config flow (user/import/reconfigure steps) and options flow
- `coordinator.py` — `ZmDataUpdateCoordinator` shared by all entities per server
- `models.py` — `ZmEntryData` dataclass for per-entry runtime data
- `camera.py` — MJPEG camera entities (one per ZM monitor)
- `select.py` — Run state select + Capturing/Analysing/Recording selects (ZM 1.37+)
- `sensor.py` — Monitor status, event count, and run state sensors
- `switch.py` — Force alarm switch + legacy function toggle (ZM < 1.37)
- `binary_sensor.py` — Server availability sensor
- `services.py` — `set_run_state` service
- `manifest.json` — Integration metadata (version, requirements, codeowners)

### Testing
- Tests use `pytest-homeassistant-custom-component` which provides the `hass` fixture and HA test infrastructure
- The `auto_enable_custom_integrations` autouse fixture in `conftest.py` ensures HA's loader picks up `custom_components/zoneminder/` instead of the built-in integration
- All patch targets use `custom_components.zoneminder.*` (not `homeassistant.components.zoneminder.*`)
- `from pytest_homeassistant_custom_component.common import async_fire_time_changed` replaces the core `tests.common` import
- 162 passing tests, 1 xfailed (BUG-08: PTZ control not exposed)

## Code Style

- **Ruff** for linting and formatting (line-length=100, target-version=py314)
- **mypy** for type checking
- Python 3.14+ only
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`

## Workflow

Before committing, always run **all** QA checks and confirm they pass:
1. `.venv/bin/ruff check custom_components tests` — linting
2. `.venv/bin/ruff format --check custom_components tests` — formatting
3. `.venv/bin/mypy custom_components` — type checking
4. `.venv/bin/pytest tests -v` — tests

Do not ask the user to commit until all four pass. Fix any failures first.

## Dependencies

- Runtime: `zm-py==0.5.5.dev13`, `homeassistant`
- Test: `pytest-homeassistant-custom-component` (pulls in HA core + test fixtures)

## Bug & Feature Tracking

Cross-references `docs/BUGS-ha-zm_zm-py.md` in the superproject. Items below track
ha-zoneminder–specific status.

### Resolved

| ID | Description | Commit |
|----|-------------|--------|
| BUG-01 | `RequestException` during login didn't set `success = False` | `63c44e2` |
| BUG-02 | No DataUpdateCoordinator — excessive API calls | `8285e06` |
| BUG-03 | `Monitor.function` getter calls `update_monitor()` — hidden I/O | `dc3a06d` |
| BUG-04 | `Monitor.is_available` calls `update_monitor()` — redundant I/O | `dc3a06d` |
| BUG-05 | No `unique_id` on any entity | `cb74a1a` |
| BUG-06 | `get_monitors()` called 3x — separate object trees | `242ad7e` |
| BUG-07 | `LoginError` not caught during setup | `f29dbb9` |
| BUG-09 | No config flow (YAML-only) | `fdd38c5` |
| BUG-10 | No `DeviceInfo` — entities not grouped | `eee8c6b` |
| BUG-12 | zm-py exceptions unhandled across integration | `0fda937` |
| BUG-13 | `get_run_states()` unused; no select entity for run state control | `eb8e1a1` |
| — | `set_run_state` service missing `id` field in services.yaml/strings.json | `63c44e2` |

### Deferred — Feature Requests

| ID | Description | Reason |
|----|-------------|--------|
| BUG-08 | PTZ control not exposed | No PTZ test hardware available to validate. zm-py support is complete; HA layer needs ONVIF-style entity service + real hardware testing. |
| BUG-16 | `Monitor.controllable` unused | Blocked by BUG-08 — will be consumed when PTZ is implemented. |
