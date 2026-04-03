"""Sample API Client."""

from __future__ import annotations

from numbers import Number
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
        raise IntegrationRaspberryHeatingApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class IntegrationRaspberryHeatingApiClient:
    """Sample API Client."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._host = host
        self._session = session

    async def async_get_sensors(self) -> list[SensorDto]:
        """Get sensors from the Raspberry Pi."""
        resp = await self._api_wrapper(
            method="get",
            url=f"http://{self._host}:8080/api/sensor",
        )
        return [
            SensorDto(sensor_id=s["sensorId"], temperature_value=s["temperatureValue"])
            for s in resp
        ]

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
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntegrationRaspberryHeatingApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntegrationRaspberryHeatingApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise IntegrationRaspberryHeatingApiClientError(
                msg,
            ) from exception


class SensorDto:
    """Data transfer object for a sensor."""

    def __init__(
        self,
        sensor_id: str,
        temperature_value: float,
    ) -> None:
        """Initialize the sensor DTO."""
        self.sensor_id = sensor_id
        self.temperature_value = temperature_value
