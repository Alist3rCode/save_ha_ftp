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


def _format_listing(probe: dict) -> str:
    """Turn a probe_path result into a human-readable string for placeholders."""
    lines: list[str] = []

    if not probe["path_exists"]:
        lines.append(f"⚠ Le chemin '{probe['browsed_path']}' sera créé au premier backup.")
        lines.append(f"Contenu du dossier parent ({probe['browsed_path']}) :")
    else:
        lines.append(f"Contenu de {probe['browsed_path']} :")

    if not probe["dirs"] and not probe["files"]:
        lines.append("  (dossier vide)")
    else:
        for d in probe["dirs"]:
            lines.append(f"  📁 {d}/")
        for f in probe["files"]:
            lines.append(f"  📄 {f}")

    return "\n".join(lines)


class HaFtpBackupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._listing_text: str = ""

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
                probe = await self.hass.async_add_executor_job(
                    ftp.probe_path,
                    user_input.get(CONF_FTP_PATH, DEFAULT_FTP_PATH),
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("FTP connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._data = user_input
                self._listing_text = _format_listing(probe)
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show FTP directory listing and ask user to confirm."""
        if user_input is not None:
            await self.async_set_unique_id(
                f"{self._data[CONF_FTP_HOST]}:{self._data.get(CONF_FTP_PORT, DEFAULT_FTP_PORT)}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"FTP Backup → {self._data[CONF_FTP_HOST]}",
                data=self._data,
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"listing": self._listing_text},
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
        self._pending: dict[str, Any] = {}
        self._listing_text: str = ""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            current = self._config_entry.data
            ftp = FtpClient(
                host=current[CONF_FTP_HOST],
                port=current.get(CONF_FTP_PORT, DEFAULT_FTP_PORT),
                user=current[CONF_FTP_USER],
                password=current[CONF_FTP_PASSWORD],
                remote_path=user_input.get(CONF_FTP_PATH, DEFAULT_FTP_PATH),
                use_tls=user_input.get(CONF_FTP_TLS, DEFAULT_FTP_TLS),
            )
            try:
                probe = await self.hass.async_add_executor_job(
                    ftp.probe_path,
                    user_input.get(CONF_FTP_PATH, DEFAULT_FTP_PATH),
                )
                self._listing_text = _format_listing(probe)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("FTP probe failed in options flow: %s", err)
                self._listing_text = f"Impossible de lister le dossier : {err}"

            self._pending = user_input
            return await self.async_step_confirm()

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

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show FTP directory listing then save options."""
        if user_input is not None:
            updated_data = dict(self._config_entry.data)
            updated_data.update(self._pending)
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=updated_data
            )
            return self.async_create_entry(title="", data=self._pending)

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"listing": self._listing_text},
        )
