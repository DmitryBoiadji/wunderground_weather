"""Convert weather.com forecasts to Home Assistant forecasts."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.weather import Forecast
from homeassistant.util import dt as dt_util

from .api import to_float
from .condition_mapping import condition_from_icon

# Daily entries are stamped 07:00 local time, so the calendar day ends 17 hours later
DAY_REMAINDER = timedelta(hours=17)
DAYPART_LENGTH = timedelta(hours=12)
HOUR = timedelta(hours=1)


def _at(values: Any, index: int) -> Any:
    """Return values[index] or None for missing lists and indexes."""
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return None


def _int(value: Any) -> int | None:
    """Return a numeric value rounded to int."""
    number = to_float(value)
    return None if number is None else round(number)


def _forecast(**values: Any) -> Forecast:
    """Build a forecast entry without empty values."""
    return Forecast(
        **{key: value for key, value in values.items() if value is not None}
    )  # type: ignore[typeddict-item]


def _daypart(data: dict[str, Any]) -> dict[str, Any]:
    """Return the day part block of a daily forecast."""
    dayparts = data.get("daypart")
    if isinstance(dayparts, list) and dayparts and isinstance(dayparts[0], dict):
        return dayparts[0]
    return {}


def daily_forecast(data: dict[str, Any] | None, now: datetime) -> list[Forecast]:
    """Return the daily forecast, one entry per calendar day."""
    if not data:
        return []
    daypart = _daypart(data)
    forecasts: list[Forecast] = []
    for index, timestamp in enumerate(data.get("validTimeUtc") or []):
        if timestamp is None:
            continue
        start = dt_util.utc_from_timestamp(timestamp)
        if start + DAY_REMAINDER <= now:
            continue
        day, night = 2 * index, 2 * index + 1
        # The day part of today disappears in the evening, use the night then
        part = day if _at(daypart.get("iconCode"), day) is not None else night
        chances = [
            chance
            for chance in (
                _int(_at(daypart.get("precipChance"), day)),
                _int(_at(daypart.get("precipChance"), night)),
            )
            if chance is not None
        ]
        forecasts.append(
            _forecast(
                datetime=start.isoformat(),
                condition=condition_from_icon(
                    _at(daypart.get("iconCode"), part), is_day=part == day
                ),
                native_temperature=to_float(
                    _at(data.get("calendarDayTemperatureMax"), index)
                ),
                native_templow=to_float(
                    _at(data.get("calendarDayTemperatureMin"), index)
                ),
                native_precipitation=to_float(_at(data.get("qpf"), index)),
                precipitation_probability=max(chances) if chances else None,
                native_wind_speed=to_float(_at(daypart.get("windSpeed"), part)),
                wind_bearing=to_float(_at(daypart.get("windDirection"), part)),
                humidity=_int(_at(daypart.get("relativeHumidity"), part)),
                uv_index=to_float(_at(daypart.get("uvIndex"), part)),
                cloud_coverage=_int(_at(daypart.get("cloudCover"), part)),
            )
        )
    return forecasts


def twice_daily_forecast(data: dict[str, Any] | None, now: datetime) -> list[Forecast]:
    """Return the forecast split into day and night parts."""
    if not data:
        return []
    daypart = _daypart(data)
    forecasts: list[Forecast] = []
    for index, timestamp in enumerate(data.get("validTimeUtc") or []):
        if timestamp is None:
            continue
        day_start = dt_util.utc_from_timestamp(timestamp)
        for part, start, is_day in (
            (2 * index, day_start, True),
            (2 * index + 1, day_start + DAYPART_LENGTH, False),
        ):
            if _at(daypart.get("iconCode"), part) is None:
                continue
            if start + DAYPART_LENGTH <= now:
                continue
            forecasts.append(
                _forecast(
                    datetime=start.isoformat(),
                    is_daytime=is_day,
                    condition=condition_from_icon(
                        _at(daypart.get("iconCode"), part), is_day=is_day
                    ),
                    native_temperature=to_float(_at(daypart.get("temperature"), part)),
                    native_precipitation=to_float(_at(daypart.get("qpf"), part)),
                    precipitation_probability=_int(
                        _at(daypart.get("precipChance"), part)
                    ),
                    native_wind_speed=to_float(_at(daypart.get("windSpeed"), part)),
                    wind_bearing=to_float(_at(daypart.get("windDirection"), part)),
                    humidity=_int(_at(daypart.get("relativeHumidity"), part)),
                    uv_index=to_float(_at(daypart.get("uvIndex"), part)),
                    cloud_coverage=_int(_at(daypart.get("cloudCover"), part)),
                )
            )
    return forecasts


def hourly_forecast(data: dict[str, Any] | None, now: datetime) -> list[Forecast]:
    """Return the hourly forecast."""
    if not data:
        return []
    forecasts: list[Forecast] = []
    for index, timestamp in enumerate(data.get("validTimeUtc") or []):
        if timestamp is None:
            continue
        start = dt_util.utc_from_timestamp(timestamp)
        if start + HOUR <= now:
            continue
        forecasts.append(
            _forecast(
                datetime=start.isoformat(),
                condition=condition_from_icon(
                    _at(data.get("iconCode"), index),
                    is_day=_at(data.get("dayOrNight"), index) != "N",
                ),
                native_temperature=to_float(_at(data.get("temperature"), index)),
                native_apparent_temperature=to_float(
                    _at(data.get("temperatureFeelsLike"), index)
                ),
                native_dew_point=to_float(_at(data.get("temperatureDewPoint"), index)),
                humidity=_int(_at(data.get("relativeHumidity"), index)),
                native_precipitation=to_float(_at(data.get("qpf"), index)),
                precipitation_probability=_int(_at(data.get("precipChance"), index)),
                native_pressure=to_float(_at(data.get("pressureMeanSeaLevel"), index)),
                native_wind_speed=to_float(_at(data.get("windSpeed"), index)),
                native_wind_gust_speed=to_float(_at(data.get("windGust"), index)),
                wind_bearing=to_float(_at(data.get("windDirection"), index)),
                uv_index=to_float(_at(data.get("uvIndex"), index)),
                cloud_coverage=_int(_at(data.get("cloudCover"), index)),
            )
        )
    return forecasts
