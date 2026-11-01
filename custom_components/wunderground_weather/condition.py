"""Map weather data to Home Assistant weather conditions."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any

from astral import Observer
from astral.sun import elevation
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.util import dt as dt_util

from .api import to_float

# weather.com icon codes (iconCode field) to Home Assistant conditions
ICON_CONDITIONS: dict[int, str] = {
    0: ATTR_CONDITION_EXCEPTIONAL,  # Tornado
    1: ATTR_CONDITION_EXCEPTIONAL,  # Tropical storm
    2: ATTR_CONDITION_EXCEPTIONAL,  # Hurricane
    3: ATTR_CONDITION_LIGHTNING_RAINY,  # Strong storms
    4: ATTR_CONDITION_LIGHTNING_RAINY,  # Thunderstorms
    5: ATTR_CONDITION_SNOWY_RAINY,  # Rain and snow
    6: ATTR_CONDITION_SNOWY_RAINY,  # Rain and sleet
    7: ATTR_CONDITION_SNOWY_RAINY,  # Wintry mix
    8: ATTR_CONDITION_SNOWY_RAINY,  # Freezing drizzle
    9: ATTR_CONDITION_RAINY,  # Drizzle
    10: ATTR_CONDITION_SNOWY_RAINY,  # Freezing rain
    11: ATTR_CONDITION_RAINY,  # Showers
    12: ATTR_CONDITION_RAINY,  # Rain
    13: ATTR_CONDITION_SNOWY,  # Flurries
    14: ATTR_CONDITION_SNOWY,  # Snow showers
    15: ATTR_CONDITION_SNOWY,  # Blowing or drifting snow
    16: ATTR_CONDITION_SNOWY,  # Snow
    17: ATTR_CONDITION_HAIL,  # Hail
    18: ATTR_CONDITION_SNOWY_RAINY,  # Sleet
    19: ATTR_CONDITION_EXCEPTIONAL,  # Blowing dust or sandstorm
    20: ATTR_CONDITION_FOG,  # Foggy
    21: ATTR_CONDITION_FOG,  # Haze
    22: ATTR_CONDITION_FOG,  # Smoke
    23: ATTR_CONDITION_WINDY,  # Breezy
    24: ATTR_CONDITION_WINDY,  # Windy
    25: ATTR_CONDITION_SNOWY,  # Frigid or ice crystals
    26: ATTR_CONDITION_CLOUDY,  # Cloudy
    27: ATTR_CONDITION_CLOUDY,  # Mostly cloudy (night)
    28: ATTR_CONDITION_CLOUDY,  # Mostly cloudy (day)
    29: ATTR_CONDITION_PARTLYCLOUDY,  # Partly cloudy (night)
    30: ATTR_CONDITION_PARTLYCLOUDY,  # Partly cloudy (day)
    31: ATTR_CONDITION_CLEAR_NIGHT,  # Clear (night)
    32: ATTR_CONDITION_SUNNY,  # Sunny
    33: ATTR_CONDITION_CLEAR_NIGHT,  # Fair (night)
    34: ATTR_CONDITION_SUNNY,  # Fair (day)
    35: ATTR_CONDITION_HAIL,  # Mixed rain and hail
    36: ATTR_CONDITION_SUNNY,  # Hot
    37: ATTR_CONDITION_LIGHTNING_RAINY,  # Isolated thunderstorms
    38: ATTR_CONDITION_LIGHTNING_RAINY,  # Scattered thunderstorms
    39: ATTR_CONDITION_RAINY,  # Scattered showers (day)
    40: ATTR_CONDITION_POURING,  # Heavy rain
    41: ATTR_CONDITION_SNOWY,  # Scattered snow showers (day)
    42: ATTR_CONDITION_SNOWY,  # Heavy snow
    43: ATTR_CONDITION_SNOWY,  # Blizzard
    45: ATTR_CONDITION_RAINY,  # Scattered showers (night)
    46: ATTR_CONDITION_SNOWY,  # Scattered snow showers (night)
    47: ATTR_CONDITION_LIGHTNING_RAINY,  # Scattered thunderstorms (night)
}

PRECIPITATION_CONDITIONS = frozenset(
    {
        ATTR_CONDITION_HAIL,
        ATTR_CONDITION_LIGHTNING_RAINY,
        ATTR_CONDITION_POURING,
        ATTR_CONDITION_RAINY,
        ATTR_CONDITION_SNOWY,
        ATTR_CONDITION_SNOWY_RAINY,
    }
)

# Heavy rain starts at 7.6 mm/h (American Meteorological Society)
HEAVY_RAIN_RATE = 7.6
# Strong breeze (Beaufort 6) starts at 39 km/h
WINDY_SPEED = 39.0
FOG_HUMIDITY = 97.0
# Below this sun elevation (degrees) irradiance says little about clouds
MIN_SUN_ELEVATION = 5.0
# Ratio of measured to clear sky irradiance
SUNNY_RATIO = 0.75
PARTLYCLOUDY_RATIO = 0.4
# Ignore weather.com conditions that were not refreshed for this long
CONDITIONS_MAX_AGE = timedelta(hours=2)


def condition_from_icon(icon_code: Any, is_day: bool = True) -> str | None:
    """Return the Home Assistant condition for a weather.com icon code."""
    if icon_code is None:
        return None
    try:
        condition = ICON_CONDITIONS.get(int(icon_code))
    except (TypeError, ValueError):
        return None
    if condition == ATTR_CONDITION_SUNNY and not is_day:
        return ATTR_CONDITION_CLEAR_NIGHT
    return condition


def precipitation_condition(rate: float, temperature: float | None) -> str:
    """Return the condition for precipitation measured by the station."""
    if temperature is not None:
        if temperature <= 0:
            return ATTR_CONDITION_SNOWY
        if temperature <= 2:
            return ATTR_CONDITION_SNOWY_RAINY
    return ATTR_CONDITION_POURING if rate >= HEAVY_RAIN_RATE else ATTR_CONDITION_RAINY


def clear_sky_irradiance(sun_elevation: float) -> float:
    """Return the Haurwitz clear sky global horizontal irradiance in W/m2."""
    if sun_elevation <= 0:
        return 0.0
    sine = math.sin(math.radians(sun_elevation))
    return 1098.0 * sine * math.exp(-0.057 / sine)


def estimate_condition(observation: dict[str, Any], now: datetime) -> str | None:
    """Estimate the condition from station sensors only.

    Used when weather.com conditions are not available. Returns None when the
    sensors do not allow a reasonable guess (for example at night).
    """
    metric = observation.get("metric") or {}
    humidity = to_float(observation.get("humidity"))
    wind_speed = to_float(metric.get("windSpeed"))

    if humidity is not None and humidity >= FOG_HUMIDITY:
        return ATTR_CONDITION_FOG

    sky = _estimate_sky(observation, now)
    if wind_speed is not None and wind_speed >= WINDY_SPEED:
        return (
            ATTR_CONDITION_WINDY_VARIANT
            if sky == ATTR_CONDITION_CLOUDY
            else ATTR_CONDITION_WINDY
        )
    return sky


def _estimate_sky(observation: dict[str, Any], now: datetime) -> str | None:
    """Estimate cloudiness by comparing irradiance with a clear sky model."""
    solar = to_float(observation.get("solarRadiation"))
    latitude = to_float(observation.get("lat"))
    longitude = to_float(observation.get("lon"))
    if solar is None or latitude is None or longitude is None:
        return None

    sun_elevation = elevation(Observer(latitude=latitude, longitude=longitude), now)
    if sun_elevation < MIN_SUN_ELEVATION:
        return None

    ratio = solar / clear_sky_irradiance(sun_elevation)
    if ratio >= SUNNY_RATIO:
        return ATTR_CONDITION_SUNNY
    if ratio >= PARTLYCLOUDY_RATIO:
        return ATTR_CONDITION_PARTLYCLOUDY
    return ATTR_CONDITION_CLOUDY


def current_condition(
    observation: dict[str, Any],
    conditions: dict[str, Any] | None,
    now: datetime,
) -> str | None:
    """Return the current condition at the station.

    weather.com conditions are preferred. The station rain gauge overrides
    them when it measures precipitation that weather.com does not report.
    Station sensors are used as a fallback.
    """
    metric = observation.get("metric") or {}
    rate = to_float(metric.get("precipRate"))

    reported = None
    if conditions and _is_fresh(conditions, now):
        reported = condition_from_icon(
            conditions.get("iconCode"), conditions.get("dayOrNight") != "N"
        )

    if rate is not None and rate > 0:
        if reported in PRECIPITATION_CONDITIONS:
            return reported
        return precipitation_condition(rate, to_float(metric.get("temp")))
    if reported is not None:
        return reported
    return estimate_condition(observation, now)


def _is_fresh(conditions: dict[str, Any], now: datetime) -> bool:
    """Return True if weather.com conditions are recent enough to use."""
    if (timestamp := to_float(conditions.get("validTimeUtc"))) is None:
        return True
    return now - dt_util.utc_from_timestamp(timestamp) <= CONDITIONS_MAX_AGE
