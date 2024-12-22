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
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", {"id": "app-root-state", "type": "application/json"})

        if not script_tag:
            raise ValueError("Weather data script tag not found!")

        json_data = json.loads(script_tag.string.replace("&q;", "\""))
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
        return {"error": str(e)}



async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Wunderground Weather platform from a config entry."""
    station_id = config_entry.data["station_id"]
    session = aiohttp.ClientSession()
    async_add_entities([WundergroundWeather(station_id, session)])

class WundergroundWeather(WeatherEntity):
    def __init__(self, station_id):
        self._station_id = station_id
        self._data = None

    @property
    def name(self):
        return f"Wunderground Weather {self._station_id}"

    @property
    def temperature(self):
        return self._data.get("imperial", {}).get("tempAvg")

    @property
    def humidity(self):
        return self._data.get("humidityAvg")

    @property
    def wind_speed(self):
        return self._data.get("imperial", {}).get("windspeedAvg")

    # @property
    # def condition(self):
    #     return "Clear"  

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    async def async_update(self):
        _LOGGER.info(f"Fetching weather data for station: {self._station_id}")
        self._data = await fetch_weather_data(self._session, self._station_id)

