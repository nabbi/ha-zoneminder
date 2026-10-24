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
# The API the user picked (auto, v2 or v3), the one found when the entry was
# set up, and where zm-api (API v3) answers when it isn't under the web path.
CONF_API_VERSION = "api_version"
CONF_API_BACKEND = "api_backend"
CONF_API_V3_URL = "api_v3_url"

API_AUTO = "auto"
API_V2 = "v2"
API_V3 = "v3"
API_VERSIONS = [API_AUTO, API_V2, API_V3]
# Auto tries these in order. API v2 first while the camera has no live view on
# v3 (no MJPEG there; HLS isn't wired up yet), so auto never trades live view
# for stills; v3 is picked when API v2 doesn't answer (OPT_USE_API off).
API_AUTO_ORDER = [API_V2, API_V3]

DEFAULT_PATH = "/zm/"
DEFAULT_PATH_ZMS = "/zm/cgi-bin/nph-zms"
DEFAULT_API_VERSION = API_AUTO
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DEFAULT_INCLUDE_ARCHIVED = False
DEFAULT_MONITORED_CONDITIONS = ["all"]
DEFAULT_COMMAND_ON = "Modect"
DEFAULT_COMMAND_OFF = "Monitor"

SERVICE_PTZ = "ptz"
SERVICE_PTZ_PRESET = "ptz_preset"
ATTR_DIRECTION = "direction"
ATTR_PRESET = "preset"
SUPPORT_PTZ = 4  # Custom feature bit for PTZ-capable cameras
