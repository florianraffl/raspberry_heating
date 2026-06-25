"""Number platform for raspberry_heating — heating pump temperature thresholds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo

from .api import HeatingPumpDto
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
    """Set up the number platform."""
    known_pump_ids: set[str] = set()
    coordinator = entry.runtime_data.coordinator

    def _check_pumps() -> None:
        pumps = coordinator.data.pumps
        new_entities: list[NumberEntity] = []
        for pump_id, pump in pumps.items():
            if pump_id in known_pump_ids or not isinstance(pump, HeatingPumpDto):
                continue
            new_entities.append(
                HeatingPumpThresholdNumber(coordinator, pump_id, entry.entry_id, "power_on", "Heating Pump")
            )
            new_entities.append(
                HeatingPumpThresholdNumber(coordinator, pump_id, entry.entry_id, "power_off", "Heating Pump")
            )
            new_entities.append(
                HeatingPumpMaxPoolTemperatureNumber(coordinator, pump_id, entry.entry_id, "Heating Pump")
            )
        known_pump_ids.update(pumps.keys())
        async_add_entities(new_entities)

    coordinator.async_add_listener(_check_pumps)


class HeatingPumpThresholdNumber(IntegrationRaspberryHeatingEntity, NumberEntity):
    """Number entity for a heating pump temperature threshold."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -50.0
    _attr_native_max_value = 150.0
    _attr_native_step = 0.1

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        pump_id: str,
        entry_id: str,
        threshold: str,  # "power_on" or "power_off"
        device_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.pump_id = pump_id
        self._threshold = threshold
        self._attr_unique_id = f"{pump_id}_{threshold}_threshold"
        self._attr_translation_key = "power_on_threshold" if threshold == "power_on" else "power_off_threshold"
        self._attr_icon = "mdi:thermometer-chevron-up" if threshold == "power_on" else "mdi:thermometer-chevron-down"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pump_id)},
            name=device_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def _pump(self) -> HeatingPumpDto | None:
        pump = self.coordinator.data.pumps.get(self.pump_id)
        return pump if isinstance(pump, HeatingPumpDto) else None

    @property
    def native_value(self) -> float | None:
        """Return the current threshold value."""
        pump = self._pump
        if pump is None:
            return None
        return pump.power_on_threshold if self._threshold == "power_on" else pump.power_off_threshold

    @property
    def available(self) -> bool:
        """Return True if the pump exists."""
        return self._pump is not None

    async def async_set_native_value(self, value: float) -> None:
        """Update the threshold via the API."""
        if self._threshold == "power_on":
            await self.coordinator.config_entry.runtime_data.client.async_update_heating_pump(
                self.pump_id, value, None, None
            )
        else:
            await self.coordinator.config_entry.runtime_data.client.async_update_heating_pump(
                self.pump_id, None, value, None
            )
        await self.coordinator.async_request_refresh()


class HeatingPumpMaxPoolTemperatureNumber(IntegrationRaspberryHeatingEntity, NumberEntity):
    """Number entity for the maximum pool temperature limit of a heating pump."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_max_value = 50.0
    _attr_native_step = 0.5
    _attr_translation_key = "max_pool_temperature"
    _attr_icon = "mdi:pool-thermometer"

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        pump_id: str,
        entry_id: str,
        device_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.pump_id = pump_id
        self._attr_unique_id = f"{pump_id}_max_pool_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pump_id)},
            name=device_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def _pump(self) -> HeatingPumpDto | None:
        pump = self.coordinator.data.pumps.get(self.pump_id)
        return pump if isinstance(pump, HeatingPumpDto) else None

    @property
    def native_value(self) -> float | None:
        """Return the current max pool temperature, or None if not set."""
        pump = self._pump
        return pump.max_pool_temperature if pump is not None else None

    @property
    def available(self) -> bool:
        """Return True if the pump exists."""
        return self._pump is not None

    async def async_set_native_value(self, value: float) -> None:
        """Set the maximum pool temperature via the API."""
        await self.coordinator.config_entry.runtime_data.client.async_update_heating_pump(
            self.pump_id, None, None, None, value
        )
        await self.coordinator.async_request_refresh()
