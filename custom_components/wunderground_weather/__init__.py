"""Initialize the Wunderground Weather integration."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wunderground_weather"
PLATFORMS = ["weather"]


async def async_setup_entry(hass, config_entry):
    """Set up Wunderground Weather from a config entry."""
    _LOGGER.debug(f"Setting up Wunderground Weather for {config_entry.entry_id}")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    try:
        await hass.config_entries.async_forward_entry_setup(config_entry, "weather")
        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up Wunderground Weather: {e}")
        return False


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.debug(f"Unloading Wunderground Weather for {config_entry.entry_id}")
    unload_ok = await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
    return unload_ok
