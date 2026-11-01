"""Sensors for Wunderground Weather."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .api import to_float
from .coordinator import WundergroundConfigEntry, WundergroundObservationCoordinator
from .entity import WundergroundEntity

# Entities are read-only views of coordinator data
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WundergroundSensorEntityDescription(SensorEntityDescription):
    """Describes a Wunderground Weather sensor."""

    value_fn: Callable[[dict[str, Any]], StateType | datetime]
    # Keep reporting while the station is stale (used for the timestamp sensor)
    available_when_stale: bool = False


def _field(key: str) -> Callable[[dict[str, Any]], float | None]:
    """Return a getter for a top level observation value."""
    return lambda observation: to_float(observation.get(key))


def _metric(key: str) -> Callable[[dict[str, Any]], float | None]:
    """Return a getter for a value of the metric block."""
    return lambda observation: to_float((observation.get("metric") or {}).get(key))


def _observation_time(observation: dict[str, Any]) -> datetime | None:
    """Return the observation time."""
    value = observation.get("obsTimeUtc")
    return dt_util.parse_datetime(value) if value else None


# Keys are part of unique IDs, do not rename them
SENSORS: tuple[WundergroundSensorEntityDescription, ...] = (
    WundergroundSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_metric("temp"),
    ),
    WundergroundSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_field("humidity"),
    ),
    WundergroundSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
        value_fn=_metric("pressure"),
    ),
    WundergroundSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_metric("windSpeed"),
    ),
    WundergroundSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_metric("windGust"),
    ),
    WundergroundSensorEntityDescription(
        key="wind_bearing",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=_field("winddir"),
    ),
    WundergroundSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_metric("dewpt"),
    ),
    WundergroundSensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_metric("heatIndex"),
    ),
    WundergroundSensorEntityDescription(
        key="wind_chill",
        translation_key="wind_chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_metric("windChill"),
    ),
    WundergroundSensorEntityDescription(
        key="solar_radiation",
        translation_key="solar_radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        suggested_display_precision=0,
        value_fn=_field("solarRadiation"),
    ),
    WundergroundSensorEntityDescription(
        key="uv",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        suggested_display_precision=1,
        value_fn=_field("uv"),
    ),
    WundergroundSensorEntityDescription(
        key="precip_rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_metric("precipRate"),
    ),
    WundergroundSensorEntityDescription(
        key="precip_total",
        translation_key="precipitation_today",
        device_class=SensorDeviceClass.PRECIPITATION,
        # The station resets the total at local midnight
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=_metric("precipTotal"),
    ),
    WundergroundSensorEntityDescription(
        key="last_observation",
        translation_key="last_observation",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        available_when_stale=True,
        value_fn=_observation_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WundergroundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wunderground Weather sensors from a config entry."""
    coordinator = entry.runtime_data.observation
    async_add_entities(
        WundergroundSensor(coordinator, description) for description in SENSORS
    )


class WundergroundSensor(WundergroundEntity, SensorEntity):
    """A single value reported by the weather station."""

    entity_description: WundergroundSensorEntityDescription

    def __init__(
        self,
        coordinator: WundergroundObservationCoordinator,
        description: WundergroundSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return False while the station is not reporting."""
        return super().available and (
            self.entity_description.available_when_stale
            or not self.coordinator.is_stale
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
