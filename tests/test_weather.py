"""Tests for the Wunderground Weather entity."""

from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from .conftest import load_json, mock_responses

ENTITY_ID = "weather.test_town"


async def test_weather_state(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entity combines station values with weather.com conditions."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # conditions.json: icon 27 (mostly cloudy, night)
    assert state.state == "cloudy"
    assert state.attributes[ATTR_WEATHER_TEMPERATURE] == 11.6
    assert state.attributes[ATTR_WEATHER_APPARENT_TEMPERATURE] == 11.6
    assert state.attributes[ATTR_WEATHER_DEW_POINT] == 10.6
    assert state.attributes[ATTR_WEATHER_HUMIDITY] == 94
    assert state.attributes[ATTR_WEATHER_PRESSURE] == 1013.61
    assert state.attributes[ATTR_WEATHER_WIND_SPEED] == 7.2
    assert state.attributes[ATTR_WEATHER_WIND_GUST_SPEED] == 11.5
    assert state.attributes[ATTR_WEATHER_WIND_BEARING] == 176
    assert state.attributes[ATTR_WEATHER_UV_INDEX] == 3.0
    assert state.attributes[ATTR_WEATHER_CLOUD_COVERAGE] == 78
    assert state.attributes[ATTR_WEATHER_VISIBILITY] == 14.48
    assert state.attributes[ATTR_ATTRIBUTION] == "Data provided by Weather Underground"


async def test_station_rain_overrides_conditions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Rain measured by the station wins over a dry weather.com report."""
    observation = load_json("observation.json")
    observation["observations"][0]["metric"]["precipRate"] = 9.1
    mock_responses(aioclient_mock, observation=observation)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "pouring"


async def test_fallback_without_conditions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Without weather.com the condition is estimated from station sensors."""
    observation = load_json("observation.json")
    observation["observations"][0]["humidity"] = 99.0
    mock_responses(aioclient_mock, observation=observation, forecast_status=500)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "fog"


@pytest.mark.parametrize(
    ("forecast_type", "count"),
    [("daily", 6), ("twice_daily", 12), ("hourly", 48)],
)
async def test_forecasts(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    forecast_type: str,
    count: int,
) -> None:
    """All forecast types are served through weather.get_forecasts."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    forecast = response[ENTITY_ID]["forecast"]
    assert len(forecast) == count
    assert all("datetime" in entry and "condition" in entry for entry in forecast)


async def test_daily_forecast_values(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Daily entries use calendar day extremes and the daytime part."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    today = response[ENTITY_ID]["forecast"][0]
    assert today["datetime"] == "2026-11-01T15:00:00+00:00"
    assert today["temperature"] == 18
    assert today["templow"] == 11
    assert today["precipitation"] == 0.05
    # max of day (49) and night (8)
    assert today["precipitation_probability"] == 49
    # icon 39, scattered showers
    assert today["condition"] == "rainy"
    assert today["wind_bearing"] == 324


async def test_hourly_forecast_values(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Hourly entries carry the full set of values."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    first = response[ENTITY_ID]["forecast"][0]
    assert first["datetime"] == "2026-11-01T12:00:00+00:00"
    assert first["temperature"] == 10
    assert first["apparent_temperature"] == 10
    assert first["precipitation_probability"] == 57
    assert first["pressure"] == 1010.23
    assert first["condition"] == "rainy"
    assert "wind_gust_speed" not in first
