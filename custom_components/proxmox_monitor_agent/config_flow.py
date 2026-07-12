"""Config flow for the Proxmox Monitor Agent integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import PmaApiClient, PmaApiConnectionError, PmaApiSchemaError
from .const import (
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .options_flow import ProxmoxMonitorAgentOptionsFlow

_LOGGER = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalize a metrics path for storage and unique ids."""
    return path if path.startswith("/") else f"/{path}"


def _unique_id(host: str, port: int, path: str) -> str:
    """Return the endpoint unique id."""
    return f"{host}:{port}{_normalize_path(path)}"


@callback
def _data_schema() -> vol.Schema:
    """Return the user step data schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_PATH, default=DEFAULT_PATH): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        }
    )


class ProxmoxMonitorAgentConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Proxmox Monitor Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_data_schema(),
                errors=errors,
            )

        host = user_input[CONF_HOST].strip()
        port = user_input[CONF_PORT]
        path = _normalize_path(user_input[CONF_PATH].strip())
        scan_interval = user_input[CONF_SCAN_INTERVAL]
        data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_PATH: path,
            CONF_SCAN_INTERVAL: scan_interval,
        }
        unique_id = _unique_id(host, port, path)

        if any(entry.unique_id == unique_id for entry in self._async_current_entries()):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(unique_id)

        client = PmaApiClient(self.hass, host, port, path)
        try:
            await client.async_fetch_metrics()
        except PmaApiConnectionError:
            errors["base"] = "cannot_connect"
        except PmaApiSchemaError:
            errors["base"] = "invalid_schema"
        except Exception:
            _LOGGER.exception("Unexpected error validating PMA endpoint")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=host, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return ProxmoxMonitorAgentOptionsFlow(config_entry)
