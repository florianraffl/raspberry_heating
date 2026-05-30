"""Constants for raspberry_heating."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "raspberry_heating"

PUMP_TYPE_FILTER = "FilterPump"
PUMP_TYPE_HEATING = "HeatingPump"
