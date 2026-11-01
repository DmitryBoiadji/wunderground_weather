"""Tests for the Weather Underground API client."""

from __future__ import annotations

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wunderground_weather.api import (
    WundergroundApiKeyError,
    WundergroundClient,
    WundergroundConnectionError,
    WundergroundStationNotFoundError,
    extract_api_key,
)

from .conftest import (
    API_KEY,
    DASHBOARD_URL,
    OBSERVATION_URL,
    load_fixture,
    load_json,
)


def _client(hass: HomeAssistant, station_id: str = "itest123 ") -> WundergroundClient:
    return WundergroundClient(async_get_clientsession(hass), station_id)


def test_extract_api_key_current_markup() -> None:
    """The key is found in the inline script of the current page."""
    assert extract_api_key(load_fixture("dashboard.html")) == API_KEY


def test_extract_api_key_legacy_markup() -> None:
    """The key is found in the legacy app-root-state block."""
    assert (
        extract_api_key(load_fixture("dashboard_legacy.html"))
        == "legacykey0123456789abcdef012345"
    )


def test_extract_api_key_missing() -> None:
    """Pages without a key return None."""
    assert extract_api_key("<html><body>Nothing here</body></html>") is None


async def test_observation_and_key_cache(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The dashboard page is fetched once and the key is reused."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(
        f"{OBSERVATION_URL}?apiKey={API_KEY}&stationId=ITEST123",
        json=load_json("observation.json"),
    )
    client = _client(hass)

    first = await client.async_get_observation()
    second = await client.async_get_observation()

    assert client.station_id == "ITEST123"
    assert first["stationID"] == "ITEST123"
    assert second == first
    page_calls = [
        call for call in aioclient_mock.mock_calls if "dashboard" in str(call[1])
    ]
    assert len(page_calls) == 1
    assert aioclient_mock.call_count == 3


async def test_rejected_key_is_refreshed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected key triggers one new page fetch and a retry."""
    aioclient_mock.get(
        DASHBOARD_URL, text=load_fixture("dashboard.html").replace(API_KEY, "oldkey")
    )
    aioclient_mock.get(
        f"{OBSERVATION_URL}?apiKey=oldkey", json=load_json("observation.json")
    )
    client = _client(hass)
    await client.async_get_observation()

    # The site rotated its key: the old one is rejected, the page has a new one
    aioclient_mock.clear_requests()
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(
        f"{OBSERVATION_URL}?apiKey=oldkey", status=401, text="apikey is not authorized"
    )
    aioclient_mock.get(
        f"{OBSERVATION_URL}?apiKey={API_KEY}", json=load_json("observation.json")
    )

    observation = await client.async_get_observation()

    assert observation["stationID"] == "ITEST123"
    urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert len([url for url in urls if "dashboard" in url]) == 1
    assert len(urls) == 3


async def test_key_rejected_twice(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """If the fresh key is rejected as well, an API key error is raised."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(OBSERVATION_URL, status=401)

    with pytest.raises(WundergroundApiKeyError):
        await _client(hass).async_get_observation()


async def test_key_not_on_page(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A page without a key raises an API key error."""
    aioclient_mock.get(DASHBOARD_URL, text="<html></html>")

    with pytest.raises(WundergroundApiKeyError, match="markup may have changed"):
        await _client(hass).async_get_observation()


@pytest.mark.parametrize(
    "response",
    [{"status": 204}, {"json": {"observations": []}}],
)
async def test_station_without_observations(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict
) -> None:
    """HTTP 204 or an empty list means the station is offline or unknown."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(OBSERVATION_URL, **response)

    with pytest.raises(WundergroundStationNotFoundError):
        await _client(hass).async_get_observation()


async def test_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Timeouts are reported as connection errors."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(OBSERVATION_URL, exc=TimeoutError())

    with pytest.raises(WundergroundConnectionError, match="TimeoutError"):
        await _client(hass).async_get_observation()


async def test_errors_do_not_leak_the_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The API key is removed from error messages."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(
        OBSERVATION_URL,
        exc=aiohttp.ClientError(f"failed for {OBSERVATION_URL}?apiKey={API_KEY}"),
    )

    with pytest.raises(WundergroundConnectionError) as err:
        await _client(hass).async_get_observation()
    assert API_KEY not in str(err.value)
    assert "***" in str(err.value)


async def test_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Unexpected HTTP statuses are connection errors."""
    aioclient_mock.get(DASHBOARD_URL, text=load_fixture("dashboard.html"))
    aioclient_mock.get(OBSERVATION_URL, status=500)

    with pytest.raises(WundergroundConnectionError, match="HTTP 500"):
        await _client(hass).async_get_observation()


async def test_dashboard_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failing dashboard page is a connection error."""
    aioclient_mock.get(DASHBOARD_URL, status=503)

    with pytest.raises(WundergroundConnectionError, match="HTTP 503"):
        await _client(hass).async_get_observation()
