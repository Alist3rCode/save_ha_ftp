"""Config flow for HA FTP Backup."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BACKUP_FREQUENCY_HOURS,
    CONF_FTP_HOST,
    CONF_FTP_PASSWORD,
    CONF_FTP_PATH,
    CONF_FTP_PORT,
    CONF_FTP_TLS,
    CONF_FTP_USER,
    CONF_MAX_BACKUPS,
    DEFAULT_BACKUP_FREQUENCY_HOURS,
    DEFAULT_FTP_PATH,
    DEFAULT_FTP_PORT,
    DEFAULT_FTP_TLS,
    DEFAULT_MAX_BACKUPS,
    DOMAIN,
)
from .ftp_client import FtpClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FTP_HOST): str,
        vol.Optional(CONF_FTP_PORT, default=DEFAULT_FTP_PORT): vol.Coerce(int),
        vol.Required(CONF_FTP_USER): str,
        vol.Required(CONF_FTP_PASSWORD): str,
        vol.Optional(CONF_FTP_PATH, default=DEFAULT_FTP_PATH): str,
        vol.Optional(CONF_FTP_TLS, default=DEFAULT_FTP_TLS): bool,
        vol.Optional(
            CONF_BACKUP_FREQUENCY_HOURS, default=DEFAULT_BACKUP_FREQUENCY_HOURS
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8760)),
        vol.Optional(CONF_MAX_BACKUPS, default=DEFAULT_MAX_BACKUPS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=365)
        ),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FTP_PATH, default=DEFAULT_FTP_PATH): str,
        vol.Optional(CONF_FTP_TLS, default=DEFAULT_FTP_TLS): bool,
        vol.Optional(
            CONF_BACKUP_FREQUENCY_HOURS, default=DEFAULT_BACKUP_FREQUENCY_HOURS
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8760)),
        vol.Optional(CONF_MAX_BACKUPS, default=DEFAULT_MAX_BACKUPS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=365)
        ),
    }
)


class HaFtpBackupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            ftp = FtpClient(
                host=user_input[CONF_FTP_HOST],
                port=user_input.get(CONF_FTP_PORT, DEFAULT_FTP_PORT),
                user=user_input[CONF_FTP_USER],
                password=user_input[CONF_FTP_PASSWORD],
                remote_path=user_input.get(CONF_FTP_PATH, DEFAULT_FTP_PATH),
                use_tls=user_input.get(CONF_FTP_TLS, DEFAULT_FTP_TLS),
            )
            try:
                await self.hass.async_add_executor_job(ftp.test_connection)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("FTP connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_FTP_HOST]}:{user_input.get(CONF_FTP_PORT, DEFAULT_FTP_PORT)}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"FTP Backup → {user_input[CONF_FTP_HOST]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HaFtpBackupOptionsFlow":
        return HaFtpBackupOptionsFlow(config_entry)


class HaFtpBackupOptionsFlow(config_entries.OptionsFlow):
    """Allow updating frequency, retention and FTP path after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            updated_data = dict(self._config_entry.data)
            updated_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=updated_data
            )
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FTP_PATH,
                    default=current.get(CONF_FTP_PATH, DEFAULT_FTP_PATH),
                ): str,
                vol.Optional(
                    CONF_FTP_TLS,
                    default=current.get(CONF_FTP_TLS, DEFAULT_FTP_TLS),
                ): bool,
                vol.Optional(
                    CONF_BACKUP_FREQUENCY_HOURS,
                    default=current.get(
                        CONF_BACKUP_FREQUENCY_HOURS, DEFAULT_BACKUP_FREQUENCY_HOURS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8760)),
                vol.Optional(
                    CONF_MAX_BACKUPS,
                    default=current.get(CONF_MAX_BACKUPS, DEFAULT_MAX_BACKUPS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
