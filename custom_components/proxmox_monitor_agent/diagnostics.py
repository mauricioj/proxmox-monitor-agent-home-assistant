"""Diagnostics for Proxmox Monitor Agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_PATH, DEFAULT_PATH, DEFAULT_PORT, DOMAIN


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping view when the value is dict-like, otherwise empty."""
    return value if isinstance(value, Mapping) else {}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return a compact diagnostics payload for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = _as_mapping(coordinator.data)
    collection = _as_mapping(data.get("collection"))
    host = _as_mapping(data.get("host"))
    errors = collection.get("errors")
    if not isinstance(errors, list):
        errors = []

    return {
        "endpoint": {
            "host": entry.data[CONF_HOST],
            "port": entry.data.get(CONF_PORT, DEFAULT_PORT),
            "path": entry.data.get(CONF_PATH, DEFAULT_PATH),
        },
        "schema": {
            "name": _as_mapping(data.get("schema")).get("name"),
            "version": _as_mapping(data.get("schema")).get("version"),
        },
        "collection": {
            "status": collection.get("status"),
            "generated_at": collection.get("generated_at"),
            "duration_ms": collection.get("duration_ms"),
            "error_count": collection.get("error_count", len(errors)),
            "errors": errors,
        },
        "host_identity": {
            "id": host.get("id"),
            "hostname": host.get("hostname"),
        },
    }
