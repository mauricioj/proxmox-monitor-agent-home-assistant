"""Options flow for the Proxmox Monitor Agent integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .maintenance import async_prune_unavailable_entities


class ProxmoxMonitorAgentOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Proxmox Monitor Agent."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the maintenance action form."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("remove_unavailable_entities", default=False): bool,
                    }
                ),
            )

        if user_input["remove_unavailable_entities"]:
            await async_prune_unavailable_entities(self.hass, self._config_entry)

        return self.async_create_entry(data={})
