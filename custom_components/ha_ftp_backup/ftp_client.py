"""FTP client wrapper (supports plain FTP and FTPS)."""
from __future__ import annotations

import ftplib
import logging
import os
from pathlib import PurePosixPath

_LOGGER = logging.getLogger(__name__)

_BACKUP_PREFIX = "ha_backup_"


class FtpClient:
    """Thin wrapper around ftplib to upload backups and manage retention."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        remote_path: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._remote_path = remote_path
        self._use_tls = use_tls

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> ftplib.FTP:
        """Return an authenticated FTP(S) connection."""
        if self._use_tls:
            ftp: ftplib.FTP = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        ftp.connect(self._host, self._port, timeout=30)
        ftp.login(self._user, self._password)

        if self._use_tls:
            ftp.prot_p()  # type: ignore[attr-defined]

        ftp.set_pasv(True)
        return ftp

    def _ensure_remote_dir(self, ftp: ftplib.FTP) -> None:
        """Create remote directory hierarchy if it does not exist."""
        parts = PurePosixPath(self._remote_path).parts
        for i in range(1, len(parts) + 1):
            segment = str(PurePosixPath(*parts[:i]))
            try:
                ftp.cwd(segment)
            except ftplib.error_perm:
                ftp.mkd(segment)
                ftp.cwd(segment)
        ftp.cwd(self._remote_path)

    # ------------------------------------------------------------------
    # Public API (blocking — run in executor)
    # ------------------------------------------------------------------

    def test_connection(self) -> None:
        """Connect, authenticate, and immediately quit (smoke-test)."""
        ftp = self._connect()
        ftp.quit()

    def upload_file(self, local_path: str, remote_filename: str) -> None:
        """Upload *local_path* as *remote_filename* under the configured remote path."""
        ftp = self._connect()
        try:
            self._ensure_remote_dir(ftp)
            with open(local_path, "rb") as fh:
                ftp.storbinary(f"STOR {remote_filename}", fh, blocksize=8192 * 8)
            _LOGGER.debug("Uploaded %s → %s/%s", local_path, self._remote_path, remote_filename)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass

    def list_backups(self) -> list[str]:
        """Return sorted list of backup filenames on the FTP server."""
        ftp = self._connect()
        try:
            self._ensure_remote_dir(ftp)
            names = ftp.nlst()
            backups = sorted(
                [n for n in names if n.startswith(_BACKUP_PREFIX) and n.endswith(".tar")]
            )
            return backups
        finally:
            try:
                ftp.quit()
            except Exception:
                pass

    def delete_file(self, remote_filename: str) -> None:
        """Delete *remote_filename* from the configured remote path."""
        ftp = self._connect()
        try:
            ftp.cwd(self._remote_path)
            ftp.delete(remote_filename)
            _LOGGER.debug("Deleted remote file %s/%s", self._remote_path, remote_filename)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass

    def prune(self, max_backups: int) -> list[str]:
        """Delete oldest backups so that at most *max_backups* remain. Returns deleted names."""
        backups = self.list_backups()
        to_delete = backups[: max(0, len(backups) - max_backups)]
        for name in to_delete:
            _LOGGER.info("Pruning old FTP backup: %s", name)
            self.delete_file(name)
        return to_delete
