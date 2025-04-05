"""The Wunderground Weather integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .weather import fetch_weather_data
from datetime import timedelta

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    CONF_STATION_NAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wunderground Weather from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get update interval from options or data
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, 
                                      entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
    
    _LOGGER.info("Setting up Wunderground Weather for station %s with update interval %d seconds", 
                entry.data["station_id"], update_interval)
    
    # Initialize the coordinator
    session = async_get_clientsession(hass)
    station_id = entry.data["station_id"]
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"wunderground_weather_{station_id}",
        update_method=lambda: fetch_weather_data(session, station_id),
        update_interval=timedelta(seconds=update_interval),
    )
    
    # Store coordinator in hass data
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for the Wunderground Weather integration."""
    # Get the new update interval from options
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    
    _LOGGER.info("Updating options for Wunderground Weather station %s", entry.data["station_id"])
    _LOGGER.info("New update interval: %d seconds", update_interval)
    
    # Get the coordinator
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Update the coordinator's update interval
    coordinator.update_interval = timedelta(seconds=update_interval)
    
    # Log the update interval change
    _LOGGER.info("Update interval changed to %d seconds for station %s", 
                update_interval, entry.data["station_id"])
    
    # Request a refresh to apply the new interval
    await coordinator.async_request_refresh()
