"""Config flow for Wunderground Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    WundergroundClient,
    WundergroundError,
    WundergroundStationNotFoundError,
    is_valid_station_id,
    normalize_station_id,
)
from .const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

UPDATE_INTERVAL_VALIDATOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATION_ID): str,
        vol.Optional(CONF_STATION_NAME): str,
        vol.Required(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): UPDATE_INTERVAL_VALIDATOR,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): UPDATE_INTERVAL_VALIDATOR,
    }
)


class WundergroundWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wunderground Weather."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WundergroundOptionsFlow:
        """Return the options flow."""
        return WundergroundOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the station and check that it reports data."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = normalize_station_id(user_input[CONF_STATION_ID])
            if not is_valid_station_id(station_id):
                errors[CONF_STATION_ID] = "invalid_station_id"
            else:
                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()

                client = WundergroundClient(
                    async_get_clientsession(self.hass), station_id
                )
                try:
                    observation = await client.async_get_observation()
                except WundergroundStationNotFoundError:
                    errors[CONF_STATION_ID] = "station_not_found"
                except WundergroundError as err:
                    LOGGER.debug("Cannot reach Weather Underground: %s", err)
                    errors["base"] = "cannot_connect"
                except Exception:
                    LOGGER.exception("Unexpected error while checking the station")
                    errors["base"] = "unknown"
                else:
                    name = (
                        (user_input.get(CONF_STATION_NAME) or "").strip()
                        or observation.get("neighborhood")
                        or station_id
                    )
                    return self.async_create_entry(
                        title=name,
                        data={CONF_STATION_ID: station_id, CONF_STATION_NAME: name},
                        options={
                            CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL]
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )


class WundergroundOptionsFlow(OptionsFlow):
    """Handle Wunderground Weather options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the update interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
