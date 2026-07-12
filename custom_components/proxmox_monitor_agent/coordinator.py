"""Data update coordinator for Proxmox Monitor Agent."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PmaApiClient, PmaApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PmaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate PMA metrics updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PmaApiClient,
        scan_interval: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the PMA data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch metrics from the PMA API."""
        try:
            return await self.client.async_fetch_metrics()
        except PmaApiError as err:
            raise UpdateFailed(str(err)) from err
