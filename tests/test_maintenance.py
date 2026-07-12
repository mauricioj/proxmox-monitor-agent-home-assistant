"""Tests for manual maintenance actions."""

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
    """Load a snapshot where dynamic items have disappeared."""
    fixture_path = Path(__file__).parent / "fixtures" / "schema_v1_missing_dynamic_item.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


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
async def test_prune_unavailable_entities_removes_only_missing_snapshot_entries(
    hass,
    enable_custom_integrations,
    pma_custom_components_path,
    schema_v1_ok,
    schema_v1_missing_dynamic_item,
) -> None:
    """Remove only entities that are currently unavailable."""
    entry = await _setup_integration_with_side_effect(
        hass,
        [schema_v1_ok, schema_v1_missing_dynamic_item],
    )

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    from custom_components.proxmox_monitor_agent.maintenance import (
        async_prune_unavailable_entities,
    )

    result = await async_prune_unavailable_entities(hass, entry)
    assert result["entities_removed"] > 0

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "pma_node_1_cpu_usage_percent"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "pma_node_1_eno1_rx_bytes"
        )
        is None
    )
    assert device_registry.async_get_device({(DOMAIN, "node_1")}) is not None
    assert device_registry.async_get_device({(DOMAIN, "node_1_nic_eno1")}) is None
    assert device_registry.async_get_device({(DOMAIN, "node_1_vm_100")}) is None
