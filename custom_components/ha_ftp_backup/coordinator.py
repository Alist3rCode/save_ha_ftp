"""Coordinator: orchestrates backup creation → FTP upload → retention pruning."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .backup_manager import BackupManager
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
    DEFAULT_MAX_BACKUPS,
)
from .ftp_client import FtpClient

_LOGGER = logging.getLogger(__name__)


class FtpBackupCoordinator:
    """Central coordinator for the FTP backup integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._ftp = self._build_ftp_client()
        self._cancel_scheduler: Any = None

        # State exposed to sensor
        self.last_backup: datetime | None = None
        self.last_backup_size_mb: float | None = None
        self.next_backup: datetime | None = None
        self.total_backups_on_ftp: int | None = None
        self.last_error: str | None = None
        self.running: bool = False

        self._listeners: list[Any] = []

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_ftp_client(self) -> FtpClient:
        d = self.entry.data
        return FtpClient(
            host=d[CONF_FTP_HOST],
            port=d.get(CONF_FTP_PORT, 21),
            user=d[CONF_FTP_USER],
            password=d[CONF_FTP_PASSWORD],
            remote_path=d.get(CONF_FTP_PATH, "/ha_backups"),
            use_tls=d.get(CONF_FTP_TLS, False),
        )

    @property
    def _frequency_hours(self) -> int:
        return self.entry.data.get(CONF_BACKUP_FREQUENCY_HOURS, DEFAULT_BACKUP_FREQUENCY_HOURS)

    @property
    def _max_backups(self) -> int:
        return self.entry.data.get(CONF_MAX_BACKUPS, DEFAULT_MAX_BACKUPS)

    # ------------------------------------------------------------------
    # Connection test (called during setup)
    # ------------------------------------------------------------------

    async def async_test_connection(self) -> None:
        """Raise if the FTP server is unreachable."""
        await self.hass.async_add_executor_job(self._ftp.test_connection)

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def async_start_scheduler(self) -> None:
        """Start the periodic backup timer."""
        interval = timedelta(hours=self._frequency_hours)
        self.next_backup = datetime.now(timezone.utc) + interval

        cancel = async_track_time_interval(
            self.hass,
            self._handle_scheduled_backup,
            interval,
        )
        self._cancel_scheduler = cancel
        _LOGGER.info(
            "FTP backup scheduler started — interval %sh, next run at %s",
            self._frequency_hours,
            self.next_backup.isoformat(),
        )

    def async_stop_scheduler(self) -> None:
        """Cancel the periodic timer."""
        if self._cancel_scheduler:
            self._cancel_scheduler()
            self._cancel_scheduler = None

    async def _handle_scheduled_backup(self, _now: datetime) -> None:
        """Callback fired by the scheduler."""
        await self.async_run_backup()
        # Update next_backup timestamp
        interval = timedelta(hours=self._frequency_hours)
        self.next_backup = datetime.now(timezone.utc) + interval
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Core backup workflow
    # ------------------------------------------------------------------

    async def async_run_backup(self) -> None:
        """Create a full backup, upload it, then prune old backups."""
        if self.running:
            _LOGGER.warning("A backup is already in progress, skipping.")
            return

        self.running = True
        self.last_error = None
        self._notify_listeners()

        try:
            async with aiohttp.ClientSession() as session:
                mgr = BackupManager(session)
                info = await mgr.create_full_backup()

            slug: str = info["slug"]
            name: str = info.get("name", slug)
            size_bytes: int = info.get("size", 0)
            local_path = f"/backup/{slug}.tar"
            remote_name = f"ha_backup_{name}_{slug}.tar"

            _LOGGER.info("Uploading backup %s (%s MB) to FTP…", slug, round(size_bytes / 1024**2, 1))
            await self.hass.async_add_executor_job(
                self._ftp.upload_file, local_path, remote_name
            )

            pruned = await self.hass.async_add_executor_job(
                self._ftp.prune, self._max_backups
            )
            if pruned:
                _LOGGER.info("Pruned %d old backup(s) from FTP", len(pruned))

            ftp_backups = await self.hass.async_add_executor_job(self._ftp.list_backups)

            self.last_backup = datetime.now(timezone.utc)
            self.last_backup_size_mb = round(size_bytes / 1024**2, 2)
            self.total_backups_on_ftp = len(ftp_backups)
            _LOGGER.info("Backup workflow completed successfully.")

        except Exception as err:  # noqa: BLE001
            self.last_error = str(err)
            _LOGGER.error("FTP backup failed: %s", err)
        finally:
            self.running = False
            self._notify_listeners()

    # ------------------------------------------------------------------
    # Listener pattern for sensor updates
    # ------------------------------------------------------------------

    def async_add_listener(self, callback: Any) -> Any:
        """Register a listener; returns an unsubscribe callable."""
        self._listeners.append(callback)

        def _remove() -> None:
            self._listeners.remove(callback)

        return _remove

    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            cb()
