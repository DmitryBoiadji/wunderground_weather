"""Tests for the condition mapping."""

from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util
import pytest

from custom_components.wunderground_weather.condition_mapping import (
    condition_from_icon,
    current_condition,
    estimate_condition,
    precipitation_condition,
)
from custom_components.wunderground_weather.forecast import (
    daily_forecast,
    twice_daily_forecast,
)

from .conftest import load_json

# Berlin, summer
LAT, LON = 52.52, 13.40


def _observation(
    *,
    solar: float | None = 0.0,
    humidity: float = 60.0,
    wind: float = 5.0,
    precip: float = 0.0,
    temp: float = 20.0,
) -> dict:
    return {
        "lat": LAT,
        "lon": LON,
        "humidity": humidity,
        "solarRadiation": solar,
        "metric": {
            "temp": temp,
            "dewpt": temp - 5,
            "windSpeed": wind,
            "precipRate": precip,
        },
    }


def _utc(value: str) -> datetime:
    return dt_util.parse_datetime(value)


@pytest.mark.parametrize(
    ("code", "is_day", "expected"),
    [
        (32, True, "sunny"),
        (36, False, "clear-night"),
        (31, False, "clear-night"),
        (30, True, "partlycloudy"),
        (26, True, "cloudy"),
        (4, True, "lightning-rainy"),
        (40, True, "pouring"),
        (16, True, "snowy"),
        (17, True, "hail"),
        (20, True, "fog"),
        (44, True, None),
        (None, True, None),
        ("bad", True, None),
    ],
)
def test_condition_from_icon(code, is_day: bool, expected: str | None) -> None:
    """weather.com icon codes map to Home Assistant conditions."""
    assert condition_from_icon(code, is_day) == expected


@pytest.mark.parametrize(
    ("rate", "temp", "expected"),
    [
        (0.5, 10.0, "rainy"),
        (8.0, 10.0, "pouring"),
        (0.5, 1.0, "snowy-rainy"),
        (0.5, -3.0, "snowy"),
        (8.0, -3.0, "snowy"),
        (0.5, None, "rainy"),
    ],
)
def test_precipitation_condition(
    rate: float, temp: float | None, expected: str
) -> None:
    """Measured precipitation is classified by rate and temperature."""
    assert precipitation_condition(rate, temp) == expected


@pytest.mark.parametrize(
    ("moment", "solar", "expected"),
    [
        # Summer evening with sunshine, earlier versions returned "exceptional"
        ("2026-07-01T17:30:00+00:00", 250.0, "sunny"),
        # Early morning, low sun
        ("2026-07-01T04:30:00+00:00", 160.0, "sunny"),
        # Sun just above the horizon, too low to judge
        ("2026-07-01T03:30:00+00:00", 30.0, None),
        ("2026-07-01T11:00:00+00:00", 850.0, "sunny"),
        ("2026-07-01T11:00:00+00:00", 500.0, "partlycloudy"),
        ("2026-07-01T11:00:00+00:00", 150.0, "cloudy"),
        # Night: clouds cannot be judged from irradiance
        ("2026-07-01T23:00:00+00:00", 0.0, None),
        # Station without a solar sensor
        ("2026-07-01T11:00:00+00:00", None, None),
    ],
)
def test_estimate_condition(
    moment: str, solar: float | None, expected: str | None
) -> None:
    """Sky estimation compares irradiance with the clear sky model."""
    assert estimate_condition(_observation(solar=solar), _utc(moment)) == expected


def test_estimate_condition_fog_and_wind() -> None:
    """Fog and wind are detected from humidity and wind speed."""
    noon = _utc("2026-07-01T11:00:00+00:00")
    assert estimate_condition(_observation(humidity=98.0), noon) == "fog"
    assert estimate_condition(_observation(solar=850.0, wind=45.0), noon) == "windy"
    assert (
        estimate_condition(_observation(solar=150.0, wind=45.0), noon)
        == "windy-variant"
    )
    assert (
        estimate_condition(_observation(wind=45.0), _utc("2026-07-01T23:00:00+00:00"))
        == "windy"
    )


def test_current_condition_priorities() -> None:
    """weather.com wins, station rain overrides a dry report, sensors are the fallback."""
    noon = _utc("2026-07-01T11:00:00+00:00")
    fresh = {"iconCode": 30, "dayOrNight": "D", "validTimeUtc": noon.timestamp() - 600}
    storm = {"iconCode": 4, "dayOrNight": "D", "validTimeUtc": noon.timestamp() - 600}
    stale = {
        "iconCode": 30,
        "dayOrNight": "D",
        "validTimeUtc": noon.timestamp() - 3 * 3600,
    }

    dry = _observation(solar=850.0)
    wet = _observation(solar=150.0, precip=1.2)

    assert current_condition(dry, fresh, noon) == "partlycloudy"
    assert current_condition(wet, fresh, noon) == "rainy"
    assert current_condition(wet, storm, noon) == "lightning-rainy"
    assert current_condition(dry, stale, noon) == "sunny"
    assert current_condition(dry, None, noon) == "sunny"


def test_daily_forecast_in_the_evening() -> None:
    """In the evening today's day part is gone, the night part is used."""
    data = load_json("forecast_daily.json")
    daypart = data["daypart"][0]
    for values in daypart.values():
        values[0] = None
    evening = dt_util.utc_from_timestamp(data["validTimeUtc"][0] + 13 * 3600)

    daily = daily_forecast(data, evening)
    assert len(daily) == 6
    assert daily[0]["condition"] == "clear-night"
    assert daily[0]["precipitation_probability"] == 8

    twice_daily = twice_daily_forecast(data, evening)
    assert len(twice_daily) == 11
    assert twice_daily[0]["is_daytime"] is False


def test_forecasts_skip_the_past() -> None:
    """Entries that already ended are not returned."""
    data = load_json("forecast_daily.json")
    next_day = dt_util.utc_from_timestamp(data["validTimeUtc"][1] + 3600)
    assert len(daily_forecast(data, next_day)) == 5
    assert daily_forecast(None, next_day) == []


def test_fog_needs_no_sunshine() -> None:
    """Saturated air in full sun is not reported as fog."""
    noon = _utc("2026-07-01T11:00:00+00:00")
    assert estimate_condition(_observation(humidity=98.0, solar=850.0), noon) == "sunny"
    assert estimate_condition(_observation(humidity=98.0, solar=150.0), noon) == "fog"
    night = _utc("2026-07-01T23:00:00+00:00")
    assert estimate_condition(_observation(humidity=98.0), night) == "fog"


def test_exceptional_wins_over_station_rain() -> None:
    """Station rain does not hide storms reported by weather.com."""
    noon = _utc("2026-07-01T11:00:00+00:00")
    tornado = {"iconCode": 0, "dayOrNight": "D", "validTimeUtc": noon.timestamp()}
    windy = {"iconCode": 24, "dayOrNight": "D", "validTimeUtc": noon.timestamp()}
    wet = _observation(precip=12.0)

    assert current_condition(wet, tornado, noon) == "exceptional"
    assert current_condition(wet, windy, noon) == "pouring"
