"""Constants for the Proxmox Monitor Agent integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "proxmox_monitor_agent"

CONF_PATH = "path"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 9782
DEFAULT_PATH = "/metrics.json"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_SCAN_INTERVAL_DELTA = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

PLATFORMS = ["sensor"]
