"""Monitor modes and event periods, as the integration has always shown them.

These came from zm-py, which aiozoneminder replaces. aiozoneminder works with
the three ZoneMinder 1.37+ fields; the entities still offer the classic
single Function as well, so the mapping stays here.
"""

from __future__ import annotations

from enum import Enum


class MonitorState(Enum):
    """A monitor's classic (pre-1.37) Function."""

    NONE = "None"
    MONITOR = "Monitor"
    MODECT = "Modect"
    RECORD = "Record"
    MOCORD = "Mocord"
    NODECT = "Nodect"


# Minimum ZM version with the Capturing/Analysing/Recording fields.
_ZM_NEW_FIELDS_VERSION = (1, 37)


def _parse_version(version_string: str | None) -> tuple[int, ...] | None:
    """Parse a ZM version string like '1.36.26' into a comparable tuple."""
    try:
        return tuple(int(x) for x in str(version_string).split("."))
    except ValueError:
        return None


def is_zm_137_or_later(zm_version: str | None) -> bool:
    """Return True if the ZM version is >= 1.37 (has the split monitor fields)."""
    parsed = _parse_version(zm_version)
    return parsed is not None and parsed >= _ZM_NEW_FIELDS_VERSION


def derive_function(capturing: str, analysing: str, recording: str) -> MonitorState | None:
    """Return the classic Function for the 1.37+ fields.

    Returns None if the combination doesn't map to any classic MonitorState.
    """
    if capturing == "None":
        return MonitorState.NONE
    if capturing != "Always":
        # Ondemand or unknown value -- no classic equivalent
        return None
    if analysing == "None" and recording == "None":
        return MonitorState.MONITOR
    if analysing == "Always" and recording == "OnMotion":
        return MonitorState.MODECT
    if analysing == "None" and recording == "Always":
        return MonitorState.RECORD
    if analysing == "Always" and recording == "Always":
        return MonitorState.MOCORD
    if analysing == "None" and recording == "OnMotion":
        return MonitorState.NODECT
    return None


class TimePeriod(Enum):
    """A period of time to count events in."""

    ALL = ("all", "Events", "total_events")
    HOUR = ("hour", "Events Last Hour", "hour_events")
    DAY = ("day", "Events Last Day", "day_events")
    WEEK = ("week", "Events Last Week", "week_events")
    MONTH = ("month", "Events Last Month", "month_events")

    @property
    def period(self) -> str:
        """Get the period of time."""
        return self.value[0]

    @property
    def title(self) -> str:
        """Explains what is measured in this period."""
        return self.value[1]

    @property
    def summary_field(self) -> str:
        """The aiozoneminder EventSummary field holding this period's count."""
        return self.value[2]

    @classmethod
    def get_time_period(cls, value: str) -> TimePeriod:
        """Get the corresponding TimePeriod from the value.

        Example values: 'all', 'hour', 'day', 'week', or 'month'.
        """
        for time_period in cls:
            if time_period.period == value:
                return time_period
        raise ValueError(f"{value} is not a valid TimePeriod")
