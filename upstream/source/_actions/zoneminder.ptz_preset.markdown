---
title: "PTZ preset"
action: zoneminder.ptz_preset
domain: zoneminder
description: "Moves a PTZ-capable ZoneMinder camera to a stored preset position."
---

Use this action to send a PTZ camera to a named preset position stored in ZoneMinder. Preset `0` is the home position. The action is only available on camera entities where ZoneMinder reports the monitor as controllable (PTZ hardware is configured in ZoneMinder).

{% include actions/ui_header.md %}

To move a PTZ camera to a preset from an automation or script:

1. Go to {% my automations title="**Settings** > **Automations & scenes**" %}.
2. Open an existing automation or script, or select **Create automation** > **Create new automation**.
3. If you're setting up a new automation, add a trigger in the **When** section. Scripts don't need a trigger. They run when something else calls them.
4. In the **Then do** section, select **Add action**.
5. From the search box, search for and select **ZoneMinder: PTZ preset**.
6. Select the target camera entity (or entities).
7. Enter the **Preset** number.
8. Select **Save**.

### Options in the UI

{% options_ui %}
Preset:
  description: "Preset number (0–99). Preset `0` returns the camera to its home position."
  required: true
{% endoptions_ui %}

{% include actions/yaml_header.md %}

In YAML, refer to this action as `zoneminder.ptz_preset`. A basic example:

{% example %}
action: |
  action: zoneminder.ptz_preset
  target:
    entity_id: camera.front_door
  data:
    preset: 1
{% endexample %}

To return a camera to its home position:

{% example %}
action: |
  action: zoneminder.ptz_preset
  target:
    entity_id: camera.front_door
  data:
    preset: 0
{% endexample %}

### Options in YAML

{% options_yaml %}
preset:
  description: "Preset number (0–99). Preset `0` returns the camera to its home position."
  required: true
  type: integer
{% endoptions_yaml %}

{% include actions/try_it.md %}

{% include actions/stuck.md %}
