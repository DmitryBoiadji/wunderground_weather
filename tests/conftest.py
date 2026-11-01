"""Fixtures for Wunderground Weather tests."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wunderground_weather.const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"

STATION_ID = "ITEST123"
API_KEY = "testkey0123456789abcdef01234567"
# Shortly after the observation in observation.json was reported
NOW = "2026-11-01T11:30:00+00:00"

DASHBOARD_URL = re.compile(r"^https://www\.wunderground\.com/dashboard/pws/")
OBSERVATION_URL = "https://api.weather.com/v2/pws/observations/current"
CONDITIONS_URL = "https://api.weather.com/v3/wx/observations/current"
DAILY_URL = "https://api.weather.com/v3/wx/forecast/daily/5day"
HOURLY_URL = "https://api.weather.com/v3/wx/forecast/hourly/2day"


def load_fixture(name: str) -> str:
    """Return the text of a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> Any:
    """Return a parsed JSON fixture."""
    return json.loads(load_fixture(name))


def mock_responses(
    aioclient_mock: AiohttpClientMocker,
    *,
    observation: dict[str, Any] | None = None,
    observation_status: int = 200,
    forecast_status: int = 200,
) -> None:
    """Register responses for all endpoints used by the integration."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(
        OBSERVATION_URL,
        status=observation_status,
        json=(
            (observation or load_json("observation.json"))
            if observation_status == 200
            else None
        ),
    )
    for url, fixture in (
        (CONDITIONS_URL, "conditions.json"),
        (DAILY_URL, "forecast_daily.json"),
        (HOURLY_URL, "forecast_hourly.json"),
    ):
        aioclient_mock.get(
            url,
            status=forecast_status,
            json=load_json(fixture) if forecast_status == 200 else None,
        )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable the custom integration in all tests."""


@pytest.fixture(autouse=True)
def frozen_time(freezer) -> None:
    """Freeze time close to the fixture observation time."""
    freezer.move_to(NOW)


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock all Weather Underground endpoints with fixture data."""
    mock_responses(aioclient_mock)
    return aioclient_mock


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry for the test station."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Town",
        unique_id=STATION_ID,
        version=1,
        minor_version=2,
        data={CONF_STATION_ID: STATION_ID, CONF_STATION_NAME: "Test Town"},
        options={CONF_UPDATE_INTERVAL: 60},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: AiohttpClientMocker
) -> MockConfigEntry:
    """Set up the integration with fixture data."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
