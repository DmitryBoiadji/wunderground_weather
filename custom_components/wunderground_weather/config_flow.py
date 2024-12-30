from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL


class WundergroundWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wunderground Weather."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            station_id = user_input.get("station_id")

            if not station_id:
                errors["station_id"] = "invalid_station_id"
            else:
                return self.async_create_entry(
                    title=f"Station {station_id}",
                    data={"station_id": station_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("station_id"): str,
                    vol.Optional("update_interval", DEFAULT_UPDATE_INTERVAL): int,
                }
            ),
            errors=errors,
        )
