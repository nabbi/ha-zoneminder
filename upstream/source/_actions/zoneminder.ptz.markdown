---
title: "PTZ move"
action: zoneminder.ptz
domain: zoneminder
description: "Moves a PTZ-capable ZoneMinder camera in a cardinal or diagonal direction."
---

Use this action to pan or tilt a PTZ camera connected to ZoneMinder. The action is only available on camera entities where ZoneMinder reports the monitor as controllable (PTZ hardware is configured in ZoneMinder).

{% include actions/ui_header.md %}

To move a PTZ camera from an automation or script:

1. Go to {% my automations title="**Settings** > **Automations & scenes**" %}.
2. Open an existing automation or script, or select **Create automation** > **Create new automation**.
3. If you're setting up a new automation, add a trigger in the **When** section. Scripts don't need a trigger. They run when something else calls them.
4. In the **Then do** section, select **Add action**.
5. From the search box, search for and select **ZoneMinder: PTZ move**.
6. Select the target camera entity (or entities).
7. Choose the **Direction** to move.
8. Select **Save**.

### Options in the UI

{% options_ui %}
Direction:
  description: "Direction to move the camera. One of: `right`, `left`, `up`, `down`, `up_left`, `up_right`, `down_left`, `down_right`."
  required: true
{% endoptions_ui %}

{% include actions/yaml_header.md %}

In YAML, refer to this action as `zoneminder.ptz`. A basic example:

{% example %}
action: |
  action: zoneminder.ptz
  target:
    entity_id: camera.front_door
  data:
    direction: right
{% endexample %}

### Options in YAML

{% options_yaml %}
direction:
  description: "Direction to move the camera. One of: `right`, `left`, `up`, `down`, `up_left`, `up_right`, `down_left`, `down_right`."
  required: true
  type: string
{% endoptions_yaml %}

{% include actions/try_it.md %}

{% include actions/stuck.md %}
