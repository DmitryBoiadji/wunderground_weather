from homeassistant import config_entries
import voluptuous as vol
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_STATION_ID,
    CONF_UPDATE_INTERVAL,
)


class WundergroundWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wunderground Weather."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            station_id = user_input.get(CONF_STATION_ID)
            update_interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

            if not station_id:
                errors[CONF_STATION_ID] = "invalid_station_id"
            else:
                # Check if this station is already configured
                for entry in self._async_current_entries():
                    if entry.data.get(CONF_STATION_ID) == station_id:
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=f"Station {station_id}",
                    data={
                        CONF_STATION_ID: station_id,
                        CONF_UPDATE_INTERVAL: update_interval,
                    },
                    options={
                        CONF_UPDATE_INTERVAL: update_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): str,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=DEFAULT_UPDATE_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import config from configuration.yaml."""
        return await self.async_step_user(import_data)
