"""Shared entity helpers for Wunderground Weather."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DASHBOARD_URL, DOMAIN, MANUFACTURER
from .coordinator import WundergroundObservationCoordinator


def station_device_info(coordinator: WundergroundObservationCoordinator) -> DeviceInfo:
    """Return device info describing the weather station."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.station_id)},
        name=coordinator.station_name,
        manufacturer=MANUFACTURER,
        model="Personal weather station",
        sw_version=(coordinator.data or {}).get("softwareType"),
        configuration_url=DASHBOARD_URL.format(
            station_id=coordinator.client.station_id
        ),
    )


class WundergroundEntity(CoordinatorEntity[WundergroundObservationCoordinator]):
    """Base class for entities backed by station observations."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: WundergroundObservationCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = station_device_info(coordinator)
