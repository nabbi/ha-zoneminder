# ZoneMinder Integration Usage Guide

## Compatibility

| ZoneMinder Version | Support Level |
|--------------------|---------------|
| 1.38.x             | Tested — full feature set |
| 1.37.x             | Legacy — attempted support (untested) |
| 1.36.x             | Legacy — attempted support (untested) |

The upstream core integration still targets 1.36+. This custom integration preserves
that compatibility path but is only actively tested against **ZoneMinder 1.38.0**.

ZoneMinder 1.37 introduced a new monitor model that split the single `Function` field
into three independent controls: **Capturing**, **Analysing**, and **Recording**. The
integration detects the server version and exposes the appropriate entities automatically
(see [Entities by ZM Version](#entities-by-zm-version) below).

## Setup

### Adding the Integration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **ZoneMinder**
3. Enter your connection details:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| Host | Yes | — | ZoneMinder hostname (and optional port), without scheme |
| Username | No | — | ZoneMinder user (required if `OPT_USE_AUTH` is enabled) |
| Password | No | — | ZoneMinder password |
| Use SSL | No | `false` | Enable HTTPS |
| Verify SSL | No | `true` | Verify the server certificate |
| Path | No | `/zm/` | Web path to ZoneMinder |
| ZMS path | No | `/zm/cgi-bin/nph-zms` | Path to the ZMS streaming CGI — must match `PATH_ZMS` in ZoneMinder's Paths settings |

### Reconfiguring Connection Settings

To change host, credentials, or SSL settings after initial setup:

**Settings > Devices & Services > ZoneMinder > (three-dot menu) > Reconfigure**

### Options

After setup, configure integration options via:

**Settings > Devices & Services > ZoneMinder > Configure**

| Option | Default | Description |
|--------|---------|-------------|
| Include archived events | `false` | Count archived events in event sensors |
| Monitored conditions | `all` | Which event time periods to create sensors for (`all`, `hour`, `day`, `week`, `month`) |
| Stream scale (%) | — | Percentage to scale MJPEG streams (1–100). Reduces bandwidth and CPU |
| Stream max FPS | — | Cap MJPEG stream frame rate (0.5–30.0 FPS). Reduces bandwidth |
| Monitor function ON* | `Modect` | Monitor function when switch is turned on |
| Monitor function OFF* | `Monitor` | Monitor function when switch is turned off |

*\* ON/OFF function options are only shown on ZoneMinder < 1.37, where the legacy
monitor function switch is used.*

## Migrating from YAML Configuration

If you previously configured ZoneMinder via `configuration.yaml`, the integration
will **automatically import** your connection settings into a config entry on the
next restart. A notification will appear in **Settings > Repairs** confirming the
import.

After import, remove all ZoneMinder YAML from your `configuration.yaml`:

- The `zoneminder:` top-level block
- Any `sensor:`, `switch:`, or `camera:` platform entries for `zoneminder`

**What is imported automatically:**
- Connection settings: host, username, password, SSL, path, path_zms, verify_ssl

**What is NOT imported (set to defaults — configure via UI):**
- `monitored_conditions` (defaults to `all`)
- `command_on` / `command_off` (defaults to `Modect` / `Monitor`)
- `include_archived` (defaults to `false`)

## Entities

### Per Server

| Entity | Type | Description |
|--------|------|-------------|
| ZoneMinder Availability | Binary sensor | Server connectivity status |
| Run State | Sensor | Current active run state (e.g., "default") |
| Run State | Select | Dropdown to change the active run state |

### Per Monitor

| Entity | Type | Description |
|--------|------|-------------|
| Camera | Camera | MJPEG stream and still image from the monitor |
| Status | Sensor | Current monitor function/state |
| Events (per period) | Sensor | Event count for selected time periods |
| Force Alarm | Switch | Trigger or cancel an alarm on the monitor |

### Entities by ZM Version

The monitor control entities differ based on your ZoneMinder version:

**ZoneMinder 1.37+ (new monitor model):**

| Entity | Type | Options | Description |
|--------|------|---------|-------------|
| Capturing | Select | None, Ondemand, Always | Controls whether the monitor captures frames |
| Analysing | Select | None, Always | Controls motion detection analysis |
| Recording | Select | None, OnMotion, Always | Controls event recording |

**ZoneMinder < 1.37 (legacy):**

| Entity | Type | Description |
|--------|------|-------------|
| Monitor Function | Switch | Toggles between the configured ON/OFF functions (e.g., Modect/Monitor) |

## Services

### `zoneminder.set_run_state`

Changes the active run state of a ZoneMinder server.

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Hostname of the ZoneMinder server to target |
| `name` | Yes | Name of the run state to activate |

Example automation action:

```yaml
action: zoneminder.set_run_state
data:
  id: zm.example.com
  name: Home
```

> **Note:** The Run State select entity provides the same functionality via the UI
> without needing to write service calls.

## Permissions

If ZoneMinder authentication is enabled (`OPT_USE_AUTH`), the configured account
needs **Edit** permission for **System** to change run states and monitor functions.

## Known Limitations

- **PTZ (Pan/Tilt/Zoom) is not supported.** The underlying zm-py library has full PTZ
  support, but the Home Assistant entity layer has not been implemented yet due to lack of
  PTZ-capable test hardware. This is tracked as BUG-08.
- **Multiple ZoneMinder servers** are supported, but each must have a unique hostname.

## Troubleshooting

### Stream not loading

- Verify that `PATH_ZMS` in ZoneMinder's **Options > Paths** matches the **ZMS path**
  configured in the integration
- If using a reverse proxy, ensure the ZMS CGI path is proxied correctly
- Try lowering **Stream scale** and **Stream max FPS** in options to reduce bandwidth

### Entities show unavailable

- Check the **ZoneMinder Availability** binary sensor — if it's off, the server is
  unreachable
- Verify credentials via **Reconfigure** if you recently changed your ZoneMinder password
- Check Home Assistant logs for `zoneminder` entries
