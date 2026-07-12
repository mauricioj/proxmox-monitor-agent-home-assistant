"""API client for Proxmox Monitor Agent."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class PmaApiError(Exception):
    """Base error for PMA API failures."""


class PmaApiConnectionError(PmaApiError):
    """Raised when PMA cannot be reached or returns an HTTP/API transport error."""


class PmaApiSchemaError(PmaApiError):
    """Raised when PMA returns an unsupported or invalid schema."""


def validate_schema(payload: dict[str, Any]) -> None:
    """Validate a PMA metrics payload schema."""
    schema = payload.get("schema")
    if not isinstance(schema, dict):
        raise PmaApiSchemaError("Missing PMA schema")

    if schema.get("name") != "pma.metrics" or schema.get("version") != 1:
        raise PmaApiSchemaError("Unsupported PMA schema")


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize optional PMA metrics collections."""
    normalized = dict(payload)

    for key in ("network", "filesystems", "storage"):
        if not isinstance(normalized.get(key), list):
            normalized[key] = []

    sensors = normalized.get("sensors")
    if isinstance(sensors, dict):
        normalized["sensors"] = dict(sensors)
        for key in ("temperatures", "fans", "voltages", "power"):
            if not isinstance(normalized["sensors"].get(key), list):
                normalized["sensors"][key] = []
    else:
        normalized["sensors"] = {
            "temperatures": [],
            "fans": [],
            "voltages": [],
            "power": [],
        }

    virtualization = normalized.get("virtualization")
    if isinstance(virtualization, dict):
        normalized["virtualization"] = dict(virtualization)
        for key in ("vms", "containers"):
            if not isinstance(normalized["virtualization"].get(key), list):
                normalized["virtualization"][key] = []
    else:
        normalized["virtualization"] = {"vms": [], "containers": []}

    return normalized


class PmaApiClient:
    """Client for a Proxmox Monitor Agent instance."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, path: str) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._host = host.removesuffix("/")
        self._port = port
        self._path = path if path.startswith("/") else f"/{path}"

    @property
    def base_url(self) -> str:
        """Return the API base URL."""
        if self._host.startswith(("http://", "https://")):
            return f"{self._host}:{self._port}"
        return f"http://{self._host}:{self._port}"

    @property
    def metrics_url(self) -> str:
        """Return the metrics endpoint URL."""
        return f"{self.base_url}{self._path}"

    @property
    def health_url(self) -> str:
        """Return the health endpoint URL."""
        return f"{self.base_url}/health"

    async def async_fetch_health(self) -> dict[str, Any]:
        """Fetch PMA health data."""
        return await self._async_get_json(self.health_url)

    async def async_fetch_metrics(self) -> dict[str, Any]:
        """Fetch and normalize PMA metrics."""
        payload = await self._async_get_json(self.metrics_url)
        validate_schema(payload)
        return normalize_snapshot(payload)

    async def _async_get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON from a PMA endpoint."""
        session = async_get_clientsession(self._hass)

        try:
            async with session.get(url) as response:
                if response.status >= 400:
                    raise PmaApiConnectionError(
                        f"PMA endpoint returned HTTP {response.status}"
                    )
                payload = await response.json()
        except PmaApiConnectionError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, TypeError, ValueError) as err:
            raise PmaApiConnectionError("Failed to fetch PMA endpoint") from err

        if not isinstance(payload, dict):
            raise PmaApiSchemaError("PMA endpoint returned a non-object JSON root")

        return payload
