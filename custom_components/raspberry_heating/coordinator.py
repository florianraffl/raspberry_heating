"""DataUpdateCoordinator for raspberry_heating."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IntegrationRaspberryHeatingApiClientAuthenticationError,
    IntegrationRaspberryHeatingApiClientError,
    PumpDto,
    SensorDto,
)

if TYPE_CHECKING:
    from .data import IntegrationRaspberryHeatingConfigEntry


class RaspberryHeatingCoordinatorData:
    """Typed container for coordinator data."""

    def __init__(self, sensors: dict[str, SensorDto], pumps: dict[str, PumpDto]) -> None:
        """Initialize coordinator data."""
        self.sensors = sensors
        self.pumps = pumps


class RaspberryHeatingDataUpdateCoordinator(DataUpdateCoordinator[RaspberryHeatingCoordinatorData]):
    """Class to manage fetching data from the API."""

    config_entry: IntegrationRaspberryHeatingConfigEntry

    async def _async_update_data(self) -> RaspberryHeatingCoordinatorData:
        """Update data via library."""
        try:
            sensors = await self.config_entry.runtime_data.client.async_get_sensors()
            pumps = await self.config_entry.runtime_data.client.async_get_pumps()
            return RaspberryHeatingCoordinatorData(
                sensors={s.sensor_id: s for s in sensors},
                pumps={p.pump_id: p for p in pumps},
            )
        except IntegrationRaspberryHeatingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except IntegrationRaspberryHeatingApiClientError as exception:
            raise UpdateFailed(exception) from exception
