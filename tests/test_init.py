"""Tests for setup, unload and migration of Wunderground Weather."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
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


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry loads, creates a device and unloads cleanly."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, STATION_ID)}
    assert device.name == "Test Town"
    assert device.manufacturer == "Weather Underground"
    assert device.sw_version == "TestStation 1.0"
    assert device.configuration_url == (
        f"https://www.wunderground.com/dashboard/pws/{STATION_ID}"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_station_offline(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An offline station makes Home Assistant retry the setup later."""
    mock_responses(aioclient_mock, observation_status=204)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_works_without_forecast(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Forecast failures do not block the setup."""
    mock_responses(aioclient_mock, forecast_status=500)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("weather.test_town").state != STATE_UNAVAILABLE


async def test_failed_update_marks_entities_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer,
) -> None:
    """A failed poll makes entities unavailable instead of keeping old values."""
    assert hass.states.get("sensor.test_town_temperature").state == "11.6"

    aioclient_mock.clear_requests()
    mock_responses(aioclient_mock, observation_status=500)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_town_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("weather.test_town").state == STATE_UNAVAILABLE


async def test_migrate_from_1_1(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Old entries get a unique ID and keep their entity IDs."""
    mock_responses(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Station ITEST123",
        version=1,
        minor_version=1,
        data={
            CONF_STATION_ID: STATION_ID,
            CONF_STATION_NAME: "Station ITEST123",
            CONF_UPDATE_INTERVAL: 90,
        },
        options={},
    )
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    old_sensor = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{STATION_ID}_temperature",
        config_entry=entry,
        suggested_object_id="temperature_station_itest123",
    )
    old_weather = entity_registry.async_get_or_create(
        "weather",
        DOMAIN,
        f"{DOMAIN}_{STATION_ID}",
        config_entry=entry,
        suggested_object_id="station_itest123",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == STATION_ID
    assert entry.data == {
        CONF_STATION_ID: STATION_ID,
        CONF_STATION_NAME: "Station ITEST123",
    }
    assert entry.options == {CONF_UPDATE_INTERVAL: 90}
    # Same entity IDs as before the upgrade
    assert hass.states.get(old_sensor.entity_id).state == "11.6"
    assert hass.states.get(old_weather.entity_id) is not None
    assert old_sensor.entity_id == "sensor.temperature_station_itest123"
