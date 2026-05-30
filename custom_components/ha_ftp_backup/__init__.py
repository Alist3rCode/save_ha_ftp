"""HA FTP Backup — sauvegarde complète HAOS vers un serveur FTP."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import FtpBackupCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA FTP Backup from a config entry."""
    coordinator = FtpBackupCoordinator(hass, entry)

    try:
        await coordinator.async_test_connection()
    except Exception as err:
        raise ConfigEntryNotReady(f"Impossible de joindre le serveur FTP : {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.async_start_scheduler()

    async def _handle_run_backup(call: ServiceCall) -> None:
        """Service handler: trigger an immediate backup."""
        await coordinator.async_run_backup()

    hass.services.async_register(DOMAIN, "run_backup", _handle_run_backup)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: FtpBackupCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_stop_scheduler()

    hass.services.async_remove(DOMAIN, "run_backup")

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
