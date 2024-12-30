import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from datetime import timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Wunderground integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    update_interval = timedelta(seconds=config_entry.data.get("update_interval"))

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Wunderground {config_entry.data['station_id']}",
        update_interval=update_interval,
        update_method=lambda: fetch_weather_data(
            hass.helpers.aiohttp_client.async_get_clientsession(),
            config_entry.data["station_id"],
        ),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, ["weather"])
    # await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor", "weather"])
    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, ["weather"])
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
