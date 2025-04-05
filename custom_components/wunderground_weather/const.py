DOMAIN = "wunderground_weather"
DEFAULT_UPDATE_INTERVAL = 60
CONF_STATION_ID = "station_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_STATION_NAME = "station_name"

# Sensor definitions
SENSOR_TYPES = {
    "temperature": ["Temperature", "°C", "mdi:thermometer"],
    "humidity": ["Humidity", "%", "mdi:water-percent"],
    "pressure": ["Pressure", "hPa", "mdi:gauge"],
    "wind_speed": ["Wind Speed", "km/h", "mdi:weather-windy"],
    "wind_gust": ["Wind Gust", "km/h", "mdi:weather-windy"],
    "wind_bearing": ["Wind Bearing", "°", "mdi:compass"],
    "dew_point": ["Dew Point", "°C", "mdi:water"],
    "solar_radiation": ["Solar Radiation", "W/m²", "mdi:white-balance-sunny"],
    "uv": ["UV Index", "", "mdi:weather-sunny"],
    "precip_rate": ["Precipitation Rate", "mm/h", "mdi:water"],
    "precip_total": ["Precipitation Total", "mm", "mdi:water"],
}