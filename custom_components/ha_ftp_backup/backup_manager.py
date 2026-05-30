"""Supervisor backup manager — creates full HAOS backups via the Supervisor REST API."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import aiohttp

from .const import SUPERVISOR_API, SUPERVISOR_BACKUPS_ENDPOINT

_LOGGER = logging.getLogger(__name__)

_SUPERVISOR_TOKEN_ENV = "SUPERVISOR_TOKEN"
_BACKUP_TIMEOUT = aiohttp.ClientTimeout(total=1800)  # 30 min max for large installs


class BackupManager:
    """Interact with the Home Assistant Supervisor to create and retrieve backups."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._token = os.environ.get(_SUPERVISOR_TOKEN_ENV, "")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def create_full_backup(self, name: str | None = None) -> dict:
        """Request a new full backup from the Supervisor.

        Returns the backup metadata dict (slug, filename, size, …).
        """
        label = name or f"ha_ftp_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        payload = {"name": label}

        _LOGGER.info("Requesting full Supervisor backup: %s", label)
        async with self._session.post(
            f"{SUPERVISOR_API}{SUPERVISOR_BACKUPS_ENDPOINT}/new/full",
            headers=self._headers,
            json=payload,
            timeout=_BACKUP_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        slug = data["data"]["slug"]
        _LOGGER.info("Backup created with slug: %s", slug)
        return await self.get_backup_info(slug)

    async def get_backup_info(self, slug: str) -> dict:
        """Return metadata for a single backup."""
        async with self._session.get(
            f"{SUPERVISOR_API}{SUPERVISOR_BACKUPS_ENDPOINT}/{slug}/info",
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return data["data"]

    async def list_backups(self) -> list[dict]:
        """Return list of all backups known to the Supervisor."""
        async with self._session.get(
            f"{SUPERVISOR_API}{SUPERVISOR_BACKUPS_ENDPOINT}",
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return data["data"]["backups"]

    def local_path(self, slug: str) -> str:
        """Return the local filesystem path for a backup slug."""
        return f"/backup/{slug}.tar"
