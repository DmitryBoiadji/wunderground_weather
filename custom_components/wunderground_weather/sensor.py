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
import logging

from .const import (
    DOMAIN,
    SENSOR_TYPES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

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
        self._station_name = coordinator.config_entry.data.get("station_name", f"Station {station_id}")
        self._attr_name = f"{SENSOR_TYPES[sensor_type][0]} {self._station_name}"
        self._attr_unique_id = f"{station_id}_{sensor_type}"
        self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._attr_icon = SENSOR_TYPES[sensor_type][2]

    @property
    def _data(self):
        """Get the processed data from coordinator."""
        if not self.coordinator.data:
            return None
            
        data = self.coordinator.data
        # Handle the case where data might be in observations array
        if "observations" in data and isinstance(data["observations"], list) and len(data["observations"]) > 0:
            return data["observations"][0]
        return data

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data = self._data
        if not data:
            return None

        # Check if data is in the expected format
        if not isinstance(data, dict):
            _LOGGER.warning("Unexpected data format: %s", data)
            return None
            
        metric = data.get("metric", {})

        try:
            if self._sensor_type == "temperature":
                value = metric.get("temp")
                return float(value) if value is not None else None
            elif self._sensor_type == "humidity":
                value = data.get("humidity")
                return float(value) if value is not None else None
            elif self._sensor_type == "pressure":
                value = metric.get("pressure")
                return float(value) if value is not None else None
            elif self._sensor_type == "wind_speed":
                value = metric.get("windSpeed")
                return float(value) if value is not None else None
            elif self._sensor_type == "wind_gust":
                value = metric.get("windGust")
                return float(value) if value is not None else None
            elif self._sensor_type == "wind_bearing":
                value = data.get("winddir")
                return float(value) if value is not None else None
            elif self._sensor_type == "dew_point":
                value = metric.get("dewpt")
                return float(value) if value is not None else None
            elif self._sensor_type == "solar_radiation":
                value = data.get("solarRadiation")
                return float(value) if value is not None else None
            elif self._sensor_type == "uv":
                value = data.get("uv")
                return float(value) if value is not None else None
            elif self._sensor_type == "precip_rate":
                value = metric.get("precipRate")
                return float(value) if value is not None else None
            elif self._sensor_type == "precip_total":
                value = metric.get("precipTotal")
                return float(value) if value is not None else None
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Error converting sensor value to number: %s", e)
            return None
        
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