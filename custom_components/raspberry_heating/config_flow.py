"""Adds config flow for RaspberryHeating."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util
from slugify import slugify

from .api import (
    IntegrationRaspberryHeatingApiClient,
    IntegrationRaspberryHeatingApiClientAuthenticationError,
    IntegrationRaspberryHeatingApiClientCommunicationError,
    IntegrationRaspberryHeatingApiClientError,
)
from .const import DOMAIN, LOGGER


def _local_time_str_to_utc(time_str: str) -> str:
    """Convert a local HH:MM:SS string (from HA TimeSelector) to UTC for the API."""
    parts = time_str.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    today = dt_util.now().date()
    local_dt = datetime(today.year, today.month, today.day, h, m, s, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_utc(local_dt).strftime("%H:%M:%S")


class RaspberryHeatingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for RaspberryHeating."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RaspberryHeatingOptionsFlowHandler:
        """Return the options flow."""
        return RaspberryHeatingOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_connection(host=user_input[CONF_HOST])
            except IntegrationRaspberryHeatingApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except IntegrationRaspberryHeatingApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except IntegrationRaspberryHeatingApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    ## Do NOT use this in production code
                    ## The unique_id should never be something that can change
                    ## https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                    unique_id=slugify(user_input[CONF_HOST])
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, (  # noqa: S101
            "Integration documentation URL is not set in manifest.json"
        )

        return self.async_show_form(
            step_id="user",
            description_placeholders={"documentation_url": integration.documentation},
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=_errors,
        )

    async def _test_connection(self, host: str) -> None:
        """Validate credentials."""
        client = IntegrationRaspberryHeatingApiClient(
            host=host,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_sensors()


class RaspberryHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow — add pumps to a Raspberry Pi entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self._pump_type: str | None = None

    async def async_step_init(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Show the pump-type selector."""
        if user_input is not None:
            self._pump_type = user_input["pump_type"]
            if self._pump_type == "filter":
                return await self.async_step_add_filter_pump()
            return await self.async_step_add_heating_pump()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("pump_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="filter", label="Filter Pump"),
                                selector.SelectOptionDict(value="heating", label="Heating Pump"),
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_add_filter_pump(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Collect parameters and create a filter pump."""
        _errors = {}
        if user_input is not None:
            try:
                client = self.config_entry.runtime_data.client
                await client.async_create_filter_pump(
                    switch_pin_id=int(user_input["switch_pin_id"]),
                    start_time=_local_time_str_to_utc(user_input["start_time"]),
                    end_time=_local_time_str_to_utc(user_input["end_time"]),
                )
            except IntegrationRaspberryHeatingApiClientError as exception:
                LOGGER.error(exception)
                _errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_filter_pump",
            data_schema=vol.Schema(
                {
                    vol.Required("switch_pin_id"): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=40, mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required("start_time", default="06:00:00"): selector.TimeSelector(),
                    vol.Required("end_time", default="10:00:00"): selector.TimeSelector(),
                }
            ),
            errors=_errors,
        )

    async def async_step_add_heating_pump(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Collect parameters and create a heating pump."""
        _errors = {}
        if user_input is not None:
            try:
                client = self.config_entry.runtime_data.client
                await client.async_create_heating_pump(
                    switch_pin_id=int(user_input["switch_pin_id"]),
                    solar_panel_sensor_key=user_input["solar_panel_sensor_key"],
                    pool_sensor_key=user_input["pool_sensor_key"],
                    power_on_threshold=user_input["power_on_threshold"],
                    power_off_threshold=user_input["power_off_threshold"],
                )
            except IntegrationRaspberryHeatingApiClientError as exception:
                LOGGER.error(exception)
                _errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_heating_pump",
            data_schema=vol.Schema(
                {
                    vol.Required("switch_pin_id"): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=40, mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required("solar_panel_sensor_key"): selector.TextSelector(),
                    vol.Required("pool_sensor_key"): selector.TextSelector(),
                    vol.Required("power_on_threshold", default=10.0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-50, max=150, step=0.1, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required("power_off_threshold", default=5.0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-50, max=150, step=0.1, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=_errors,
        )
