# ha-zoneminder

[![QA](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml/badge.svg)](https://github.com/nabbi/ha-zoneminder/actions/workflows/qa.yml)

ZoneMinder custom integration for Home Assistant (HACS-compatible).

This is an extracted and independently maintained version of the core ZoneMinder integration, giving full freedom to fix bugs, modernize architecture, and iterate independently.

## Installation

### Manual

1. Copy the `custom_components/zoneminder/` directory into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

This integration uses the same YAML configuration as the core ZoneMinder integration:

```yaml
zoneminder:
  - host: your-zm-host.example.com
    username: admin
    password: secret
```

See the [Home Assistant ZoneMinder documentation](https://www.home-assistant.io/integrations/zoneminder) for full configuration options.

## License

Apache-2.0
