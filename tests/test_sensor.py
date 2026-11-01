"""Tests for Wunderground Weather sensors."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wunderground_weather.const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

from .conftest import STATION_ID, mock_responses


@pytest.mark.parametrize(
    ("entity_id", "state", "unit", "device_class", "state_class"),
    [
        (
            "sensor.test_town_temperature",
            "11.6",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_humidity",
            "94.0",
            "%",
            SensorDeviceClass.HUMIDITY,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_atmospheric_pressure",
            "1013.61",
            "hPa",
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_wind_speed",
            "7.2",
            "km/h",
            SensorDeviceClass.WIND_SPEED,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_wind_gust",
            "11.5",
            "km/h",
            SensorDeviceClass.WIND_SPEED,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_wind_direction",
            "176.0",
            "°",
            SensorDeviceClass.WIND_DIRECTION,
            SensorStateClass.MEASUREMENT_ANGLE,
        ),
        (
            "sensor.test_town_dew_point",
            "10.6",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_heat_index",
            "11.6",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_wind_chill",
            "11.6",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_solar_radiation",
            "412.5",
            "W/m²",
            SensorDeviceClass.IRRADIANCE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_uv_index",
            "3.0",
            "UV index",
            None,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_precipitation_intensity",
            "0.0",
            "mm/h",
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.test_town_precipitation_today",
            "4.09",
            "mm",
            SensorDeviceClass.PRECIPITATION,
            SensorStateClass.TOTAL_INCREASING,
        ),
        (
            "sensor.test_town_last_observation",
            "2026-11-01T11:28:33+00:00",
            None,
            SensorDeviceClass.TIMESTAMP,
            None,
        ),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    state: str,
    unit: str | None,
    device_class: str | None,
    state_class: str | None,
) -> None:
    """Every sensor reports its value with unit, device class and state class."""
    current = hass.states.get(entity_id)
    assert current is not None, entity_id
    assert current.state == state
    assert current.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit
    assert current.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert current.attributes.get(ATTR_STATE_CLASS) == state_class


async def test_unique_ids_are_unchanged(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Unique IDs keep the format of earlier versions."""
    entity_registry = er.async_get(hass)
    for key in (
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_gust",
        "wind_bearing",
        "dew_point",
        "solar_radiation",
        "uv",
        "precip_rate",
        "precip_total",
    ):
        assert entity_registry.async_get_entity_id(
            "sensor", "wunderground_weather", f"{STATION_ID}_{key}"
        ), key


async def test_stale_station_is_unavailable(
    hass: HomeAssistant, setup_integration: MockConfigEntry, freezer
) -> None:
    """Values freeze when a station stops reporting, so show them as unavailable."""
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.test_town_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("weather.test_town").state == STATE_UNAVAILABLE
    # The timestamp stays visible to show when the station reported last
    assert (
        hass.states.get("sensor.test_town_last_observation").state
        == "2026-11-01T11:28:33+00:00"
    )


async def test_long_interval_is_not_stale(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    """With a 1 hour interval, data just over an hour old is still valid."""
    mock_responses(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Town",
        unique_id=STATION_ID,
        version=1,
        minor_version=2,
        data={CONF_STATION_ID: STATION_ID, CONF_STATION_NAME: "Test Town"},
        options={CONF_UPDATE_INTERVAL: 3600},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.test_town_temperature").state == "11.6"
