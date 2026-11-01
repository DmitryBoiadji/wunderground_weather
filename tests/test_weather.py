"""Tests for the Wunderground Weather entity."""

from __future__ import annotations

from datetime import timedelta

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
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from .conftest import CONDITIONS_URL, HOURLY_URL, load_json, mock_responses

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
    await hass.async_block_till_done(wait_background_tasks=True)

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
    await hass.async_block_till_done(wait_background_tasks=True)

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


async def _get_forecast(hass: HomeAssistant, forecast_type: str) -> list[dict]:
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    return response[ENTITY_ID]["forecast"]


async def _advance(hass: HomeAssistant, freezer, delta: timedelta) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _fresh_observation(freezer_now: str) -> dict:
    """Return the fixture observation reported at the given time."""
    observation = load_json("observation.json")
    observation["observations"][0]["obsTimeUtc"] = freezer_now
    return observation


async def test_conditions_poll_without_subscription(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer,
) -> None:
    """Conditions refresh every 15 minutes even without a forecast card."""
    assert hass.states.get(ENTITY_ID).state == "cloudy"

    conditions = load_json("conditions.json")
    conditions["iconCode"] = 33
    conditions["validTimeUtc"] += 900
    aioclient_mock.clear_requests()
    aioclient_mock.get(CONDITIONS_URL, json=conditions)
    mock_responses(aioclient_mock)
    await _advance(hass, freezer, timedelta(minutes=15, seconds=1))

    assert hass.states.get(ENTITY_ID).state == "clear-night"


async def test_partial_forecast_failure_keeps_old_parts(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer,
) -> None:
    """A failing endpoint keeps its previous data, the others are updated."""
    conditions = load_json("conditions.json")
    conditions["iconCode"] = 33
    conditions["validTimeUtc"] += 900
    aioclient_mock.clear_requests()
    aioclient_mock.get(CONDITIONS_URL, json=conditions)
    aioclient_mock.get(HOURLY_URL, status=500)
    mock_responses(aioclient_mock)
    await _advance(hass, freezer, timedelta(minutes=15, seconds=1))

    coordinator = setup_integration.runtime_data.forecast
    assert coordinator.last_update_success
    assert coordinator.data.conditions["iconCode"] == 33
    assert coordinator.data.hourly is not None
    assert len(await _get_forecast(hass, "hourly")) == 48


async def test_forecast_survives_weather_com_outage(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer,
) -> None:
    """The last forecast is served for a while when weather.com is down."""
    aioclient_mock.clear_requests()
    mock_responses(
        aioclient_mock,
        observation=_fresh_observation("2026-11-01T11:45:00Z"),
        forecast_status=500,
    )
    await _advance(hass, freezer, timedelta(minutes=16))

    assert setup_integration.runtime_data.forecast.last_update_success is False
    assert len(await _get_forecast(hass, "daily")) == 6
    assert len(await _get_forecast(hass, "hourly")) == 48
    state = hass.states.get(ENTITY_ID)
    assert state.state == "cloudy"
    assert state.attributes[ATTR_WEATHER_CLOUD_COVERAGE] == 78

    # 3 hours later: hourly forecast and conditions are too old
    aioclient_mock.clear_requests()
    mock_responses(
        aioclient_mock,
        observation=_fresh_observation("2026-11-01T14:45:00Z"),
        forecast_status=500,
    )
    await _advance(hass, freezer, timedelta(hours=3))

    assert await _get_forecast(hass, "hourly") == []
    assert len(await _get_forecast(hass, "daily")) == 6
    state = hass.states.get(ENTITY_ID)
    assert ATTR_WEATHER_CLOUD_COVERAGE not in state.attributes
    assert ATTR_WEATHER_VISIBILITY not in state.attributes


async def test_twice_daily_forecast_values(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Day parts start at 07:00 and 19:00 local time."""
    forecast = await _get_forecast(hass, "twice_daily")
    day, night = forecast[0], forecast[1]

    assert day["datetime"] == "2026-11-01T15:00:00+00:00"
    assert day["is_daytime"] is True
    assert day["temperature"] == 18
    assert day["condition"] == "rainy"
    assert night["datetime"] == "2026-11-02T03:00:00+00:00"
    assert night["is_daytime"] is False
    assert night["temperature"] == 10
    assert night["condition"] == "clear-night"
