"""DataUpdateCoordinator for raspberry_heating."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IntegrationRaspberryHeatingApiClientAuthenticationError,
    IntegrationRaspberryHeatingApiClientError,
    SensorDto,
)

if TYPE_CHECKING:
    from .data import IntegrationRaspberryHeatingConfigEntry
    from .sensor import IntegrationRaspberryHeatingSensor


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class RaspberryHeatingDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: IntegrationRaspberryHeatingConfigEntry

    sensors_data: list[SensorDto] = []

    sensors: list[IntegrationRaspberryHeatingSensor] = []

    async def _async_update_data(self) -> dict[str, SensorDto]:
        """Update data via library."""
        try:
            resp = await self.config_entry.runtime_data.client.async_get_sensors()
            return {sensor.sensor_id: sensor for sensor in resp}
            self.sensors_data = (
                await self.config_entry.runtime_data.client.async_get_sensors()
            )

            for sensor in self.sensors:
                sensor.update_state(self.sensors_data)

            non_existent_sensors = [
                sensor_data
                for sensor_data in self.sensors_data
                if not any(
                    sensor.sensor_id == sensor_data.sensor_id for sensor in self.sensors
                )
            ]

        except IntegrationRaspberryHeatingApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except IntegrationRaspberryHeatingApiClientError as exception:
            raise UpdateFailed(exception) from exception
