"""Client for the Weather Underground PWS and weather.com APIs."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import aiohttp

from .const import DASHBOARD_URL, LOGGER

API_BASE_URL = "https://api.weather.com"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

# The dashboard page is only served to browser-like clients
PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# Current page: inline script with `const data = {"API_KEY":"..."}`.
# Legacy page: app-root-state JSON with "SUN_API_KEY".
API_KEY_PATTERN = re.compile(r'"(?:SUN_)?API_KEY"\s*:\s*"([A-Za-z0-9]+)"')

STATION_ID_PATTERN = re.compile(r"^[A-Z0-9]+$")

HTTP_NO_CONTENT = 204
# Wait before scraping the page again when it gave no working key
KEY_RETRY_COOLDOWN = 600  # seconds
UNAUTHORIZED_STATUSES = frozenset({401, 403})


class WundergroundError(Exception):
    """Base error of the Weather Underground client."""


class WundergroundConnectionError(WundergroundError):
    """Network error, timeout or unexpected response."""


class WundergroundApiKeyError(WundergroundError):
    """The API key could not be found on the dashboard page or was rejected."""


class WundergroundStationNotFoundError(WundergroundError):
    """The station does not exist or has not reported recently."""


def normalize_station_id(station_id: str) -> str:
    """Return the station ID in the form the API expects (it is case sensitive)."""
    return station_id.strip().upper()


def is_valid_station_id(station_id: str) -> bool:
    """Return True if the normalized station ID looks like a PWS ID."""
    return bool(STATION_ID_PATTERN.match(station_id))


def extract_api_key(html: str) -> str | None:
    """Return the weather.com API key embedded in a dashboard page."""
    # The legacy Angular page encoded quotes as &q; inside app-root-state
    match = API_KEY_PATTERN.search(html.replace("&q;", '"'))
    return match.group(1) if match else None


def to_float(value: Any) -> float | None:
    """Return a numeric API value as float, or None if it is missing or invalid."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _describe(err: BaseException, secret: str | None = None) -> str:
    """Return a printable error description without the API key."""
    text = str(err) or type(err).__name__
    if secret:
        text = text.replace(secret, "***")
    return text


class WundergroundClient:
    """Fetch observations and forecasts for one personal weather station.

    The API key is scraped from the public dashboard page once and reused
    until the API rejects it, then it is fetched again. If the page has no
    working key, it is not loaded again for KEY_RETRY_COOLDOWN seconds.
    """

    def __init__(self, session: aiohttp.ClientSession, station_id: str) -> None:
        """Initialize the client."""
        self._session = session
        self.station_id = normalize_station_id(station_id)
        self._api_key: str | None = None
        self._api_key_lock = asyncio.Lock()
        self._key_retry_after: float | None = None

    async def async_get_observation(self) -> dict[str, Any]:
        """Return the latest observation of the station."""
        data = await self._async_request(
            "/v2/pws/observations/current",
            {
                "stationId": self.station_id,
                "numericPrecision": "decimal",
                "format": "json",
                "units": "m",
            },
        )
        observations = (data or {}).get("observations") or []
        if not observations:
            raise WundergroundStationNotFoundError(
                f"Station {self.station_id} has no current observations"
            )
        return observations[0]

    async def async_get_conditions(
        self, latitude: float, longitude: float
    ) -> dict[str, Any] | None:
        """Return weather.com current conditions for a location."""
        return await self._async_request(
            "/v3/wx/observations/current", _location_params(latitude, longitude)
        )

    async def async_get_daily_forecast(
        self, latitude: float, longitude: float
    ) -> dict[str, Any] | None:
        """Return the 5 day forecast for a location."""
        return await self._async_request(
            "/v3/wx/forecast/daily/5day", _location_params(latitude, longitude)
        )

    async def async_get_hourly_forecast(
        self, latitude: float, longitude: float
    ) -> dict[str, Any] | None:
        """Return the 48 hour forecast for a location."""
        return await self._async_request(
            "/v3/wx/forecast/hourly/2day", _location_params(latitude, longitude)
        )

    async def _async_request(
        self, path: str, params: dict[str, str]
    ) -> dict[str, Any] | None:
        """Call the API, refreshing the API key once if it was rejected."""
        api_key = await self._async_get_api_key()
        status, data = await self._async_api_get(path, params, api_key)
        if status in UNAUTHORIZED_STATUSES:
            LOGGER.debug("API key was rejected (HTTP %s), fetching a new one", status)
            api_key = await self._async_get_api_key(rejected_key=api_key)
            status, data = await self._async_api_get(path, params, api_key)
            if status in UNAUTHORIZED_STATUSES:
                # A fresh key that is rejected will not work a minute later either
                self._key_retry_after = time.monotonic() + KEY_RETRY_COOLDOWN
                raise WundergroundApiKeyError(
                    f"The API key from the dashboard page was rejected (HTTP {status})"
                )
        return data

    async def _async_get_api_key(self, rejected_key: str | None = None) -> str:
        """Return the cached API key, scraping a new one if needed."""
        async with self._api_key_lock:
            # Another request may have refreshed the key while we waited
            if self._api_key is not None and self._api_key != rejected_key:
                return self._api_key
            if (
                self._key_retry_after is not None
                and time.monotonic() < self._key_retry_after
            ):
                raise WundergroundApiKeyError(
                    "No working API key, the dashboard page will be checked again later"
                )
            self._api_key = None
            try:
                self._api_key = await self._async_fetch_api_key()
            except WundergroundApiKeyError:
                self._key_retry_after = time.monotonic() + KEY_RETRY_COOLDOWN
                raise
            return self._api_key

    async def _async_fetch_api_key(self) -> str:
        """Scrape the API key from the station dashboard page."""
        url = DASHBOARD_URL.format(station_id=self.station_id)
        LOGGER.debug("Fetching API key from %s", url)
        try:
            async with self._session.get(
                url, headers=PAGE_HEADERS, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    raise WundergroundConnectionError(
                        f"Dashboard page returned HTTP {response.status}"
                    )
                html = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WundergroundConnectionError(
                f"Cannot load the dashboard page: {_describe(err)}"
            ) from err

        if not (api_key := extract_api_key(html)):
            raise WundergroundApiKeyError(
                "API key not found on the dashboard page, markup may have changed"
            )
        return api_key

    async def _async_api_get(
        self, path: str, params: dict[str, str], api_key: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Perform one API request and return its status and JSON body."""
        try:
            async with self._session.get(
                f"{API_BASE_URL}{path}",
                params={**params, "apiKey": api_key},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if (
                    response.status in UNAUTHORIZED_STATUSES
                    or response.status == HTTP_NO_CONTENT
                ):
                    return response.status, None
                if response.status != 200:
                    raise WundergroundConnectionError(
                        f"{path} returned HTTP {response.status}"
                    )
                try:
                    data = await response.json(content_type=None)
                except ValueError as err:
                    raise WundergroundConnectionError(
                        f"{path} returned invalid JSON"
                    ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            # aiohttp errors may contain the request URL with the key, do not
            # chain them or the key ends up in debug tracebacks
            raise WundergroundConnectionError(
                f"Request to {path} failed: {_describe(err, api_key)}"
            ) from None

        if not isinstance(data, dict):
            raise WundergroundConnectionError(f"{path} returned unexpected data")
        return response.status, data


def _location_params(latitude: float, longitude: float) -> dict[str, str]:
    """Return query parameters for weather.com location based endpoints."""
    return {
        "geocode": f"{latitude:.3f},{longitude:.3f}",
        "format": "json",
        "units": "m",
        "language": "en-US",
    }
