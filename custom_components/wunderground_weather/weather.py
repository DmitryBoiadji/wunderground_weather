from homeassistant.components.weather import WeatherEntity
from homeassistant.util.unit_system import UnitOfTemperature
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import aiohttp
from bs4 import BeautifulSoup
import json
import logging
import async_timeout
from datetime import timedelta

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

async def fetch_weather_data(session, station_id):
    """Fetch weather data asynchronously."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://www.wunderground.com/dashboard/pws/{station_id}"
    try:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            html_content = await response.text()

        soup = BeautifulSoup(html_content, "html.parser")
        script_tag = soup.find("script", {"id": "app-root-state", "type": "application/json"})

        if not script_tag or not script_tag.string.strip():
            raise ValueError("Script tag content is empty or missing!")

        script_content = script_tag.string.replace("&q;", "\"")

        try:
            json_data = json.loads(script_content)
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Error decoding JSON: {e}")
            raise ValueError("Failed to parse weather data from script tag!")

        api_key = json_data.get("process.env", {}).get("SUN_API_KEY")
        if not api_key:
            raise ValueError("API key not found in data!")

        api_url = (
            f"https://api.weather.com/v2/pws/observations/current?"
            f"apiKey={api_key}&stationId={station_id}&numericPrecision=decimal&format=json&units=m"
        )
        async with session.get(api_url) as api_response:
            api_response.raise_for_status()
            return await api_response.json()

    except Exception as e:
        _LOGGER.error(f"Error fetching weather data: {e}")
        return None

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Wunderground Weather platform from a config entry."""
    station_id = config_entry.data["station_id"]
    
    # Get the coordinator from hass data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Add the weather entity
    async_add_entities([WundergroundWeather(coordinator, station_id)], True)

class WundergroundWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, coordinator: DataUpdateCoordinator, station_id: str):
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._station_id = station_id

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"wunderground_weather_{self._station_id}"

    @property
    def name(self):
        return f"Wunderground Weather {self._station_id}"

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
    def humidity(self):
        """Return the humidity."""
        data = self._data
        return data.get("humidity") if data else None

    @property
    def native_temperature(self):
        """Return the temperature."""
        data = self._data
        return (
            data.get("metric", {}).get("temp")
            if data
            else None
        )

    @property
    def native_temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        data = self._data
        return (
            data.get("metric", {}).get("windSpeed")
            if data
            else None
        )

    @property
    def native_wind_gust_speed(self):
        """Return the wind gust speed."""
        data = self._data
        return (
            data.get("metric", {}).get("windGust")
            if data
            else None
        )

    @property
    def native_wind_speed_unit(self):
        """Return the unit of measurement for wind speed."""
        return "km/h"

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        data = self._data
        return data.get("winddir") if data else None

    @property
    def native_pressure(self):
        """Return the pressure."""
        data = self._data
        return (
            data.get("metric", {}).get("pressure")
            if data
            else None
        )

    @property
    def native_pressure_unit(self):
        """Return the unit of measurement for pressure."""
        return "hPa"

    @property
    def condition(self):
        """Return the weather condition."""
        data = self._data
        if not data:
            return None
        return map_condition(data)

def map_condition(data):
    """Map weather data to Home Assistant conditions."""
    metric = data.get("metric", {})
    temp = metric.get("temp", 0)
    humidity = data.get("humidity", 0)
    wind_speed = metric.get("windSpeed", 0)
    precip_rate = metric.get("precipRate", 0)
    solar_radiation = data.get("solarRadiation", 0)
    uv_index = data.get("uv", 0)
    obs_time = data.get("obsTimeLocal", "")

    # Ensure all values are numbers
    try:
        temp = float(temp) if temp is not None else 0
        humidity = float(humidity) if humidity is not None else 0
        wind_speed = float(wind_speed) if wind_speed is not None else 0
        precip_rate = float(precip_rate) if precip_rate is not None else 0
        solar_radiation = float(solar_radiation) if solar_radiation is not None else 0
        uv_index = float(uv_index) if uv_index is not None else 0
    except (ValueError, TypeError):
        _LOGGER.warning("Error converting weather values to numbers")
        temp = 0
        humidity = 0
        wind_speed = 0
        precip_rate = 0
        solar_radiation = 0
        uv_index = 0

    # Safely determine if it's day or night
    is_day = True  # Default to day
    try:
        if obs_time and " " in obs_time:
            time_parts = obs_time.split(" ")
            if len(time_parts) > 1:
                time_str = time_parts[1]
                if ":" in time_str:
                    hour_str = time_str.split(":")[0]
                    hour = int(hour_str)
                    is_day = 6 <= hour <= 18
    except (ValueError, IndexError):
        _LOGGER.warning("Could not parse observation time: %s", obs_time)

    if precip_rate > 0.0:
        if temp <= 0:
            return "snowy-rainy" if precip_rate > 0.1 else "snowy"
        return "pouring" if precip_rate > 5.0 else "rainy"

    if solar_radiation > 50 and is_day:
        return "sunny" if humidity < 70 else "partlycloudy"

    if humidity >= 95 and solar_radiation < 10:
        return "fog"

    if wind_speed > 20:
        return "windy-variant" if solar_radiation < 50 else "windy"

    if solar_radiation < 10 and not is_day:
        return "clear-night"

    if solar_radiation < 50:
        return "cloudy"

    return "exceptional"
