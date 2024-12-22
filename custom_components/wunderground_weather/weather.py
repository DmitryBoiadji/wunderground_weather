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

    @property
    def name(self):
        return f"Wunderground Weather {self._station_id}"

    @property
    def temperature(self):
        if "error" in self._data:
            _LOGGER.error(f"Error in weather data: {self._data['error']}")
            return None
        return self._data.get("imperial", {}).get("tempAvg")

    @property
    def humidity(self):
        return self._data.get("humidityAvg")

    @property
    def wind_speed(self):
        return self._data.get("imperial", {}).get("windspeedAvg")

    @property
    def condition(self):
        return "Clear"

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    async def async_update(self):
        """Fetch data from the API."""
        _LOGGER.debug(f"Fetching weather data for station {self._station_id}")

        data = await fetch_weather_data(self._session, self._station_id)
        _LOGGER.debug(f"Script tag content (decoded): {data[:500]}")
        

        if not data:
            _LOGGER.warning(f"No data fetched for station {self._station_id}")
            self._data = {}
        else:
            self._data = data

