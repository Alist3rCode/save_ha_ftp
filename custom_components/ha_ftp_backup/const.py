"""Constants for HA FTP Backup."""
DOMAIN = "ha_ftp_backup"

PLATFORMS: list[str] = ["sensor"]

# Config entry keys
CONF_FTP_HOST = "ftp_host"
CONF_FTP_PORT = "ftp_port"
CONF_FTP_USER = "ftp_user"
CONF_FTP_PASSWORD = "ftp_password"
CONF_FTP_PATH = "ftp_path"
CONF_FTP_TLS = "ftp_tls"
CONF_BACKUP_FREQUENCY_HOURS = "backup_frequency_hours"
CONF_MAX_BACKUPS = "max_backups"

# Defaults
DEFAULT_FTP_PORT = 21
DEFAULT_FTP_PATH = "/ha_backups"
DEFAULT_FTP_TLS = False
DEFAULT_BACKUP_FREQUENCY_HOURS = 24
DEFAULT_MAX_BACKUPS = 7

# Supervisor API
SUPERVISOR_API = "http://supervisor"
SUPERVISOR_BACKUPS_ENDPOINT = "/backups"

# Attributes
ATTR_LAST_BACKUP = "last_backup"
ATTR_LAST_BACKUP_SIZE = "last_backup_size_mb"
ATTR_NEXT_BACKUP = "next_backup"
ATTR_TOTAL_BACKUPS_FTP = "total_backups_on_ftp"
ATTR_LAST_ERROR = "last_error"
