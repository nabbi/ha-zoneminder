# ha-zoneminder

[![QA](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml/badge.svg)](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml)

ZoneMinder custom integration for Home Assistant (HACS-compatible).

This is an independently maintained replacement for the core ZoneMinder integration,
with bug fixes, a modern config flow, coordinator-based polling, and support for
ZoneMinder 1.37+ monitor controls.

## Compatibility

Tested against **ZoneMinder 1.38.0**. Legacy support for 1.36.x and 1.37.x is
attempted (upstream core still targets these) but untested.

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install **ZoneMinder**.

### Manual

Copy `custom_components/zoneminder/` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Quick Start

1. **Settings > Devices & Services > Add Integration > ZoneMinder**
2. Enter your host, credentials, and SSL settings
3. Configure options (event sensors, stream scale/FPS) via **Configure**

All configuration is done through the UI. See the [Usage Guide](docs/USAGE.md)
for full details on entities, options, YAML migration, and troubleshooting.

## What's Different from Core

- Config flow with reconfigure support (no more YAML-only setup)
- `DataUpdateCoordinator` — single batched API poll every 30s instead of per-entity calls
- `unique_id` and `DeviceInfo` on all entities
- Proper error handling for zm-py exceptions across the integration
- Run state select entity (dropdown control, not just a sensor)
- Per-monitor force alarm switch
- Capturing / Analysing / Recording select entities for ZoneMinder 1.37+
- Stream scale and max FPS options for bandwidth control
- Automatic YAML import with migration guidance

## YAML Migration

If you have existing `zoneminder:` YAML configuration, it will be **automatically
imported** into a config entry on restart. A repair notification will guide you to
remove the YAML and review options in the UI. See the
[Usage Guide](docs/USAGE.md#migrating-from-yaml-configuration) for details.

## Architecture

This integration communicates with ZoneMinder through
[zm-py](https://github.com/rohankapoorcom/zm-py), a lightweight Python API client.
The coordinator polls zm-py every 30 seconds and all entity platforms read from the
shared coordinator data — no entity makes direct API calls for state reads.

Architecture diagrams (draw.io source):

- [Component Architecture](docs/architecture.drawio) — stack overview: HA Core, ha-zoneminder, zm-py, ZoneMinder Server
- [Coordinator Data Flow](docs/data-flow.drawio) — read/write paths through the ZmDataUpdateCoordinator
- [Config & Options Flow](docs/config-flow.drawio) — user setup, YAML import, reconfigure, and options flow

## License

Apache-2.0
