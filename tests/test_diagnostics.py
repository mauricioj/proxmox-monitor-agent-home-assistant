"""Tests for diagnostics."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proxmox_monitor_agent.const import DOMAIN
from custom_components.proxmox_monitor_agent.diagnostics import (
    async_get_config_entry_diagnostics,
)


def _fake_coordinator(data: dict) -> object:
    """Build a minimal fake coordinator."""
    return type("FakeCoordinator", (), {"data": data})()


async def test_diagnostics_returns_endpoint_and_collection_summary(hass) -> None:
    """Diagnostics include endpoint and collection summaries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "pve01.local", "port": 9782, "path": "/metrics.json"},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _fake_coordinator(
        {
            "schema": {"name": "pma.metrics", "version": 1},
            "collection": {
                "status": "partial",
                "generated_at": "2026-07-06T12:00:00Z",
                "duration_ms": 842,
                "errors": [{"module": "network", "message": "timeout"}],
            },
            "host": {"id": "node-1", "hostname": "pve01"},
            "network": [{"id": "eno1", "rx_bytes": 1000}],
        }
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["endpoint"] == {
        "host": "pve01.local",
        "port": 9782,
        "path": "/metrics.json",
    }
    assert result["schema"] == {"name": "pma.metrics", "version": 1}
    assert result["collection"]["status"] == "partial"
    assert result["collection"]["generated_at"] == "2026-07-06T12:00:00Z"
    assert result["collection"]["duration_ms"] == 842
    assert result["collection"]["error_count"] == 1
    assert result["collection"]["errors"] == [{"module": "network", "message": "timeout"}]


async def test_diagnostics_preserves_collection_summary_fields(hass) -> None:
    """Diagnostics preserve collection timing and error metadata."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "pve01.local"})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _fake_coordinator(
        {
            "collection": {
                "status": "ok",
                "generated_at": "2026-07-06T12:00:00Z",
                "duration_ms": 123,
                "error_count": 0,
                "errors": [],
            },
            "host": {"id": "node-1", "hostname": "pve01"},
        }
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["collection"] == {
        "status": "ok",
        "generated_at": "2026-07-06T12:00:00Z",
        "duration_ms": 123,
        "error_count": 0,
        "errors": [],
    }


async def test_diagnostics_includes_host_identity_and_stays_compact(hass) -> None:
    """Diagnostics include host identity without raw snapshot payloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "pve01.local", "port": 9782, "path": "/metrics.json"},
    )
    huge_raw = {"nested": {"lots": ["of", "data"]}}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _fake_coordinator(
        {
            "schema": {"name": "pma.metrics", "version": 1},
            "collection": {
                "status": "ok",
                "generated_at": "2026-07-06T12:00:00Z",
                "duration_ms": 10,
                "errors": [],
            },
            "host": {"id": "node-1", "hostname": "pve01"},
            "network": huge_raw,
            "virtualization": huge_raw,
            "filesystems": huge_raw,
        }
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["host_identity"] == {"id": "node-1", "hostname": "pve01"}
    assert "network" not in result
    assert "virtualization" not in result
    assert "filesystems" not in result
    assert set(result) == {"endpoint", "schema", "collection", "host_identity"}
