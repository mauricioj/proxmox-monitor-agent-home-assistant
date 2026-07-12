"""Tests for the Proxmox Monitor Agent coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proxmox_monitor_agent import async_setup_entry, async_unload_entry
from custom_components.proxmox_monitor_agent.api import (
    PmaApiConnectionError,
    PmaApiError,
)
from custom_components.proxmox_monitor_agent.const import (
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from custom_components.proxmox_monitor_agent.coordinator import PmaDataUpdateCoordinator


@pytest.mark.asyncio
async def test_async_setup_entry_refreshes_stores_and_forwards_platforms(
    hass, monkeypatch
) -> None:
    """Refresh, store the coordinator, and forward platforms on setup."""
    events: list[str] = []
    forwarded_coordinators: list[PmaDataUpdateCoordinator] = []
    client = AsyncMock()

    async def forward_entry_setups(entry, platforms) -> None:
        events.append("forward")
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert isinstance(coordinator, PmaDataUpdateCoordinator)
        forwarded_coordinators.append(coordinator)

    forward_setups = AsyncMock(side_effect=forward_entry_setups)

    async def first_refresh(coordinator: PmaDataUpdateCoordinator) -> None:
        events.append("refresh")
        coordinator.data = {"schema": {"name": "pma.metrics", "version": 1}}

    monkeypatch.setattr(
        "custom_components.proxmox_monitor_agent.PmaApiClient",
        lambda *args: client,
    )
    monkeypatch.setattr(
        PmaDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        first_refresh,
    )
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        forward_setups,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "pma.local",
            CONF_PORT: 9782,
            CONF_PATH: "/metrics.json",
            CONF_SCAN_INTERVAL: 60,
        },
    )

    result = await async_setup_entry(hass, entry)

    assert result is True
    assert isinstance(hass.data[DOMAIN][entry.entry_id], PmaDataUpdateCoordinator)
    assert hass.data[DOMAIN][entry.entry_id].data == {
        "schema": {"name": "pma.metrics", "version": 1}
    }
    assert forwarded_coordinators == [hass.data[DOMAIN][entry.entry_id]]
    assert events == ["refresh", "forward"]
    forward_setups.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_unload_entry_removes_state_when_platform_unload_succeeds(
    hass, monkeypatch
) -> None:
    """Remove stored integration state after a successful platform unload."""
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = object()
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    unload_platforms = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
    unload_platforms.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_unload_entry_leaves_state_when_platform_unload_fails(
    hass, monkeypatch
) -> None:
    """Keep stored integration state when platform unload fails."""
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = object()
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    unload_platforms = AsyncMock(return_value=False)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    result = await async_unload_entry(hass, entry)

    assert result is False
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    unload_platforms.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_unload_entry_ignores_missing_state_when_platform_unload_succeeds(
    hass, monkeypatch
) -> None:
    """Do not fail cleanup when unload succeeds but entry state is already absent."""
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data[DOMAIN] = {}
    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    )

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_async_update_data_stores_fetched_metrics(hass) -> None:
    """Store metrics returned by the PMA API client."""
    metrics = {"schema": {"name": "pma.metrics", "version": 1}}
    client = AsyncMock()
    client.async_fetch_metrics.return_value = metrics
    coordinator = PmaDataUpdateCoordinator(hass, client, 60)

    await coordinator.async_refresh()

    assert coordinator.data == metrics
    client.async_fetch_metrics.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        PmaApiError("api failed"),
        PmaApiConnectionError("connection failed"),
    ],
)
async def test_async_update_data_maps_api_errors_to_update_failed(
    hass, error: PmaApiError
) -> None:
    """Map PMA API errors to Home Assistant update failures."""
    client = AsyncMock()
    client.async_fetch_metrics.side_effect = error
    coordinator = PmaDataUpdateCoordinator(hass, client, 60)

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert str(err.value) == str(error)
