"""Shared entity helpers for the Proxmox Monitor Agent integration."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PmaDataUpdateCoordinator


def sanitize_id(value: object) -> str:
    """Normalize a value for use in Home Assistant entity identifiers."""
    sanitized = re.sub(r"[^0-9A-Za-z]+", "_", str(value)).strip("_").lower()
    return sanitized or "unknown"


def vm_memory_percent(item: Mapping[str, Any]) -> float | None:
    """Return VM memory usage percentage from byte counters."""
    used = item.get("memory_used_bytes")
    total = item.get("memory_total_bytes")
    if not isinstance(used, int | float) or not isinstance(total, int | float):
        return None
    if total <= 0:
        return None

    return round((used / total) * 100, 2)


def host_id(snapshot: Mapping[str, Any]) -> str:
    """Return the sanitized host identifier for a metrics snapshot."""
    host = snapshot.get("host")
    if not isinstance(host, Mapping):
        return "unknown"

    return sanitize_id(host.get("id") or host.get("hostname") or "unknown")


def host_device_info(
    snapshot: Mapping[str, Any], configuration_url: str | None = None
) -> DeviceInfo:
    """Build Home Assistant device info for the Proxmox host."""
    host = snapshot.get("host")
    if not isinstance(host, Mapping):
        host = {}

    hostname = host.get("hostname") or "unknown"
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, host_id(snapshot))},
        "name": f"Proxmox {hostname}",
    }

    for key in ("manufacturer", "model", "serial_number", "sw_version"):
        value = host.get(key)
        if value is not None:
            device_info[key] = value

    if configuration_url is not None:
        device_info["configuration_url"] = configuration_url

    return device_info


class PmaEntity(CoordinatorEntity[PmaDataUpdateCoordinator]):
    """Base entity for Proxmox Monitor Agent entities."""

    _attr_has_entity_name = True

    @property
    def snapshot(self) -> Mapping[str, Any]:
        """Return the latest coordinator snapshot."""
        return self.coordinator.data or {}
