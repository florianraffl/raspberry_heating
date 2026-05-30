"""Sensor platform for raspberry_heating."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo

from .api import HeatingPumpDto, SensorDto
from .const import DOMAIN
from .entity import IntegrationRaspberryHeatingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RaspberryHeatingDataUpdateCoordinator
    from .data import IntegrationRaspberryHeatingConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: IntegrationRaspberryHeatingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    known_sensor_ids: set[str] = set()
    coordinator = entry.runtime_data.coordinator

    def _check_sensors() -> None:
        api_sensors = coordinator.data.sensors
        api_pumps = coordinator.data.pumps

        # Build a map: sensor_id -> heating pump that owns it
        sensor_to_pump: dict[str, HeatingPumpDto] = {}
        for pump in api_pumps.values():
            if isinstance(pump, HeatingPumpDto):
                sensor_to_pump[pump.solar_panel_sensor_key] = pump
                sensor_to_pump[pump.pool_sensor_key] = pump

        new_entities: list[IntegrationRaspberryHeatingSensor] = []
        for sensor_id, sensor_dto in api_sensors.items():
            if sensor_id in known_sensor_ids:
                continue
            owning_pump = sensor_to_pump.get(sensor_id)
            new_entities.append(
                IntegrationRaspberryHeatingSensor(
                    coordinator=coordinator,
                    sensor=sensor_dto,
                    owning_pump=owning_pump,
                    entry_id=entry.entry_id,
                )
            )

        known_sensor_ids.update(api_sensors.keys())

        # Refresh native_value for already-registered entities via coordinator update
        async_add_entities(new_entities)

    coordinator.async_add_listener(_check_sensors)


class IntegrationRaspberryHeatingSensor(IntegrationRaspberryHeatingEntity, SensorEntity):
    """raspberry_heating Sensor class."""

    sensor_id: str

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        sensor: SensorDto,
        owning_pump: HeatingPumpDto | None,
        entry_id: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.sensor_id = sensor.sensor_id
        self._attr_unique_id = sensor.sensor_id
        self._attr_name = sensor.sensor_id

        if owning_pump is not None:
            # Place this sensor under the heating pump device instead of the Pi device.
            self._attr_translation_key = (
                "solar_temperature"
                if sensor.sensor_id == owning_pump.solar_panel_sensor_key
                else "pool_temperature"
            )
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, owning_pump.pump_id)},
                via_device=(DOMAIN, entry_id),
            )
        else:
            # Unassigned sensor: use raw sensor ID as name (unique per device).
            self._attr_name = sensor.sensor_id
        # else: inherits the Pi-level DeviceInfo set by IntegrationRaspberryHeatingEntity

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
        """Return the current temperature from the coordinator."""
        sensor = self.coordinator.data.sensors.get(self.sensor_id)
        return sensor.temperature_value if sensor else None

    @property
    def suggested_display_precision(self) -> int | None:
        """Return the suggested display precision."""
        return 2
