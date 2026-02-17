# Breaking Changes & Migration Guide

This document covers what changes when moving from the **built-in HA core ZoneMinder
integration** to this **ha-zoneminder custom integration**. Read this before upgrading
so you know what to expect and what to fix.

## Configuration: YAML to Config Flow

The biggest user-facing change. This integration no longer uses `configuration.yaml`
for setup — it uses the standard HA config flow UI.

**What happens automatically:** If you have existing YAML config, the integration
imports your **connection settings** (host, credentials, SSL, paths) into a config
entry on first restart. A repair notification confirms the import.

**What does NOT import — you must reconfigure in the UI:**

| Option | Default after import | Where to set |
|--------|---------------------|--------------|
| `monitored_conditions` | `all` | Settings > Devices & Services > ZoneMinder > Configure |
| `include_archived` | `false` | Same |
| `command_on` | `Modect` | Same (ZM < 1.37 only) |
| `command_off` | `Monitor` | Same (ZM < 1.37 only) |

If you had customized any of these in YAML (e.g., `monitored_conditions: [hour, day]`
or `command_on: Mocord`), you need to re-apply those settings through the options UI.

**After verifying the import works**, remove from `configuration.yaml`:
- The `zoneminder:` top-level block
- Any `sensor:`, `switch:`, or `camera:` platform entries for `zoneminder`

## Monitor Control on ZM 1.37+ (Select Entities Replace Switch)

This is the most likely automation breaker for users on modern ZoneMinder.

ZoneMinder 1.37 split the single `Function` field into three independent controls:
`Capturing`, `Analysing`, and `Recording`. The integration follows suit.

**Before (ZM < 1.37 or legacy integration):**
```yaml
# Single switch toggling between e.g. Modect and Monitor
- service: switch.turn_on
  target:
    entity_id: switch.front_door_state
```

**After (ZM 1.37+):**
```yaml
# Three independent selects
- service: select.select_option
  target:
    entity_id: select.front_door_capturing
  data:
    option: Always

- service: select.select_option
  target:
    entity_id: select.front_door_analysing
  data:
    option: Always

- service: select.select_option
  target:
    entity_id: select.front_door_recording
  data:
    option: OnMotion
```

The legacy `switch.*_state` entity is **not created** on ZM 1.37+. If your ZM
server is 1.37+ and you have automations using the old switch, they will break.

On ZM < 1.37, the switch still exists and works as before.

## Entity Unique IDs (All New)

The legacy integration had **no unique IDs** on any entity. This integration adds
them to every entity. This is not a breaking change per se, but has side effects:

- Entities now appear in the entity registry and can be renamed/customized via UI
- If you previously had entity ID conflicts from renaming monitors in ZM, those
  are now resolved — each entity is anchored to `{host}_{monitor_id}`
- Entity IDs themselves (the `sensor.foo_bar` part) are still derived from monitor
  names, so they should match what you had before

## Device Grouping (All New)

All entities are now grouped under HA devices:

- **Per-server device**: Contains the availability binary sensor, run state sensor,
  and run state select. Shows ZM version as `sw_version`.
- **Per-monitor devices**: Contains the camera, status sensor, event sensors,
  switches, and selects for that monitor. Linked to the server via `via_device`.

This means the Devices page now shows a ZoneMinder device hierarchy. Dashboards
using device-based cards will pick these up. No action required, but your device
list will grow.

## New Entities

These entities did not exist in the legacy integration:

| Entity | Type | Availability |
|--------|------|-------------|
| `switch.*_force_alarm` | Switch | All ZM versions, per monitor |
| `select.run_state_select` | Select | All ZM versions, per server |
| `select.*_capturing` | Select | ZM 1.37+ only, per monitor |
| `select.*_analysing` | Select | ZM 1.37+ only, per monitor |
| `select.*_recording` | Select | ZM 1.37+ only, per monitor |

These appear automatically. If you don't want them, disable them in the entity
registry.

## Status Sensor Display (ZM 1.37+)

The monitor status sensor (`sensor.*_status`) now shows richer state on ZM 1.37+:

- If the three-field state maps to a classic function (e.g., Modect, Record), it
  shows the classic name
- If it doesn't map cleanly, it shows a composed value like `Always/Always/None`
- On ZM < 1.37, behavior is unchanged — shows the `Function` field value

If you have automations that check `sensor.*_status` against specific values, test
that they still match.

## Service: `zoneminder.set_run_state`

The service still exists and works the same way, but two things changed:

1. **The `id` field is now validated.** The legacy integration silently fell through
   to a KeyError if you passed an invalid host. Now it logs an error and returns
   early.
2. **There is now a select entity alternative.** `select.run_state_select` provides
   the same functionality via the UI. The service remains for backward compatibility
   and automation use.

## Polling & Performance

Not a breaking change, but worth knowing:

- **Before:** Each entity polled independently (~14 API calls per monitor per cycle)
- **After:** A shared `DataUpdateCoordinator` fetches all data in one batch every
  30 seconds (~3-5 API calls total per cycle)

If you had ZoneMinder performance issues or API rate limiting, this should help
significantly. The 30-second interval is not currently configurable.

## zm-py Version Bump

The integration requires `zm-py==0.5.5.dev13` (up from `0.5.4` in core). This
version adds ZM 1.37+ monitor field support, force alarm, and better error handling.
It installs automatically — just be aware if you have zm-py pinned elsewhere.

## Options Available After Setup

These are configurable at any time via the integration options UI (no restart needed):

| Option | Default | Notes |
|--------|---------|-------|
| Include archived events | `false` | Event count sensors |
| Monitored conditions | `all` | Which time periods get event sensors |
| Stream scale (%) | — | 1-100, reduces MJPEG bandwidth |
| Stream max FPS | — | 0.5-30.0, caps stream frame rate |
| Monitor function ON | `Modect` | ZM < 1.37 only |
| Monitor function OFF | `Monitor` | ZM < 1.37 only |

Stream scale and max FPS are new — they help with bandwidth on remote/constrained
setups.

## Migration Checklist

1. Back up your automations, scripts, and dashboard configs
2. Install ha-zoneminder via HACS (or copy to `custom_components/`)
3. Restart Home Assistant — YAML import triggers automatically
4. Check **Settings > Repairs** for the import confirmation
5. Go to **Settings > Devices & Services > ZoneMinder > Configure** and review options
   (especially `monitored_conditions` and `command_on`/`command_off` if you customized them)
6. **If on ZM 1.37+:** Update automations that used `switch.*_state` to use the
   new `select.*_capturing` / `select.*_analysing` / `select.*_recording` entities
7. Test that dashboards and automations still work
8. Remove all ZoneMinder YAML from `configuration.yaml`
9. Restart once more to confirm clean operation
