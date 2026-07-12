"""Maintenance helpers for Proxmox Monitor Agent."""

from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


async def async_prune_unavailable_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, int]:
    """Remove unavailable entities for a config entry and cleanup empty devices."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    removed_entities = 0
    removed_devices = 0

    for entity_entry in list(er.async_entries_for_config_entry(entity_registry, entry.entry_id)):
        state = hass.states.get(entity_entry.entity_id)
        if state is None or state.state != STATE_UNAVAILABLE:
            continue
        entity_registry.async_remove(entity_entry.entity_id)
        removed_entities += 1

    for device_entry in list(dr.async_entries_for_config_entry(device_registry, entry.entry_id)):
        if er.async_entries_for_device(entity_registry, device_entry.id):
            continue
        device_registry.async_remove_device(device_entry.id)
        removed_devices += 1

    return {
        "entities_removed": removed_entities,
        "devices_removed": removed_devices,
    }
