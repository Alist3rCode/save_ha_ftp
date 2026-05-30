"""Sensor platform for HA FTP Backup."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LAST_BACKUP,
    ATTR_LAST_BACKUP_SIZE,
    ATTR_LAST_ERROR,
    ATTR_NEXT_BACKUP,
    ATTR_TOTAL_BACKUPS_FTP,
    DOMAIN,
)
from .coordinator import FtpBackupCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FtpBackupCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FtpBackupStatusSensor(coordinator, entry)])


class FtpBackupStatusSensor(SensorEntity):
    """Sensor reporting the status of the last FTP backup."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "FTP Backup Status"
    _attr_icon = "mdi:cloud-upload"

    def __init__(self, coordinator: FtpBackupCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        if self._coordinator.running:
            return "running"
        if self._coordinator.last_error:
            return "error"
        if self._coordinator.last_backup:
            return "ok"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self._coordinator.last_backup:
            attrs[ATTR_LAST_BACKUP] = self._coordinator.last_backup.isoformat()
        if self._coordinator.last_backup_size_mb is not None:
            attrs[ATTR_LAST_BACKUP_SIZE] = self._coordinator.last_backup_size_mb
        if self._coordinator.next_backup:
            attrs[ATTR_NEXT_BACKUP] = self._coordinator.next_backup.isoformat()
        if self._coordinator.total_backups_on_ftp is not None:
            attrs[ATTR_TOTAL_BACKUPS_FTP] = self._coordinator.total_backups_on_ftp
        if self._coordinator.last_error:
            attrs[ATTR_LAST_ERROR] = self._coordinator.last_error
        return attrs

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
