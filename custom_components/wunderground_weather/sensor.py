"""Support for Wunderground Weather sensors."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SENSOR_TYPES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wunderground Weather sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(
            WundergroundWeatherSensor(
                coordinator,
                config_entry.data["station_id"],
                sensor_type,
            )
        )
    
    async_add_entities(sensors, True)


class WundergroundWeatherSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Wunderground Weather sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, station_id: str, sensor_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._sensor_type = sensor_type
        self._attr_name = f"{SENSOR_TYPES[sensor_type][0]} {station_id}"
        self._attr_unique_id = f"{station_id}_{sensor_type}"
        self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._attr_icon = SENSOR_TYPES[sensor_type][2]

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        data = self.coordinator.data
        metric = data.get("metric", {})

        if self._sensor_type == "temperature":
            return metric.get("temp")
        elif self._sensor_type == "humidity":
            return data.get("humidity")
        elif self._sensor_type == "pressure":
            return metric.get("pressure")
        elif self._sensor_type == "wind_speed":
            return metric.get("windSpeed")
        elif self._sensor_type == "wind_gust":
            return metric.get("windGust")
        elif self._sensor_type == "wind_bearing":
            return data.get("winddir")
        elif self._sensor_type == "dew_point":
            return metric.get("dewpt")
        elif self._sensor_type == "solar_radiation":
            return data.get("solarRadiation")
        elif self._sensor_type == "uv":
            return data.get("uv")
        elif self._sensor_type == "precip_rate":
            return metric.get("precipRate")
        elif self._sensor_type == "precip_total":
            return metric.get("precipTotal")
        
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        if self._sensor_type == "temperature":
            return SensorDeviceClass.TEMPERATURE
        elif self._sensor_type == "humidity":
            return SensorDeviceClass.HUMIDITY
        elif self._sensor_type == "pressure":
            return SensorDeviceClass.PRESSURE
        return None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class of the sensor."""
        if self._sensor_type in ["temperature", "pressure"]:
            return SensorStateClass.MEASUREMENT
        elif self._sensor_type == "humidity":
            return SensorStateClass.MEASUREMENT
        return None 