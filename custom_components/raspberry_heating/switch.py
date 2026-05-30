"""Switch platform for raspberry_heating — pump control switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .api import FilterPumpDto, HeatingPumpDto
from .const import DOMAIN
from .entity import IntegrationRaspberryHeatingEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import PumpDto
    from .coordinator import RaspberryHeatingDataUpdateCoordinator
    from .data import IntegrationRaspberryHeatingConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: IntegrationRaspberryHeatingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    known_pump_ids: set[str] = set()
    swim_mode_added = False
    coordinator = entry.runtime_data.coordinator

    def _check_pumps() -> None:
        nonlocal swim_mode_added
        pumps = coordinator.data.pumps
        new_entities: list[SwitchEntity] = []
        for pump_id, pump in pumps.items():
            if pump_id in known_pump_ids:
                continue
            device_name = "Filter Pump" if isinstance(pump, FilterPumpDto) else "Heating Pump"
            new_entities.append(PumpPowerSwitch(coordinator, pump_id, entry.entry_id, device_name))
            new_entities.append(PumpEnabledSwitch(coordinator, pump_id, entry.entry_id, device_name))
            if isinstance(pump, HeatingPumpDto):
                new_entities.append(HeatingPumpAutoModeSwitch(coordinator, pump_id, entry.entry_id, device_name))
        known_pump_ids.update(pumps.keys())

        if not swim_mode_added and len(known_pump_ids) >= 2:
            new_entities.append(SwimModeSwitch(coordinator, entry.entry_id))
            swim_mode_added = True

        async_add_entities(new_entities)

    coordinator.async_add_listener(_check_pumps)


class _PumpSwitchBase(IntegrationRaspberryHeatingEntity, SwitchEntity):
    """Base class for pump switches."""

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pump_id)},
            name=device_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def _pump(self) -> PumpDto | None:
        return self.coordinator.data.pumps.get(self.pump_id)

    @property
    def available(self) -> bool:
        """Return True if the pump still exists in the API response."""
        return self._pump is not None


class PumpPowerSwitch(_PumpSwitchBase):
    """Switch to manually turn the pump relay on or off.

    Shown as unavailable when the pump is disabled or when a heating pump
    is running in automatic mode — the state is still displayed, but the
    switch cannot be toggled.
    """

    _attr_icon = "mdi:power"
    _attr_translation_key = "power"

    def __init__(
        self, coordinator: RaspberryHeatingDataUpdateCoordinator, pump_id: str, entry_id: str, device_name: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, pump_id, entry_id, device_name)
        self._attr_unique_id = f"{pump_id}_power"

    @property
    def is_on(self) -> bool | None:
        """Return the actual relay state."""
        return self._pump.is_on if self._pump else None

    @property
    def available(self) -> bool:
        """Return False when the pump cannot be manually controlled."""
        pump = self._pump
        if pump is None:
            return False
        if pump.is_disabled:
            return False
        return not (isinstance(pump, HeatingPumpDto) and pump.use_automatic_mode)

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the pump."""
        await self.coordinator.config_entry.runtime_data.client.async_pump_on(self.pump_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the pump."""
        await self.coordinator.config_entry.runtime_data.client.async_pump_off(self.pump_id)
        await self.coordinator.async_request_refresh()


class PumpEnabledSwitch(_PumpSwitchBase):
    """Switch to enable or disable a pump."""

    _attr_icon = "mdi:check-circle"
    _attr_translation_key = "enabled"

    def __init__(
        self, coordinator: RaspberryHeatingDataUpdateCoordinator, pump_id: str, entry_id: str, device_name: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, pump_id, entry_id, device_name)
        self._attr_unique_id = f"{pump_id}_enabled"

    @property
    def is_on(self) -> bool | None:
        """Return True when the pump is enabled (not disabled)."""
        return not self._pump.is_disabled if self._pump else None

    async def async_turn_on(self, **_: Any) -> None:
        """Enable the pump."""
        await self.coordinator.config_entry.runtime_data.client.async_pump_enable(self.pump_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Disable the pump."""
        await self.coordinator.config_entry.runtime_data.client.async_pump_disable(self.pump_id)
        await self.coordinator.async_request_refresh()


class HeatingPumpAutoModeSwitch(_PumpSwitchBase):
    """Switch to toggle automatic mode on a heating pump."""

    _attr_icon = "mdi:thermostat-auto"
    _attr_translation_key = "auto_mode"

    def __init__(
        self, coordinator: RaspberryHeatingDataUpdateCoordinator, pump_id: str, entry_id: str, device_name: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, pump_id, entry_id, device_name)
        self._attr_unique_id = f"{pump_id}_auto_mode"

    @property
    def is_on(self) -> bool | None:
        """Return True when automatic mode is active."""
        pump = self._pump
        return pump.use_automatic_mode if isinstance(pump, HeatingPumpDto) else None

    async def async_turn_on(self, **_: Any) -> None:
        """Enable automatic mode."""
        await self.coordinator.config_entry.runtime_data.client.async_update_heating_pump(
            self.pump_id, None, None, True
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Disable automatic mode."""
        await self.coordinator.config_entry.runtime_data.client.async_update_heating_pump(
            self.pump_id, None, None, False
        )
        await self.coordinator.async_request_refresh()


class SwimModeSwitch(IntegrationRaspberryHeatingEntity, SwitchEntity):
    """Global switch that disables all pumps at once so it is safe to swim.

    Appears on the Pi device (not a specific pump) and is only registered
    once at least two pumps are configured. Turning it on disables every
    pump; turning it off enables them all so they resume normal operation.
    """

    _attr_translation_key = "swim_mode"
    _attr_icon = "mdi:swim"

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_swim_mode"
        # Lives on the Pi device (DeviceInfo already set by IntegrationRaspberryHeatingEntity)

    @property
    def is_on(self) -> bool:
        """Return True when ALL pumps are disabled (swim mode active)."""
        pumps = self.coordinator.data.pumps
        return bool(pumps) and all(p.is_disabled for p in pumps.values())

    async def async_turn_on(self, **_: Any) -> None:
        """Disable every pump — safe to swim."""
        client = self.coordinator.config_entry.runtime_data.client
        for pump_id in self.coordinator.data.pumps:
            await client.async_pump_disable(pump_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Re-enable every pump — they will resume normal operation."""
        client = self.coordinator.config_entry.runtime_data.client
        for pump_id in self.coordinator.data.pumps:
            await client.async_pump_enable(pump_id)
        await self.coordinator.async_request_refresh()
