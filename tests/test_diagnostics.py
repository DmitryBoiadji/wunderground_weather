"""Tests for Wunderground Weather diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wunderground_weather.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import API_KEY


async def test_diagnostics(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Diagnostics contain the data needed for support, without secrets."""
    result = await async_get_config_entry_diagnostics(hass, setup_integration)

    assert result["observation"]["last_update_success"] is True
    assert result["observation"]["data"]["lat"] == "**REDACTED**"
    assert result["observation"]["data"]["metric"]["temp"] == 11.6
    assert result["forecast"]["has_daily"] is True
    assert result["forecast"]["has_hourly"] is True
    assert API_KEY not in str(result)
