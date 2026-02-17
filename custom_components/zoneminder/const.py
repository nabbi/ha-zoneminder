"""Constants for ZoneMinder integration."""

from homeassistant.const import Platform

DOMAIN = "zoneminder"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_PATH_ZMS = "path_zms"
CONF_INCLUDE_ARCHIVED = "include_archived"
CONF_STREAM_SCALE = "stream_scale"
CONF_STREAM_MAXFPS = "stream_maxfps"

DEFAULT_PATH = "/zm/"
DEFAULT_PATH_ZMS = "/zm/cgi-bin/nph-zms"
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DEFAULT_INCLUDE_ARCHIVED = False
DEFAULT_MONITORED_CONDITIONS = ["all"]
DEFAULT_COMMAND_ON = "Modect"
DEFAULT_COMMAND_OFF = "Monitor"
