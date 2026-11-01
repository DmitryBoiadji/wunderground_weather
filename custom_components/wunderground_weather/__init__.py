"""The Wunderground Weather integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WundergroundClient, normalize_station_id
from .const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import (
    WundergroundConfigEntry,
    WundergroundData,
    WundergroundForecastCoordinator,
    WundergroundObservationCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: WundergroundConfigEntry
) -> bool:
    """Set up Wunderground Weather from a config entry."""
    client = WundergroundClient(
        async_get_clientsession(hass), entry.data[CONF_STATION_ID]
    )
    observation = WundergroundObservationCoordinator(hass, entry, client)
    # Raises ConfigEntryNotReady, Home Assistant retries the setup later
    await observation.async_config_entry_first_refresh()

    forecast = WundergroundForecastCoordinator(hass, entry, client, observation)
    # Forecasts are optional, a failure here must not block the setup
    await forecast.async_refresh()

    entry.runtime_data = WundergroundData(
        client=client, observation=observation, forecast=forecast
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WundergroundConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: WundergroundConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, entry: WundergroundConfigEntry
) -> bool:
    """Migrate old config entries."""
    if entry.version > 1:
        # Downgrade from a future version
        return False

    if entry.minor_version < 2:
        # 1.1 stored the interval in data and options and had no unique ID
        station_id = entry.data[CONF_STATION_ID]
        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        unique_id = entry.unique_id
        if unique_id is None:
            candidate = normalize_station_id(station_id)
            in_use = any(
                other.unique_id == candidate
                for other in hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != entry.entry_id
            )
            unique_id = None if in_use else candidate
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_STATION_ID: station_id,
                CONF_STATION_NAME: entry.data.get(CONF_STATION_NAME) or entry.title,
            },
            options={CONF_UPDATE_INTERVAL: update_interval},
            unique_id=unique_id,
            minor_version=2,
        )
        LOGGER.debug("Migrated config entry %s to version 1.2", entry.entry_id)

    return True
