"""Tests for the Wunderground Weather config and options flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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

from .conftest import DASHBOARD_URL, STATION_ID, mock_responses


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_user_flow(hass: HomeAssistant, mock_api: AiohttpClientMocker) -> None:
    """A valid station creates an entry named after its neighborhood."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: " itest123 ", CONF_UPDATE_INTERVAL: 120}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Town"
    assert result["data"] == {
        CONF_STATION_ID: STATION_ID,
        CONF_STATION_NAME: "Test Town",
    }
    assert result["options"] == {CONF_UPDATE_INTERVAL: 120}
    assert result["result"].unique_id == STATION_ID


async def test_user_flow_custom_name(
    hass: HomeAssistant, mock_api: AiohttpClientMocker
) -> None:
    """A name entered by the user wins over the neighborhood."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_STATION_ID: STATION_ID,
            CONF_STATION_NAME: "Garden",
            CONF_UPDATE_INTERVAL: 60,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garden"
    assert result["data"][CONF_STATION_NAME] == "Garden"


async def test_invalid_station_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """IDs with unexpected characters are rejected without a request."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: "../ITEST", CONF_UPDATE_INTERVAL: 60}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATION_ID: "invalid_station_id"}
    assert aioclient_mock.call_count == 0


async def test_station_not_found_then_recover(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unknown station shows an error and the flow can be retried."""
    mock_responses(aioclient_mock, observation_status=204)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: STATION_ID, CONF_UPDATE_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATION_ID: "station_not_found"}

    aioclient_mock.clear_requests()
    mock_responses(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: STATION_ID, CONF_UPDATE_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Network errors show cannot_connect."""
    aioclient_mock.get(DASHBOARD_URL, exc=TimeoutError())
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: STATION_ID, CONF_UPDATE_INTERVAL: 60}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_key_not_found_is_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A dashboard page without a key shows cannot_connect."""
    aioclient_mock.get(DASHBOARD_URL, text="<html></html>")
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: STATION_ID, CONF_UPDATE_INTERVAL: 60}
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: AiohttpClientMocker
) -> None:
    """The same station cannot be added twice, regardless of case."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_STATION_ID: STATION_ID.lower(), CONF_UPDATE_INTERVAL: 60}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_reloads_entry(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Changing the interval stores it and applies it after a reload."""
    entry = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 300}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_UPDATE_INTERVAL: 300}
    assert entry.runtime_data.observation.update_interval.total_seconds() == 300
