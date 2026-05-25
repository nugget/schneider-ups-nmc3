"""Config flow for Schneider Electric UPS NMC3."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_PRIVACY_PROTOCOL,
    CONF_SNMP_VERSION,
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    CONF_USERNAME,
    DEFAULT_PORT,
    DEFAULT_RETRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .snmp import (
    AUTH_PROTOCOL_MD5,
    AUTH_PROTOCOL_NONE,
    AUTH_PROTOCOL_SHA,
    PRIVACY_PROTOCOL_AES,
    PRIVACY_PROTOCOL_DES,
    PRIVACY_PROTOCOL_NONE,
    SNMP_VERSION_2C,
    SNMP_VERSION_3,
    SNMPClient,
    SNMPConfigurationError,
    SNMPConnectionConfig,
    SNMPError,
)
from .syslog import (
    DEFAULT_SYSLOG_BIND_ADDRESS,
    DEFAULT_SYSLOG_ENABLED,
    DEFAULT_SYSLOG_PORT,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)

SNMP_VERSION_OPTIONS = {
    SNMP_VERSION_2C: "SNMPv2c",
    SNMP_VERSION_3: "SNMPv3",
}
AUTH_PROTOCOL_OPTIONS = {
    AUTH_PROTOCOL_NONE: "No authentication",
    AUTH_PROTOCOL_MD5: "MD5",
    AUTH_PROTOCOL_SHA: "SHA",
}
PRIVACY_PROTOCOL_OPTIONS = {
    PRIVACY_PROTOCOL_NONE: "No privacy",
    PRIVACY_PROTOCOL_DES: "DES",
    PRIVACY_PROTOCOL_AES: "AES",
}
CONFIGURATION_ERROR_MESSAGES = {
    "SNMPv3 requires a username": {CONF_USERNAME: "missing_username"},
    "SNMPv3 authentication key is required": {CONF_AUTH_KEY: "missing_auth_key"},
    "SNMPv3 privacy key is required": {CONF_PRIVACY_KEY: "missing_privacy_key"},
    "SNMPv3 privacy requires authentication": {
        CONF_AUTH_PROTOCOL: "privacy_requires_auth"
    },
}


class SchneiderUPSNMC3ConfigFlow(  # pyright: ignore[reportGeneralTypeIssues]
    config_entries.ConfigFlow,
    domain=DOMAIN,  # pyright: ignore[reportCallIssue]
):
    """Handle a config flow for Schneider Electric UPS NMC3."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._base_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._base_input = user_input
            if user_input[CONF_SNMP_VERSION] == SNMP_VERSION_3:
                return await self.async_step_snmpv3()
            return await self.async_step_snmpv2c()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(
                        CONF_SNMP_VERSION, default=SNMP_VERSION_2C
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": value, "label": label}
                                for value, label in SNMP_VERSION_OPTIONS.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10,
                            max=3600,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_snmpv2c(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMPv2c credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**self._base_input, **user_input}
            errors = await self._async_validate_input(data)
            if not errors:
                return await self._async_create_entry(data)

        return self.async_show_form(
            step_id="snmpv2c",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMMUNITY, default="public"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_snmpv3(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMPv3 credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**self._base_input, **user_input}
            errors = await self._async_validate_input(data)
            if not errors:
                return await self._async_create_entry(data)

        return self.async_show_form(
            step_id="snmpv3",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(
                        CONF_AUTH_PROTOCOL, default=AUTH_PROTOCOL_SHA
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": value, "label": label}
                                for value, label in AUTH_PROTOCOL_OPTIONS.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_AUTH_KEY): str,
                    vol.Required(
                        CONF_PRIVACY_PROTOCOL, default=PRIVACY_PROTOCOL_AES
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": value, "label": label}
                                for value, label in PRIVACY_PROTOCOL_OPTIONS.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_PRIVACY_KEY): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchneiderUPSNMC3OptionsFlow:
        """Create the options flow."""
        return SchneiderUPSNMC3OptionsFlow(config_entry)

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate the user input by querying the UPS."""
        client: SNMPClient | None = None
        try:
            client = SNMPClient(_config_from_data(data))
            ups_data = await client.async_get_data()
        except SNMPConfigurationError as err:
            _LOGGER.debug("SNMP configuration validation failed", exc_info=err)
            return _snmp_configuration_errors(err)
        except SNMPError as err:
            _LOGGER.debug("SNMP validation failed", exc_info=err)
            return {"base": "cannot_connect"}
        finally:
            if client is not None:
                client.close()

        await self.async_set_unique_id(ups_data.unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: data[CONF_HOST],
                CONF_PORT: data[CONF_PORT],
            }
        )
        data["_title"] = ups_data.name

        return {}

    async def _async_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create the config entry."""
        title = data.pop("_title", data[CONF_HOST])
        return self.async_create_entry(title=title, data=data)


class SchneiderUPSNMC3OptionsFlow(config_entries.OptionsFlow):
    """Handle options for Schneider Electric UPS NMC3."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        syslog_enabled = self._config_entry.options.get(
            CONF_SYSLOG_ENABLED,
            self._config_entry.data.get(CONF_SYSLOG_ENABLED, DEFAULT_SYSLOG_ENABLED),
        )
        syslog_bind_address = self._config_entry.options.get(
            CONF_SYSLOG_BIND_ADDRESS,
            self._config_entry.data.get(
                CONF_SYSLOG_BIND_ADDRESS,
                DEFAULT_SYSLOG_BIND_ADDRESS,
            ),
        )
        syslog_port = self._config_entry.options.get(
            CONF_SYSLOG_PORT,
            self._config_entry.data.get(CONF_SYSLOG_PORT, DEFAULT_SYSLOG_PORT),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=scan_interval
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10,
                            max=3600,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                    vol.Required(CONF_SYSLOG_ENABLED, default=syslog_enabled): bool,
                    vol.Required(
                        CONF_SYSLOG_BIND_ADDRESS,
                        default=syslog_bind_address,
                    ): str,
                    vol.Required(
                        CONF_SYSLOG_PORT,
                        default=syslog_port,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )


def _config_from_data(data: dict[str, Any]) -> SNMPConnectionConfig:
    """Build an SNMP connection config from config entry data."""
    return SNMPConnectionConfig(
        host=data[CONF_HOST],
        port=int(data.get(CONF_PORT, DEFAULT_PORT)),
        version=data[CONF_SNMP_VERSION],
        community=data.get(CONF_COMMUNITY),
        username=data.get(CONF_USERNAME),
        auth_protocol=data.get(CONF_AUTH_PROTOCOL, AUTH_PROTOCOL_NONE),
        auth_key=data.get(CONF_AUTH_KEY),
        privacy_protocol=data.get(CONF_PRIVACY_PROTOCOL, PRIVACY_PROTOCOL_NONE),
        privacy_key=data.get(CONF_PRIVACY_KEY),
        timeout=DEFAULT_TIMEOUT,
        retries=DEFAULT_RETRIES,
    )


def _snmp_configuration_errors(err: SNMPConfigurationError) -> dict[str, str]:
    """Map local SNMP configuration failures to config flow errors."""
    return CONFIGURATION_ERROR_MESSAGES.get(
        str(err),
        {"base": "invalid_snmp_configuration"},
    )
