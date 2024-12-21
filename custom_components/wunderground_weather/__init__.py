"""Initialize the Wunderground Weather integration."""

DOMAIN = "wunderground_weather"
PLATFORMS = ["weather"]

async def async_setup_entry(hass, config_entry):
    """Set up Wunderground Weather from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    # Set up
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True

async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(config_entry.entry_id)
    return await hass.config_entries.async_forward_entry_unload(config_entry, PLATFORMS)
"""Initialize the Wunderground Weather integration."""
