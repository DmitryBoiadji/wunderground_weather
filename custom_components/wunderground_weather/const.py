"""Constants for the Wunderground Weather integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "wunderground_weather"
LOGGER = logging.getLogger(__package__)

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Observation polling interval in seconds
DEFAULT_UPDATE_INTERVAL: Final = 60
MIN_UPDATE_INTERVAL: Final = 30
MAX_UPDATE_INTERVAL: Final = 3600

# Current conditions and forecasts change slowly, poll them less often
FORECAST_UPDATE_INTERVAL: Final = timedelta(minutes=15)
# Keep serving forecasts this long when weather.com polls fail
DAILY_FORECAST_MAX_AGE: Final = timedelta(hours=6)
HOURLY_FORECAST_MAX_AGE: Final = timedelta(hours=2)

# A station that has not reported for this long is considered offline
STALE_OBSERVATION_AGE: Final = timedelta(hours=1)

ATTRIBUTION: Final = "Data provided by Weather Underground"
MANUFACTURER: Final = "Weather Underground"
DASHBOARD_URL: Final = "https://www.wunderground.com/dashboard/pws/{station_id}"
