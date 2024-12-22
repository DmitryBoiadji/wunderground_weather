from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS
import aiohttp
from bs4 import BeautifulSoup
import json
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wunderground_weather"


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

        _LOGGER.debug(f"Script tag content (decoded): {script_content[:500]}")  # Log first 500 characters

        try:
            json_data = json.loads(script_content)
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Error decoding JSON: {e}")
            raise ValueError("Failed to parse weather data from script tag!")

        api_key = json_data.get("process.env", {}).get("SUN_API_KEY")
        _LOGGER.info(f"API Key: {api_key}")

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
        return {"error": str(e)}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Wunderground Weather platform from a config entry."""
    station_id = config_entry.data["station_id"]
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    async_add_entities([WundergroundWeather(station_id, session)], True)


class WundergroundWeather(WeatherEntity):
    def __init__(self, station_id, session):
        """Initialize the weather entity."""
        self._station_id = station_id
        self._session = session
        self._data = {}

    # Example
    # apparent_temperature: 12.0
    # cloud_coverage: 0
    # dew_point: 5.0
    # humidity: 76
    # precipitation_unit: mm
    # pressure: 1019
    # pressure_unit: hPa
    # temperature: 14.2
    # temperature_unit: °C
    # uv_index: 2
    # visibility: 10
    # visibility_unit: km
    # wind_bearing: 260
    # wind_gust_speed: 51.56
    # wind_speed: 35.17
    # wind_speed_unit: km/h

    # data:
    # {
    #   'stationID': 'ICHIIN35',
    #   'obsTimeUtc': '2024-12-22T12:04:08Z',
    #   'obsTimeLocal': '2024-12-22 14:04:08',
    #   'neighborhood': 'Chișinău',
    #   'softwareType': 'EasyWeatherPro_V5.1.7',
    #   'country': 'MD',
    #   'solarRadiation': 53.4,
    #   'lon': 28.853941,
    #   'realtimeFrequency': None,
    #   'epoch': 1734869048,
    #   'lat': 47.006611,
    #   'uv': 0.0,
    #   'winddir': 279,
    #   'humidity': 86.0,
    #   'qcStatus': 1,
    #   'metric': {
    #     'temp': -0.6,
    #     'heatIndex': -0.6,
    #     'dewpt': -2.6,
    #     'windChill': -2.3,
    #     'windSpeed': 5.0,
    #     'windGust': 5.8,
    #     'pressure': 1001.19,
    #     'precipRate': 0.0,
    #     'precipTotal': 0.0,
    #     'elev': 20.4
    #   }
    # }

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"wunderground_weather_{self._station_id}"

    @property
    def name(self):
        return f"Wunderground Weather {self._station_id}"

    @property
    def humidity(self):
        return self._data.get("humidity")

    @property
    def native_temperature(self):
        return self._data.get("metric", {}).get("temp")

    @property
    def native_temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def native_wind_speed(self):
        return self._data.get("metric", {}).get("windSpeed")

    @property
    def native_wind_gust_speed(self):
        return self._data.get("metric", {}).get("windGust")

    @property
    def native_wind_speed_unit(self):
        return "km/h"

    @property
    def native_dew_point(self):
        return self._data.get("metric", {}).get("dew_point")

    @property
    def wind_bearing(self):
        return self._data.get("winddir", {})

    @property
    def condition(self):
        return map_condition(self._data)

    @property
    def uv_index(self):
        return self._data.get("uv", {})

    async def async_update(self):
        """Fetch data from the API."""
        _LOGGER.debug(f"Fetching weather data for station {self._station_id}")

        data = await fetch_weather_data(self._session, self._station_id)
        _LOGGER.debug(f"Script tag content (decoded): {str(data)}")

        if not data:
            _LOGGER.warning(f"No data fetched for station {self._station_id}")
            self._data = {}
        else:
            self._data = data.get('observations')[0]
            _LOGGER.debug(f"DATA : {str(self._data)}")
            _LOGGER.debug(f"TEST humidity : {str(self._data.get('humidity'))}")


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

    is_day = "06:00" <= obs_time.split(" ")[1] <= "18:00"

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
