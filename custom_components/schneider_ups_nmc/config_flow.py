"""Config flow for APC UPS NMC."""

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
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
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
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigFlowResult

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
    "SNMPv3 authentication passphrase is required": {CONF_AUTH_KEY: "missing_auth_key"},
    "SNMPv3 privacy passphrase is required": {CONF_PRIVACY_KEY: "missing_privacy_key"},
    "SNMPv3 privacy requires authentication": {
        CONF_AUTH_PROTOCOL: "privacy_requires_auth"
    },
}
RECONFIGURE_REPLACED_DATA_KEYS = {
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_HOST,
    CONF_PORT,
    CONF_PRIVACY_KEY,
    CONF_PRIVACY_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SNMP_VERSION,
    CONF_USERNAME,
}


class SchneiderUPSNMCConfigFlow(  # pyright: ignore[reportGeneralTypeIssues]
    config_entries.ConfigFlow,
    domain=DOMAIN,  # pyright: ignore[reportCallIssue]
):
    """Handle a config flow for APC UPS NMC."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._base_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._base_input = user_input
            if user_input[CONF_SNMP_VERSION] == SNMP_VERSION_3:
                return await self.async_step_snmpv3()
            return await self.async_step_snmpv2c()

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._base_input = user_input
            if user_input[CONF_SNMP_VERSION] == SNMP_VERSION_3:
                return await self.async_step_snmpv3()
            return await self.async_step_snmpv2c()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_base_schema(entry.data),
        )

    async def async_step_snmpv2c(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle SNMPv2c credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**self._base_input, **user_input}
            errors = await self._async_validate_input(data)
            if not errors:
                return self._async_finish_flow(data)

        return self.async_show_form(
            step_id="snmpv2c",
            data_schema=_snmpv2c_schema(self._credentials_defaults()),
            errors=errors,
        )

    async def async_step_snmpv3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle SNMPv3 credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**self._base_input, **user_input}
            errors = await self._async_validate_input(data)
            if not errors:
                return self._async_finish_flow(data)

        return self.async_show_form(
            step_id="snmpv3",
            data_schema=_snmpv3_schema(self._credentials_defaults()),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchneiderUPSNMCOptionsFlow:
        """Create the options flow."""
        return SchneiderUPSNMCOptionsFlow(config_entry)

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
        if self.source == config_entries.SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="wrong_device")
        else:
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: data[CONF_HOST],
                    CONF_PORT: data[CONF_PORT],
                }
            )
        data["_title"] = ups_data.name

        return {}

    def _async_finish_flow(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the config entry after validation."""
        title = data.get("_title", data[CONF_HOST])
        entry_data = _entry_data(data)
        if self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                entry,
                title=title,
                data=_reconfigured_entry_data(entry.data, entry_data),
            )

        return self.async_create_entry(title=title, data=entry_data)

    def _credentials_defaults(self) -> Mapping[str, Any]:
        """Return saved credential defaults for reconfigure flows."""
        if self.source != config_entries.SOURCE_RECONFIGURE:
            return {}
        return self._get_reconfigure_entry().data


class SchneiderUPSNMCOptionsFlow(config_entries.OptionsFlow):
    """Handle options for APC UPS NMC."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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


def _base_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Build the shared UPS connection schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            _required(CONF_HOST, defaults): str,
            _required(CONF_PORT, defaults, DEFAULT_PORT): int,
            _required(CONF_SNMP_VERSION, defaults, SNMP_VERSION_2C): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": value, "label": label}
                        for value, label in SNMP_VERSION_OPTIONS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            _required(
                CONF_SCAN_INTERVAL,
                defaults,
                DEFAULT_SCAN_INTERVAL,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=3600,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                )
            ),
        }
    )


def _snmpv2c_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the SNMPv2c credential schema."""
    return vol.Schema(
        {
            _required(CONF_COMMUNITY, defaults, "public"): _password_selector(),
        }
    )


def _snmpv3_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the SNMPv3 credential schema."""
    return vol.Schema(
        {
            _required(CONF_USERNAME, defaults): str,
            _required(CONF_AUTH_PROTOCOL, defaults, AUTH_PROTOCOL_SHA): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": value, "label": label}
                        for value, label in AUTH_PROTOCOL_OPTIONS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            _optional(CONF_AUTH_KEY, defaults): _password_selector(),
            _required(
                CONF_PRIVACY_PROTOCOL,
                defaults,
                PRIVACY_PROTOCOL_AES,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": value, "label": label}
                        for value, label in PRIVACY_PROTOCOL_OPTIONS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            _optional(CONF_PRIVACY_KEY, defaults): _password_selector(),
        }
    )


def _password_selector() -> TextSelector:
    """Return a password-style text selector for SNMP secrets."""
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _required(
    key: str,
    defaults: Mapping[str, Any],
    fallback: Any = vol.UNDEFINED,
) -> Any:
    """Return a required voluptuous marker with a default when available."""
    if key in defaults:
        return vol.Required(key, default=defaults[key])
    if fallback is not vol.UNDEFINED:
        return vol.Required(key, default=fallback)
    return vol.Required(key)


def _optional(key: str, defaults: Mapping[str, Any]) -> Any:
    """Return an optional voluptuous marker with a default when available."""
    if key in defaults:
        return vol.Optional(key, default=defaults[key])
    return vol.Optional(key)


def _entry_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return config entry data without flow-private values."""
    return {key: value for key, value in data.items() if key != "_title"}


def _reconfigured_entry_data(
    existing_data: Mapping[str, Any],
    updated_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge reconfigured flow data while preserving unrelated entry data."""
    preserved_data = {
        key: value
        for key, value in existing_data.items()
        if key not in RECONFIGURE_REPLACED_DATA_KEYS and key != "_title"
    }
    return preserved_data | dict(updated_data)


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
