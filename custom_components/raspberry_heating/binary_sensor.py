"""Binary sensor platform for raspberry_heating — pump IsOn state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .api import FilterPumpDto, PumpDto
from .const import DOMAIN
from .entity import IntegrationRaspberryHeatingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RaspberryHeatingDataUpdateCoordinator
    from .data import IntegrationRaspberryHeatingConfigEntry


def _pump_device_name(pump: PumpDto) -> str:
    return "Filter Pump" if isinstance(pump, FilterPumpDto) else "Heating Pump"


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: IntegrationRaspberryHeatingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    known_pump_ids: set[str] = set()
    coordinator = entry.runtime_data.coordinator

    def _check_pumps() -> None:
        pumps = coordinator.data.pumps
        new_entities = [
            PumpIsOnBinarySensor(
                coordinator=coordinator,
                pump_id=pump_id,
                entry_id=entry.entry_id,
                device_name=_pump_device_name(pump),
            )
            for pump_id, pump in pumps.items()
            if pump_id not in known_pump_ids
        ]
        known_pump_ids.update(p.pump_id for p in new_entities)
        async_add_entities(new_entities)

    coordinator.async_add_listener(_check_pumps)


class PumpIsOnBinarySensor(IntegrationRaspberryHeatingEntity, BinarySensorEntity):
    """Read-only binary sensor showing the actual relay state of a pump."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:water-pump"

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
        self._attr_unique_id = f"{pump_id}_is_on"
        self._attr_translation_key = "is_on"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pump_id)},
            name=device_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def _pump(self) -> PumpDto | None:
        return self.coordinator.data.pumps.get(self.pump_id)

    @property
    def is_on(self) -> bool | None:
        """Return true if the pump relay is on."""
        return self._pump.is_on if self._pump else None

    @property
    def available(self) -> bool:
        """Return True if the pump still exists in the API response."""
        return self._pump is not None
