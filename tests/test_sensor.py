"""Tests for Proxmox Monitor Agent sensors."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import custom_components
import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proxmox_monitor_agent.const import (
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def pma_custom_components_path() -> None:
    """Enable Home Assistant discovery for this custom integration."""
    custom_components.__path__ = [
        path for path in custom_components.__path__ if Path(path).is_dir()
    ]


@pytest.fixture
def schema_v1_ok() -> dict:
    """Load a complete schema v1 PMA metrics snapshot."""
    fixture_path = Path(__file__).parent / "fixtures" / "schema_v1_ok.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def schema_v1_missing_dynamic_item() -> dict:
    """Load a snapshot where a dynamic item has disappeared."""
    fixture_path = Path(__file__).parent / "fixtures" / "schema_v1_missing_dynamic_item.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


async def _setup_integration(hass, snapshot: dict) -> MockConfigEntry:
    """Set up the PMA integration with a fixed metrics snapshot."""
    return await _setup_integration_with_side_effect(hass, [snapshot])


async def _setup_integration_with_side_effect(
    hass, snapshots: list[dict]
) -> MockConfigEntry:
    """Set up the PMA integration with sequential metrics snapshots."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "pve01.local",
            CONF_PORT: 9782,
            CONF_PATH: "/metrics.json",
            CONF_SCAN_INTERVAL: 60,
        },
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.async_fetch_metrics.side_effect = snapshots

    with patch(
        "custom_components.proxmox_monitor_agent.PmaApiClient",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True

    await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_setup_creates_expected_sensor_unique_ids(
    hass, enable_custom_integrations, pma_custom_components_path, schema_v1_ok
) -> None:
    """Create entity registry entries for host, guest, network, and storage data."""
    await _setup_integration(hass, schema_v1_ok)

    registry = er.async_get(hass)
    expected_unique_ids = {
        "pma_node_1_collection_status",
        "pma_node_1_collection_duration",
        "pma_node_1_cpu_usage_percent",
        "pma_node_1_load_average_1m",
        "pma_node_1_load_average_5m",
        "pma_node_1_load_average_15m",
        "pma_node_1_memory_used_percent",
        "pma_node_1_swap_used_percent",
        "pma_node_1_uptime",
        "pma_node_1_vm_100_status",
        "pma_node_1_vm_100_cpu_usage_percent",
        "pma_node_1_vm_100_memory_used_percent",
        "pma_node_1_vm_100_uptime",
        "pma_node_1_lxc_200_status",
        "pma_node_1_lxc_200_cpu_usage_percent",
        "pma_node_1_lxc_200_memory_used_percent",
        "pma_node_1_lxc_200_uptime",
        "pma_node_1_eno1_state",
        "pma_node_1_eno1_rx_bytes",
        "pma_node_1_eno1_tx_bytes",
        "pma_node_1_eno1_rx_errors",
        "pma_node_1_eno1_tx_errors",
        "pma_node_1_eno1_speed_mbps",
        "pma_node_1_root_used_percent",
        "pma_node_1_root_available_bytes",
        "pma_node_1_root_used_bytes",
        "pma_node_1_local_lvm_used_percent",
        "pma_node_1_local_lvm_available_bytes",
        "pma_node_1_local_lvm_used_bytes",
        "pma_node_1_coretemp_isa_0000_package_id_0_temp1_input",
        "pma_node_1_coretemp_isa_0000_core_0_temp2_input",
        "pma_node_1_coretemp_isa_0000_core_1_temp3_input",
        "pma_node_1_coretemp_isa_0000_core_2_temp4_input",
        "pma_node_1_coretemp_isa_0000_core_3_temp5_input",
    }

    for unique_id in expected_unique_ids:
        assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None


@pytest.mark.asyncio
async def test_setup_creates_representative_sensor_states(
    hass, enable_custom_integrations, pma_custom_components_path, schema_v1_ok
) -> None:
    """Expose representative state values from the current metrics snapshot."""
    await _setup_integration(hass, schema_v1_ok)

    registry = er.async_get(hass)

    def state_for(unique_id: str) -> str:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state.state

    assert state_for("pma_node_1_cpu_usage_percent") == "12.5"
    assert state_for("pma_node_1_vm_100_memory_used_percent") == "50.0"
    assert state_for("pma_node_1_lxc_200_status") == "stopped"
    assert state_for("pma_node_1_eno1_rx_bytes") == "10.0"
    assert state_for("pma_node_1_root_used_percent") == "55.0"
    assert state_for("pma_node_1_local_lvm_used_percent") == "70.0"
    assert state_for("pma_node_1_root_available_bytes") == "20.01"
    assert state_for("pma_node_1_local_lvm_available_bytes") == "1.91"
    assert state_for("pma_node_1_uptime") == "1 day, 22:36:26"
    assert state_for("pma_node_1_coretemp_isa_0000_package_id_0_temp1_input") == "57"
    assert state_for("pma_node_1_coretemp_isa_0000_core_0_temp2_input") == "56"

    def attrs_for(unique_id: str) -> dict:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return dict(state.attributes)

    assert attrs_for("pma_node_1_eno1_rx_bytes")["unit_of_measurement"] == "GiB"
    assert attrs_for("pma_node_1_root_available_bytes")["unit_of_measurement"] == "GiB"
    assert attrs_for("pma_node_1_local_lvm_available_bytes")["unit_of_measurement"] == "MiB"
    assert "unit_of_measurement" not in attrs_for("pma_node_1_uptime")
    assert attrs_for("pma_node_1_coretemp_isa_0000_package_id_0_temp1_input")["device_class"] == "temperature"


@pytest.mark.asyncio
async def test_setup_uses_contextual_sensor_names(
    hass, enable_custom_integrations, pma_custom_components_path, schema_v1_ok
) -> None:
    """Expose item-specific names for host device sensors."""
    await _setup_integration(hass, schema_v1_ok)

    registry = er.async_get(hass)

    def original_name_for(unique_id: str) -> str:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None
        entity_entry = registry.entities.get(entity_id)
        assert entity_entry is not None
        assert entity_entry.original_name is not None
        return entity_entry.original_name

    assert original_name_for("pma_node_1_eno1_tx_bytes") == "TX bytes"
    assert original_name_for("pma_node_1_root_used_bytes") == "Filesystem / Used bytes"
    assert original_name_for("pma_node_1_local_lvm_used_bytes") == "Storage local-lvm Used bytes"
    assert original_name_for("pma_node_1_coretemp_isa_0000_package_id_0_temp1_input") == "Package id 0"


@pytest.mark.asyncio
async def test_setup_creates_host_and_guest_devices(
    hass, enable_custom_integrations, pma_custom_components_path, schema_v1_ok
) -> None:
    """Create device registry entries for the host, VM, and LXC container."""
    await _setup_integration(hass, schema_v1_ok)

    registry = dr.async_get(hass)

    assert registry.async_get_device({(DOMAIN, "node_1")}) is not None
    vm_device = registry.async_get_device({(DOMAIN, "node_1_vm_100")})
    lxc_device = registry.async_get_device({(DOMAIN, "node_1_lxc_200")})

    assert vm_device is not None
    assert vm_device.name == "VM 100 ha-test-vm"
    assert lxc_device is not None
    assert lxc_device.name == "LXC 200 ha-test-lxc"


@pytest.mark.asyncio
async def test_setup_creates_nic_devices(
    hass, enable_custom_integrations, pma_custom_components_path, schema_v1_ok
) -> None:
    """Create a dedicated device for each network interface."""
    await _setup_integration(hass, schema_v1_ok)

    registry = dr.async_get(hass)
    nic_device = registry.async_get_device({(DOMAIN, "node_1_nic_eno1")})
    assert nic_device is not None
    assert nic_device.name == "NIC eno1"
    assert nic_device.via_device_id is not None

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "pma_node_1_eno1_tx_bytes"
    )
    assert entity_id is not None
    assert entity_registry.entities[entity_id].original_name == "TX bytes"


@pytest.mark.asyncio
async def test_dynamic_item_disappears_entity_becomes_unavailable(
    hass,
    enable_custom_integrations,
    pma_custom_components_path,
    schema_v1_ok,
    schema_v1_missing_dynamic_item,
) -> None:
    """Keep existing entities registered and mark them unavailable after refresh."""
    entry = await _setup_integration_with_side_effect(
        hass,
        [schema_v1_ok, schema_v1_missing_dynamic_item],
    )

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "pma_node_1_eno1_rx_bytes")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "10.0"

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert registry.async_get_entity_id("sensor", DOMAIN, "pma_node_1_eno1_rx_bytes") == entity_id
    assert hass.states.get(entity_id).state == "unavailable"
