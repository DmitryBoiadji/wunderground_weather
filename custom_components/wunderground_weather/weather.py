"""Weather entity for Wunderground Weather."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import to_float
from .condition_mapping import current_condition, is_fresh_conditions
from .const import (
    ATTRIBUTION,
    DAILY_FORECAST_MAX_AGE,
    DOMAIN,
    HOURLY_FORECAST_MAX_AGE,
)
from .coordinator import (
    WundergroundConfigEntry,
    WundergroundData,
    WundergroundForecastCoordinator,
    WundergroundObservationCoordinator,
)
from .entity import station_device_info
from .forecast import daily_forecast, hourly_forecast, twice_daily_forecast

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WundergroundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Wunderground Weather entity from a config entry."""
    async_add_entities([WundergroundWeather(entry.runtime_data)])


class WundergroundWeather(
    CoordinatorWeatherEntity[
        WundergroundObservationCoordinator,
        WundergroundForecastCoordinator,
        WundergroundForecastCoordinator,
        WundergroundForecastCoordinator,
    ]
):
    """Station observations combined with weather.com conditions and forecasts."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, data: WundergroundData) -> None:
        """Initialize the weather entity."""
        super().__init__(
            data.observation,
            daily_coordinator=data.forecast,
            hourly_coordinator=data.forecast,
            twice_daily_coordinator=data.forecast,
            # Old parts of a forecast are dropped in forecast.py, so serve the
            # last successful forecast through short weather.com outages
            daily_forecast_valid=DAILY_FORECAST_MAX_AGE,
            hourly_forecast_valid=HOURLY_FORECAST_MAX_AGE,
            twice_daily_forecast_valid=DAILY_FORECAST_MAX_AGE,
        )
        self._forecast_coordinator = data.forecast
        # Same unique ID as earlier versions to keep the entity registry entry
        self._attr_unique_id = f"{DOMAIN}_{data.observation.station_id}"
        self._attr_device_info = station_device_info(data.observation)

    async def async_added_to_hass(self) -> None:
        """Keep the conditions coordinator polling while the entity exists."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._forecast_coordinator.async_add_listener(
                self._handle_conditions_update
            )
        )

    @callback
    def _handle_conditions_update(self) -> None:
        """Write the state when weather.com conditions change."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return False while the station is not reporting."""
        return super().available and not self.coordinator.is_stale

    @property
    def _observation(self) -> dict[str, Any]:
        """Return the latest station observation."""
        return self.coordinator.data or {}

    @property
    def _metric(self) -> dict[str, Any]:
        """Return the metric block of the observation."""
        return self._observation.get("metric") or {}

    @property
    def _conditions(self) -> dict[str, Any] | None:
        """Return weather.com current conditions, if known and recent."""
        data = self._forecast_coordinator.data
        if not data or not data.conditions:
            return None
        if not is_fresh_conditions(data.conditions, dt_util.utcnow()):
            return None
        return data.conditions

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return current_condition(self._observation, self._conditions, dt_util.utcnow())

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return to_float(self._metric.get("temp"))

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the feels like temperature."""
        temperature = to_float(self._metric.get("temp"))
        heat_index = to_float(self._metric.get("heatIndex"))
        wind_chill = to_float(self._metric.get("windChill"))
        if temperature is None:
            return None
        if heat_index is not None and heat_index > temperature:
            return heat_index
        if wind_chill is not None and wind_chill < temperature:
            return wind_chill
        return temperature

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return to_float(self._metric.get("dewpt"))

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        return to_float(self._observation.get("humidity"))

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return to_float(self._metric.get("pressure"))

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return to_float(self._metric.get("windSpeed"))

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return to_float(self._metric.get("windGust"))

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        return to_float(self._observation.get("winddir"))

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return to_float(self._observation.get("uv"))

    @property
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage reported by weather.com."""
        return to_float((self._conditions or {}).get("cloudCover"))

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility reported by weather.com."""
        return to_float((self._conditions or {}).get("visibility"))

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        data = self._forecast_coordinator.data
        return daily_forecast(data.daily if data else None, dt_util.utcnow())

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the day and night forecast."""
        data = self._forecast_coordinator.data
        return twice_daily_forecast(data.daily if data else None, dt_util.utcnow())

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        data = self._forecast_coordinator.data
        return hourly_forecast(data.hourly if data else None, dt_util.utcnow())
