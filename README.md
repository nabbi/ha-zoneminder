# ha-zoneminder

[![QA](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml/badge.svg)](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml)

ZoneMinder custom integration for Home Assistant (HACS-compatible).

This is a barrier-free maintained replacement for the core ZoneMinder integration,
with bug fixes, a modern config flow, coordinator-based polling, and support for
ZoneMinder 1.37+ monitor controls.

## Compatibility

Tested against **ZoneMinder 1.38.3**.

Older 1.36.x and 1.37.x releases are confirmed working yet likely won't receive additional updates.

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install **ZoneMinder**.

### Manual

Copy `custom_components/zoneminder/` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Quick Start

1. **Settings > Devices & Services > Add Integration > ZoneMinder**
2. Enter your host, credentials, and SSL settings
3. Leave **API** on **Auto**, or pick API v2 or API v3 (see below)
4. Configure options (event sensors, stream scale/FPS) via **Configure**

All configuration is done through the UI. See the [Usage Guide](docs/USAGE.md)
for full details on entities, options, YAML migration, and troubleshooting.

## What's Different from Core

- Config flow with reconfigure support (no more YAML-only setup)
- `DataUpdateCoordinator` — single batched API poll every 30s instead of per-entity calls
- `unique_id` and `DeviceInfo` on all entities
- Proper error handling for ZoneMinder API errors across the integration
- Run state select entity (dropdown control, not just a sensor)
- Per-monitor force alarm switch
- Capturing / Analysing / Recording select entities for ZoneMinder 1.37+
- PTZ directional control and preset services for controllable cameras
- Stream scale and max FPS options for bandwidth control
- Automatic YAML import with migration guidance

## API v2 and API v3

The **API** setting picks how the integration talks to ZoneMinder:

- **Auto** (default): ZoneMinder's API v2 when it answers, else API v3
  ([zm-api](https://github.com/SteveGilvarry/zm-api)) under the same path (`/zm/api/v3`),
  or at the zm-api URL when one is given
- **API v2**: ZoneMinder's own API under the path (`/zm/api`)
- **API v3**: zm-api only, under the path or at the server root (`/api/v3`). Set the
  zm-api URL when it runs on its own port (for example `http://zm.local:8080`)

The API found is stored with the entry, so Home Assistant doesn't look again at each
start; **Reconfigure** looks again. A wrong password stops the search (both APIs check
the same ZoneMinder users), and API v2 turned off (`OPT_USE_API`) counts as not answering. Entries made before this setting are API v2.
Entities and their IDs are the same on both APIs.

API v3 is new here: cameras show still images on it (zm-api has no MJPEG; its HLS
streams aren't used yet), and zm-api needs a login even when ZoneMinder's
authentication is off. Auto prefers API v2 for that reason.

## YAML Migration

If you have existing `zoneminder:` YAML configuration, it will be **automatically
imported** into a config entry on restart. A repair notification will guide you to
remove the YAML and review options in the UI. See the
[Usage Guide](docs/USAGE.md#migrating-from-yaml-configuration) for details.

## Architecture

This integration communicates with ZoneMinder's API v2 (or API v3, see above) through
[aiozoneminder](https://github.com/ZoneMinder/aiozoneminder), an async Python client,
on Home Assistant's own HTTP session. (Up to 0.1.5 it used
[zm-py](https://github.com/rohankapoorcom/zm-py).) The coordinator polls every 30 seconds
and all entity platforms read from the shared coordinator data — no entity makes direct
API calls for state reads.

Architecture diagrams (draw.io source):

- [Component Architecture](docs/architecture.png) — stack overview: HA Core, ha-zoneminder, the API client (drawn as zm-py, now aiozoneminder), ZoneMinder Server
- [Coordinator Data Flow](docs/data-flow.png) — read/write paths through the ZmDataUpdateCoordinator
- [Config & Options Flow](docs/config-flow.png) — user setup, YAML import, reconfigure, and options flow

## License

Apache-2.0
