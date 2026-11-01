"""Data update coordinators for Wunderground Weather."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    WundergroundClient,
    WundergroundError,
    WundergroundStationNotFoundError,
)
from .const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FORECAST_UPDATE_INTERVAL,
    LOGGER,
    STALE_OBSERVATION_AGE,
)

type WundergroundConfigEntry = ConfigEntry[WundergroundData]


@dataclass(slots=True)
class WundergroundData:
    """Runtime data stored in the config entry."""

    client: WundergroundClient
    observation: WundergroundObservationCoordinator
    forecast: WundergroundForecastCoordinator


@dataclass(slots=True)
class ForecastData:
    """weather.com data for the station location, any part may be missing."""

    conditions: dict[str, Any] | None
    daily: dict[str, Any] | None
    hourly: dict[str, Any] | None


class WundergroundObservationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the latest observation of a personal weather station."""

    config_entry: WundergroundConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WundergroundConfigEntry,
        client: WundergroundClient,
    ) -> None:
        """Initialize the coordinator."""
        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.station_id}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        # Stored ID is used for unique IDs to keep existing entity registry entries
        self.station_id: str = entry.data[CONF_STATION_ID]
        self.station_name: str = entry.data.get(CONF_STATION_NAME) or entry.title

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest observation."""
        try:
            return await self.client.async_get_observation()
        except WundergroundStationNotFoundError as err:
            raise UpdateFailed(
                f"Station {self.client.station_id} is offline or does not exist"
            ) from err
        except WundergroundError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def observation_time(self) -> datetime | None:
        """Return when the station reported the current observation."""
        if not self.data or not (value := self.data.get("obsTimeUtc")):
            return None
        return dt_util.parse_datetime(value)

    @property
    def is_stale(self) -> bool:
        """Return True if the station stopped reporting."""
        observed = self.observation_time
        return observed is not None and (
            dt_util.utcnow() - observed > STALE_OBSERVATION_AGE
        )

    @property
    def location(self) -> tuple[float, float] | None:
        """Return the station latitude and longitude."""
        if not self.data:
            return None
        latitude, longitude = self.data.get("lat"), self.data.get("lon")
        if latitude is None or longitude is None:
            return None
        return float(latitude), float(longitude)


class WundergroundForecastCoordinator(TimestampDataUpdateCoordinator[ForecastData]):
    """Poll weather.com current conditions and forecasts for the station location."""

    config_entry: WundergroundConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WundergroundConfigEntry,
        client: WundergroundClient,
        observation: WundergroundObservationCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.station_id}_forecast",
            update_interval=FORECAST_UPDATE_INTERVAL,
        )
        self.client = client
        self._observation = observation

    async def _async_update_data(self) -> ForecastData:
        """Fetch conditions and forecasts, keeping old parts that failed."""
        if (location := self._observation.location) is None:
            raise UpdateFailed("Station location is not known yet")

        results = await asyncio.gather(
            self.client.async_get_conditions(*location),
            self.client.async_get_daily_forecast(*location),
            self.client.async_get_hourly_forecast(*location),
            return_exceptions=True,
        )
        errors: list[WundergroundError] = []
        for result in results:
            if isinstance(result, WundergroundError):
                errors.append(result)
            elif isinstance(result, BaseException):
                raise result
        if len(errors) == len(results):
            raise UpdateFailed(f"Forecast update failed: {errors[0]}") from errors[0]
        for error in errors:
            LOGGER.debug("Part of the forecast update failed: %s", error)

        previous = self.data
        parts: list[dict[str, Any] | None] = []
        for field, result in zip(
            ("conditions", "daily", "hourly"), results, strict=True
        ):
            if isinstance(result, BaseException):
                parts.append(getattr(previous, field) if previous else None)
            else:
                parts.append(result)
        return ForecastData(conditions=parts[0], daily=parts[1], hourly=parts[2])
