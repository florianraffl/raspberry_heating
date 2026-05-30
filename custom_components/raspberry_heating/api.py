"""Sample API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout


class IntegrationRaspberryHeatingApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationRaspberryHeatingApiClientCommunicationError(
    IntegrationRaspberryHeatingApiClientError,
):
    """Exception to indicate a communication error."""


class IntegrationRaspberryHeatingApiClientAuthenticationError(
    IntegrationRaspberryHeatingApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise IntegrationRaspberryHeatingApiClientAuthenticationError(msg)
    response.raise_for_status()


class IntegrationRaspberryHeatingApiClient:
    """Sample API Client."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Sample API Client."""
        self._host = host
        self._session = session
        self._port = 8081

    async def async_get_sensors(self) -> list[SensorDto]:
        """Get sensors from the Raspberry Pi."""
        resp = await self._api_wrapper(
            method="get", url=f"http://{self._host}:{self._port}/api/sensor"
        )
        return [
            SensorDto(sensor_id=s["sensorId"], temperature_value=s["temperatureValue"])
            for s in resp
        ]

    async def async_get_pumps(self) -> list[PumpDto]:
        """Get pumps from the Raspberry Pi."""
        resp = await self._api_wrapper(
            method="get", url=f"http://{self._host}:{self._port}/api/pump"
        )
        return [_parse_pump(p) for p in resp]

    async def async_create_filter_pump(
        self, switch_pin_id: int, start_time: str, end_time: str
    ) -> None:
        """Create a filter pump."""
        await self._api_wrapper(
            method="post",
            url=f"http://{self._host}:{self._port}/api/pump/filter",
            data={
                "switchPinId": switch_pin_id,
                "startTime": start_time,
                "endTime": end_time,
            },
        )

    async def async_create_heating_pump(
        self,
        switch_pin_id: int,
        solar_panel_sensor_key: str,
        pool_sensor_key: str,
        power_on_threshold: float,
        power_off_threshold: float,
    ) -> None:
        """Create a heating pump."""
        await self._api_wrapper(
            method="post",
            url=f"http://{self._host}:{self._port}/api/pump/heating",
            data={
                "switchPinId": switch_pin_id,
                "solarPanelSensorKey": solar_panel_sensor_key,
                "poolSensorKey": pool_sensor_key,
                "powerOnThreshold": power_on_threshold,
                "powerOffThreshold": power_off_threshold,
            },
        )

    async def async_update_filter_pump(
        self, pump_id: str, start_time: str | None, end_time: str | None
    ) -> None:
        """Update a filter pump."""
        await self._api_wrapper(
            method="put",
            url=f"http://{self._host}:{self._port}/api/pump/filter",
            data={"id": pump_id, "startTime": start_time, "endTime": end_time},
        )

    async def async_update_heating_pump(
        self,
        pump_id: str,
        power_on_threshold: float | None,
        power_off_threshold: float | None,
        use_automatic_mode: bool | None,
    ) -> None:
        """Update a heating pump."""
        await self._api_wrapper(
            method="put",
            url=f"http://{self._host}:{self._port}/api/pump/heating",
            data={
                "id": pump_id,
                "powerOnThreshold": power_on_threshold,
                "powerOffThreshold": power_off_threshold,
                "useAutomaticMode": use_automatic_mode,
            },
        )

    async def async_pump_on(self, pump_id: str) -> None:
        """Manually turn on a pump."""
        await self._api_wrapper(
            method="post", url=f"http://{self._host}:{self._port}/api/pump/{pump_id}/on"
        )

    async def async_pump_off(self, pump_id: str) -> None:
        """Manually turn off a pump."""
        await self._api_wrapper(
            method="post",
            url=f"http://{self._host}:{self._port}/api/pump/{pump_id}/off",
        )

    async def async_pump_disable(self, pump_id: str) -> None:
        """Disable a pump."""
        await self._api_wrapper(
            method="post",
            url=f"http://{self._host}:{self._port}/api/pump/{pump_id}/disable",
        )

    async def async_pump_enable(self, pump_id: str) -> None:
        """Enable a pump."""
        await self._api_wrapper(
            method="post",
            url=f"http://{self._host}:{self._port}/api/pump/{pump_id}/enable",
        )

    async def async_delete_pump(self, pump_id: str) -> None:
        """Delete a pump."""
        await self._api_wrapper(
            method="delete", url=f"http://{self._host}:{self._port}/api/pump/{pump_id}"
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                if response.status == 204 or response.content_length == 0:
                    return None
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntegrationRaspberryHeatingApiClientCommunicationError(
                msg
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntegrationRaspberryHeatingApiClientCommunicationError(
                msg
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise IntegrationRaspberryHeatingApiClientError(msg) from exception


def _parse_pump(data: dict) -> PumpDto:
    pump_type = data.get("type")
    if pump_type == "FilterPump":
        return FilterPumpDto(
            pump_id=data["id"],
            is_on=data["isOn"],
            is_disabled=data["isDisabled"],
            start_time=data["startTime"],
            end_time=data["endTime"],
            last_manual_powered_off=data.get("lastManualPoweredOff"),
            is_manual_powered_on=data["isManualPoweredOn"],
        )
    if pump_type == "HeatingPump":
        return HeatingPumpDto(
            pump_id=data["id"],
            is_on=data["isOn"],
            is_disabled=data["isDisabled"],
            solar_panel_sensor_key=data["solarPanelSensorKey"],
            pool_sensor_key=data["poolSensorKey"],
            power_on_threshold=data["powerOnThreshold"],
            power_off_threshold=data["powerOffThreshold"],
            use_automatic_mode=data["useAutomaticMode"],
        )
    msg = f"Unknown pump type: {pump_type}"
    raise IntegrationRaspberryHeatingApiClientError(msg)


class SensorDto:
    """Data transfer object for a sensor."""

    def __init__(self, sensor_id: str, temperature_value: float) -> None:
        """Initialize the sensor DTO."""
        self.sensor_id = sensor_id
        self.temperature_value = temperature_value


class PumpDto:
    """Base data transfer object for a pump."""

    def __init__(self, pump_id: str, is_on: bool, is_disabled: bool) -> None:
        """Initialize the pump DTO."""
        self.pump_id = pump_id
        self.is_on = is_on
        self.is_disabled = is_disabled


class FilterPumpDto(PumpDto):
    """Data transfer object for a filter pump."""

    def __init__(
        self,
        pump_id: str,
        is_on: bool,
        is_disabled: bool,
        start_time: str,
        end_time: str,
        last_manual_powered_off: str | None,
        is_manual_powered_on: bool,
    ) -> None:
        """Initialize the filter pump DTO."""
        super().__init__(pump_id, is_on, is_disabled)
        self.start_time = start_time
        self.end_time = end_time
        self.last_manual_powered_off = last_manual_powered_off
        self.is_manual_powered_on = is_manual_powered_on


class HeatingPumpDto(PumpDto):
    """Data transfer object for a heating pump."""

    def __init__(
        self,
        pump_id: str,
        is_on: bool,
        is_disabled: bool,
        solar_panel_sensor_key: str,
        pool_sensor_key: str,
        power_on_threshold: float,
        power_off_threshold: float,
        use_automatic_mode: bool,
    ) -> None:
        """Initialize the heating pump DTO."""
        super().__init__(pump_id, is_on, is_disabled)
        self.solar_panel_sensor_key = solar_panel_sensor_key
        self.pool_sensor_key = pool_sensor_key
        self.power_on_threshold = power_on_threshold
        self.power_off_threshold = power_off_threshold
        self.use_automatic_mode = use_automatic_mode
