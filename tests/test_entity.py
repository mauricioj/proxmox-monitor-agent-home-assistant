"""Tests for shared Proxmox Monitor Agent entity helpers."""

from __future__ import annotations

from custom_components.proxmox_monitor_agent.const import DOMAIN
from custom_components.proxmox_monitor_agent.entity import (
    PmaEntity,
    host_device_info,
    host_id,
    sanitize_id,
    vm_memory_percent,
)


def test_sanitize_id_replaces_non_alnum_groups() -> None:
    """Normalize entity identifier fragments."""
    assert sanitize_id("Node 1/eno.1") == "node_1_eno_1"


def test_sanitize_id_falls_back_to_unknown_for_empty_values() -> None:
    """Return unknown when normalization leaves no identifier content."""
    assert sanitize_id("") == "unknown"
    assert sanitize_id("///...   ") == "unknown"


def test_vm_memory_percent_computes_rounded_percentage() -> None:
    """Compute VM memory usage percentage from byte counters."""
    assert (
        vm_memory_percent({"memory_used_bytes": 50, "memory_total_bytes": 200})
        == 25.0
    )


def test_vm_memory_percent_rounds_to_two_decimals() -> None:
    """Round computed memory usage percentage to two decimal places."""
    assert (
        vm_memory_percent({"memory_used_bytes": 1, "memory_total_bytes": 3})
        == 33.33
    )


def test_vm_memory_percent_returns_none_for_invalid_inputs() -> None:
    """Return None when memory counters are missing, invalid, or unusable."""
    assert vm_memory_percent({"memory_used_bytes": "50", "memory_total_bytes": 200}) is None
    assert vm_memory_percent({"memory_used_bytes": 50, "memory_total_bytes": "200"}) is None
    assert vm_memory_percent({"memory_total_bytes": 200}) is None
    assert vm_memory_percent({"memory_used_bytes": 50}) is None
    assert vm_memory_percent({"memory_used_bytes": 50, "memory_total_bytes": 0}) is None
    assert vm_memory_percent({"memory_used_bytes": 50, "memory_total_bytes": -1}) is None


def test_host_id_prefers_host_id_and_sanitizes_it() -> None:
    """Prefer the host ID over hostname when building host IDs."""
    snapshot = {"host": {"id": "Node 1/eno.1", "hostname": "pve"}}

    assert host_id(snapshot) == "node_1_eno_1"


def test_host_id_falls_back_to_hostname_then_unknown() -> None:
    """Use hostname and then unknown when host ID is unavailable."""
    assert host_id({"host": {"hostname": "PVE A"}}) == "pve_a"
    assert host_id({"host": {"id": "", "hostname": ""}}) == "unknown"
    assert host_id({}) == "unknown"


def test_host_device_info_includes_identifiers_name_and_optional_fields() -> None:
    """Build Home Assistant device info from host metadata."""
    snapshot = {
        "host": {
            "id": "Node 1/eno.1",
            "hostname": "pve-a",
            "manufacturer": "Acme",
            "model": "PX-1",
            "serial_number": "SN123",
            "sw_version": "8.2.4",
        }
    }

    device_info = host_device_info(snapshot, configuration_url="https://pve-a:8006")

    assert device_info["identifiers"] == {(DOMAIN, "node_1_eno_1")}
    assert device_info["name"] == "Proxmox pve-a"
    assert device_info["manufacturer"] == "Acme"
    assert device_info["model"] == "PX-1"
    assert device_info["serial_number"] == "SN123"
    assert device_info["sw_version"] == "8.2.4"
    assert device_info["configuration_url"] == "https://pve-a:8006"


def test_host_device_info_without_optional_fields_includes_required_fields_only() -> None:
    """Build minimal device info when optional host metadata is absent."""
    snapshot = {"host": {"id": "Node 1", "hostname": "pve-a"}}

    device_info = host_device_info(snapshot)

    assert device_info == {
        "identifiers": {(DOMAIN, "node_1")},
        "name": "Proxmox pve-a",
    }


def test_pma_entity_has_entity_name_and_snapshot_reads_coordinator_data() -> None:
    """Expose coordinator data through the base entity snapshot helper."""
    coordinator = type(
        "FakeCoordinator",
        (),
        {"data": {"host": {"hostname": "pve-a"}}, "last_update_success": True},
    )()
    entity = PmaEntity(coordinator)

    assert entity._attr_has_entity_name is True
    assert entity.has_entity_name is True
    assert entity.snapshot == {"host": {"hostname": "pve-a"}}

    coordinator.data = None
    assert entity.snapshot == {}
