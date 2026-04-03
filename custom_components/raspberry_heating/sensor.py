"""Sensor platform for raspberry_heating."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature

from .entity import IntegrationRaspberryHeatingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from raspberry_heating.api import SensorDto

    from .coordinator import RaspberryHeatingDataUpdateCoordinator
    from .data import IntegrationRaspberryHeatingConfigEntry


class RaspberryHeatingSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Raspberry Heating sensor entity."""

    sensor: SensorDto


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationRaspberryHeatingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    known_sensors: set[IntegrationRaspberryHeatingSensor] = set()
    coordinator: RaspberryHeatingDataUpdateCoordinator = entry.runtime_data.coordinator

    def _check_sensors() -> None:
        api_sensors: dict[str, SensorDto] = coordinator.data

        for sensor in known_sensors:
            sensor.update_state(list(api_sensors.values()))

        new_sensors = [
            IntegrationRaspberryHeatingSensor(
                coordinator=coordinator,
                sensor=api_sensors[sensor],
            )
            for sensor in api_sensors
            if sensor not in [known_sensor.sensor_id for known_sensor in known_sensors]
        ]
        known_sensors.update(new_sensors)
        async_add_entities(new_sensors)

    coordinator.async_add_listener(_check_sensors)


class IntegrationRaspberryHeatingSensor(
    IntegrationRaspberryHeatingEntity, SensorEntity
):
    """raspberry_heating Sensor class."""

    sensor_id: str

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        sensor: SensorDto,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_native_value: float | None = self._sensor.temperature_value
        self._attr_name = self._sensor.sensor_id
        self.sensor_id = self._sensor.sensor_id
        self._attr_unique_id = self._sensor.sensor_id
        self.device_entry_id = self._sensor.sensor_id

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self) -> UnitOfTemperature:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def suggested_display_precision(self) -> int | None:
        """Return the suggested display precision."""
        return 2

    def update_state(self, sensor_datas: list[SensorDto]) -> None:
        """Update the state of the sensor."""
        if not any(
            sensor_data.sensor_id == self.sensor_id for sensor_data in sensor_datas
        ):
            self._attr_native_value = None
            return

        self._attr_native_value = next(
            sensor_data.temperature_value
            for sensor_data in sensor_datas
            if sensor_data.sensor_id == self.sensor_id
        )
