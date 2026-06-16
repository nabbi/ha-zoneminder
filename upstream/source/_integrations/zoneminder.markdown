---
title: ZoneMinder
description: How to integrate ZoneMinder into Home Assistant.
ha_category:
  - Binary sensor
  - Camera
  - Hub
  - Select
  - Sensor
  - Switch
ha_release: 0.31
ha_iot_class: Local Polling
ha_config_flow: true
ha_codeowners:
  - '@nabbi'
ha_domain: zoneminder
ha_platforms:
  - binary_sensor
  - camera
  - select
  - sensor
  - switch
ha_integration_type: integration
---

The **ZoneMinder** {% term integration %} integrates Home Assistant with your [ZoneMinder](https://www.zoneminder.com) surveillance system.

It provides camera streams, monitor controls, event counts, run state management, and PTZ control for compatible cameras.

{% include integrations/config_flow.md %}

{% configuration_basic %}
Host:
  description: "Hostname (or IP address and optional port) of your ZoneMinder server, without a scheme — for example, `zm.example.com` or `192.168.1.10:8080`."
  required: true
Username:
  description: "ZoneMinder username. Required if `OPT_USE_AUTH` is enabled in ZoneMinder."
  required: false
Password:
  description: "ZoneMinder password. Required if `OPT_USE_AUTH` is enabled in ZoneMinder."
  required: false
Use SSL:
  description: Enable HTTPS for the connection.
  required: false
  default: "`false`"
Verify SSL:
  description: Verify the server's SSL certificate.
  required: false
  default: "`true`"
Path:
  description: Web path to the ZoneMinder installation.
  required: false
  default: "`/zm/`"
ZMS path:
  description: "Path to the ZMS streaming CGI script. Must match the `PATH_ZMS` setting in ZoneMinder's **Options > Paths** page."
  required: false
  default: "`/zm/cgi-bin/nph-zms`"
{% endconfiguration_basic %}

## Options

After adding the integration, configure options at **{% my integrations title="Settings > Devices & Services" %}** > **ZoneMinder** > **Configure**.

{% configuration_basic %}
Include archived events:
  description: Include archived events in event count sensors.
  default: "`false`"
Monitored conditions:
  description: "Time periods for which to create event count sensors. Available values: `all`, `hour`, `day`, `week`, `month`."
  default: "`all`"
Stream scale (%, 1–100):
  description: "Scale factor for MJPEG streams. Lower values reduce bandwidth and CPU usage on the ZoneMinder server."
Stream max FPS (MJPEG only):
  description: "Maximum frame rate cap for MJPEG streams (0.5–30.0, step 0.5). Lower values reduce bandwidth."
Monitor function for ON state:
  description: "Monitor function to apply when the legacy function switch is turned on. Only shown for ZoneMinder older than 1.37."
  default: "`Modect`"
Monitor function for OFF state:
  description: "Monitor function to apply when the legacy function switch is turned off. Only shown for ZoneMinder older than 1.37."
  default: "`Monitor`"
{% endconfiguration_basic %}

## Reconfiguring

To change the host, credentials, or connection settings after initial setup, select **Reconfigure** from the three-dot menu on the integration card.

## Migrating from YAML configuration

If you previously configured ZoneMinder using `configuration.yaml`, your connection settings are automatically imported into a config entry on the next restart. A notification appears in {% my repairs title="**Settings** > **System** > **Repairs**" %} confirming the import.

After confirming the import, remove the following from your `configuration.yaml`:

- The `zoneminder:` top-level block
- Any `sensor:`, `switch:`, and `camera:` platform entries for `zoneminder`

The following options are **not** imported and fall back to defaults. Review them in the integration options UI:

| YAML option | Default after import |
|-------------|---------------------|
| `monitored_conditions` | `all` |
| `include_archived` | `false` |
| `command_on` | `Modect` |
| `command_off` | `Monitor` |

## Platforms

### Binary sensor

The integration creates one availability binary sensor per ZoneMinder server,
indicating whether the server is reachable and its daemons are running.

### Camera

The integration creates one camera entity per ZoneMinder monitor, providing the
MJPEG video stream and a still image snapshot. The stream URL and FPS can be
tuned in the integration options.

For monitors that ZoneMinder reports as controllable (PTZ hardware present),
the camera entity supports the [`zoneminder.ptz`](#action-zoneminderptz) and
[`zoneminder.ptz_preset`](#action-zoneminderptz_preset) actions.

### Select

**Per server:**

| Entity | Description |
|--------|-------------|
| Run State Select | Changes the active ZoneMinder run state. In addition to user-defined run states, the dropdown includes built-in `stop` and `restart` options. This entity remains available even when ZoneMinder daemons are stopped, allowing you to restart ZoneMinder from the Home Assistant UI. |

**Per monitor — all ZoneMinder versions:**

| Entity | Options | Description |
|--------|---------|-------------|
| Function | None, Monitor, Modect, Record, Mocord, Nodect | Sets the monitor function. On ZoneMinder 1.37 and later, shows **Custom** when the current Capturing/Analysing/Recording combination does not map to a classic function. |

**Per monitor — ZoneMinder 1.37 and later only:**

| Entity | Options | Description |
|--------|---------|-------------|
| Capturing | None, Ondemand, Always | Controls whether the monitor captures frames. |
| Analysing | None, Always | Controls motion detection analysis. |
| Recording | None, OnMotion, Always | Controls event recording. |

### Sensor

**Per server:**

| Entity | Description |
|--------|-------------|
| Run State | The name of the currently active run state. Goes unavailable when ZoneMinder daemons are stopped. |

**Per monitor:**

| Entity | Description |
|--------|-------------|
| Status | The current monitor function. On ZoneMinder 1.37 and later, shows a composite value (for example, `Always/Always/None`) when the three-field state does not map to a classic function name. |
| Events | Event count sensor for each monitored time period (configured in options). |

### Switch

**Per monitor — all ZoneMinder versions:**

| Entity | Description |
|--------|-------------|
| Force Alarm | Forces the monitor into an alarm/recording state, or cancels a forced alarm. |

**Per monitor — ZoneMinder older than 1.37 only:**

| Entity | Description |
|--------|-------------|
| State | Binary toggle between the configured ON and OFF functions (set in integration options). |

## Actions

{% include integrations/actions.md %}

## Permissions

If ZoneMinder authentication is enabled (`OPT_USE_AUTH`), the account configured
in the integration must have **Edit** permission for **System** to change run
states and monitor functions.
