"""Time platform for raspberry_heating — filter pump start/end times."""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .api import FilterPumpDto
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
    """Set up the time platform."""
    known_pump_ids: set[str] = set()
    coordinator = entry.runtime_data.coordinator

    def _check_pumps() -> None:
        pumps = coordinator.data.pumps
        new_entities: list[TimeEntity] = []
        for pump_id, pump in pumps.items():
            if pump_id in known_pump_ids or not isinstance(pump, FilterPumpDto):
                continue
            new_entities.append(FilterPumpTimeEntity(coordinator, pump_id, entry.entry_id, "start", "Filter Pump"))
            new_entities.append(FilterPumpTimeEntity(coordinator, pump_id, entry.entry_id, "end", "Filter Pump"))
        known_pump_ids.update(pumps.keys())
        async_add_entities(new_entities)

    coordinator.async_add_listener(_check_pumps)


def _utc_time_str_to_local(time_str: str) -> time:
    """Convert a UTC HH:MM:SS string (from the API) to the HA local time."""
    parts = time_str.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    today = dt_util.now().date()
    utc_dt = datetime(today.year, today.month, today.day, h, m, s, tzinfo=UTC)
    return dt_util.as_local(utc_dt).time()


def _local_time_to_utc_str(t: time) -> str:
    """Convert a local time (from the HA UI) to a UTC HH:MM:SS string for the API."""
    today = dt_util.now().date()
    local_dt = datetime(
        today.year, today.month, today.day, t.hour, t.minute, t.second, tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    return dt_util.as_utc(local_dt).strftime("%H:%M:%S")


class FilterPumpTimeEntity(IntegrationRaspberryHeatingEntity, TimeEntity):
    """Time entity for a filter pump start or end time."""

    def __init__(
        self,
        coordinator: RaspberryHeatingDataUpdateCoordinator,
        pump_id: str,
        entry_id: str,
        which: str,  # "start" or "end"
        device_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.pump_id = pump_id
        self._which = which
        self._attr_unique_id = f"{pump_id}_{which}_time"
        self._attr_translation_key = "start_time" if which == "start" else "end_time"
        self._attr_icon = "mdi:clock-start" if which == "start" else "mdi:clock-end"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pump_id)},
            name=device_name,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def _pump(self) -> FilterPumpDto | None:
        pump = self.coordinator.data.pumps.get(self.pump_id)
        return pump if isinstance(pump, FilterPumpDto) else None

    @property
    def native_value(self) -> time | None:
        """Return the current time value converted from UTC to local time."""
        pump = self._pump
        if pump is None:
            return None
        raw = pump.start_time if self._which == "start" else pump.end_time
        return _utc_time_str_to_local(raw)

    @property
    def available(self) -> bool:
        """Return True if the pump exists."""
        return self._pump is not None

    async def async_set_value(self, value: time) -> None:
        """Convert local time to UTC and update via the API."""
        utc_str = _local_time_to_utc_str(value)
        if self._which == "start":
            await self.coordinator.config_entry.runtime_data.client.async_update_filter_pump(
                self.pump_id, utc_str, None
            )
        else:
            await self.coordinator.config_entry.runtime_data.client.async_update_filter_pump(
                self.pump_id, None, utc_str
            )
        await self.coordinator.async_request_refresh()
