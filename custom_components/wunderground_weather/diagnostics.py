"""Diagnostics support for Wunderground Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import WundergroundConfigEntry

# Station coordinates are public on wunderground.com, but diagnostics are
# often pasted into public issues
TO_REDACT = {"lat", "lon"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WundergroundConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    forecast = data.forecast.data
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "observation": {
            "last_update_success": data.observation.last_update_success,
            "is_stale": data.observation.is_stale,
            "data": async_redact_data(data.observation.data or {}, TO_REDACT),
        },
        "forecast": {
            "last_update_success": data.forecast.last_update_success,
            "last_update_success_time": (
                data.forecast.last_update_success_time.isoformat()
                if data.forecast.last_update_success_time
                else None
            ),
            "conditions": forecast.conditions if forecast else None,
            "has_daily": bool(forecast and forecast.daily),
            "has_hourly": bool(forecast and forecast.hourly),
        },
    }
