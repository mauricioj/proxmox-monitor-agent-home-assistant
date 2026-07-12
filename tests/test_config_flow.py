"""Tests for the Proxmox Monitor Agent config flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import custom_components
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.proxmox_monitor_agent.api import (
    PmaApiConnectionError,
    PmaApiSchemaError,
)
from custom_components.proxmox_monitor_agent.const import (
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


USER_INPUT = {
    CONF_HOST: "pve01.local",
    CONF_PORT: DEFAULT_PORT,
    CONF_PATH: DEFAULT_PATH,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


@pytest.fixture
def pma_config_flow(hass, enable_custom_integrations) -> None:
    """Enable Home Assistant flow manager discovery for this custom integration."""
    custom_components.__path__ = [
        path for path in custom_components.__path__ if Path(path).is_dir()
    ]


@pytest.mark.asyncio
async def test_user_step_shows_form(hass, pma_config_flow) -> None:
    """Show the user form when no input is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_user_input_creates_entry_when_metrics_fetch_succeeds(
    hass, pma_config_flow
) -> None:
    """Create a config entry after validating the PMA metrics endpoint."""
    client = AsyncMock()

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
        return_value=client,
    ) as client_cls, patch(
        "custom_components.proxmox_monitor_agent.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "pve01.local"
    assert result["data"] == USER_INPUT
    client_cls.assert_called_once_with(
        hass,
        USER_INPUT[CONF_HOST],
        USER_INPUT[CONF_PORT],
        USER_INPUT[CONF_PATH],
    )
    client.async_fetch_metrics.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_input_preserves_user_scan_interval(
    hass, pma_config_flow
) -> None:
    """Store a user-provided scan interval in the config entry data."""
    client = AsyncMock()
    user_input = {**USER_INPUT, CONF_SCAN_INTERVAL: 30}

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
        return_value=client,
    ), patch(
        "custom_components.proxmox_monitor_agent.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_SCAN_INTERVAL] == 30


@pytest.mark.asyncio
async def test_user_input_connection_error_shows_cannot_connect(
    hass, pma_config_flow
) -> None:
    """Map PMA connection errors to a cannot_connect form error."""
    client = AsyncMock()
    client.async_fetch_metrics.side_effect = PmaApiConnectionError

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_input_schema_error_shows_invalid_schema(
    hass, pma_config_flow
) -> None:
    """Map PMA schema errors to an invalid_schema form error."""
    client = AsyncMock()
    client.async_fetch_metrics.side_effect = PmaApiSchemaError

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_schema"}


@pytest.mark.asyncio
async def test_user_input_unexpected_error_shows_unknown(
    hass, pma_config_flow
) -> None:
    """Map unexpected validation errors to an unknown form error."""
    client = AsyncMock()
    client.async_fetch_metrics.side_effect = RuntimeError("boom")

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_user_input_duplicate_unique_id_aborts_already_configured(
    hass, pma_config_flow
) -> None:
    """Abort when the endpoint unique id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="pve01.local:9782/metrics.json",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.proxmox_monitor_agent.config_flow.PmaApiClient",
    ) as client_cls:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_options_flow_triggers_manual_prune_action(
    hass, pma_config_flow
) -> None:
    """Expose the manual prune action through the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.proxmox_monitor_agent.options_flow.async_prune_unavailable_entities",
        AsyncMock(return_value={"entities_removed": 1, "devices_removed": 1}),
    ) as prune:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"remove_unavailable_entities": True},
        )

    assert result["type"] == "create_entry"
    prune.assert_awaited_once_with(hass, entry)
