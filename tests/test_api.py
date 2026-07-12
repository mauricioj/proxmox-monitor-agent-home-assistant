"""Tests for the Proxmox Monitor Agent API client."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import aiohttp
from aioresponses import aioresponses

from custom_components.proxmox_monitor_agent import api
from custom_components.proxmox_monitor_agent.api import (
    PmaApiClient,
    PmaApiConnectionError,
    PmaApiSchemaError,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
async def api_client_session(monkeypatch: pytest.MonkeyPatch) -> aiohttp.ClientSession:
    """Provide a plain aiohttp session for API unit tests."""
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        monkeypatch.setattr(api, "async_get_clientsession", lambda hass: session)
        yield session


@pytest.mark.asyncio
async def test_async_fetch_metrics_succeeds_and_validates_schema_v1(api_client_session) -> None:
    """Fetch metrics and validate PMA schema v1."""
    payload = load_fixture("schema_v1_ok.json")
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, payload=payload)

        result = await client.async_fetch_metrics()

    assert result["schema"]["version"] == 1
    assert result["collection"]["status"] == "ok"
    assert result["host"]["hostname"] == "pve01"
    assert result["network"][0]["id"] == "eno1"
    assert result["virtualization"]["vms"][0]["vmid"] == 100


@pytest.mark.asyncio
async def test_async_fetch_metrics_defaults_optional_collections(api_client_session) -> None:
    """Default missing PMA collection arrays."""
    payload = {
        "schema": {"name": "pma.metrics", "version": 1},
        "collection": {"status": "ok", "errors": []},
        "host": {"id": "node-1", "hostname": "pve01"},
        "virtualization": {},
    }
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, payload=payload)

        result = await client.async_fetch_metrics()

    assert result["network"] == []
    assert result["filesystems"] == []
    assert result["storage"] == []
    assert result["sensors"]["temperatures"] == []
    assert result["sensors"]["fans"] == []
    assert result["sensors"]["voltages"] == []
    assert result["sensors"]["power"] == []
    assert result["virtualization"]["vms"] == []
    assert result["virtualization"]["containers"] == []


@pytest.mark.asyncio
async def test_async_fetch_metrics_normalizes_null_optional_collections(api_client_session) -> None:
    """Default null PMA collection arrays."""
    payload = {
        "schema": {"name": "pma.metrics", "version": 1},
        "collection": {"status": "ok", "errors": []},
        "host": {"id": "node-1", "hostname": "pve01"},
        "network": None,
        "filesystems": None,
        "storage": None,
        "virtualization": {
            "vms": None,
            "containers": None,
        },
    }
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, payload=payload)

        result = await client.async_fetch_metrics()

    assert result["network"] == []
    assert result["filesystems"] == []
    assert result["storage"] == []
    assert result["sensors"]["temperatures"] == []
    assert result["sensors"]["fans"] == []
    assert result["sensors"]["voltages"] == []
    assert result["sensors"]["power"] == []
    assert result["virtualization"]["vms"] == []
    assert result["virtualization"]["containers"] == []


@pytest.mark.asyncio
async def test_async_fetch_metrics_accepts_partial_collection_status(api_client_session) -> None:
    """Accept partial PMA snapshots without changing collection status."""
    payload = load_fixture("schema_v1_partial.json")
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, payload=payload)

        result = await client.async_fetch_metrics()

    assert result["collection"]["status"] == "partial"


@pytest.mark.asyncio
async def test_async_fetch_metrics_rejects_unsupported_schema(api_client_session) -> None:
    """Reject metrics with an unsupported schema version."""
    payload = load_fixture("schema_v2_unsupported.json")
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, payload=payload)

        with pytest.raises(PmaApiSchemaError):
            await client.async_fetch_metrics()


@pytest.mark.asyncio
async def test_async_fetch_metrics_maps_http_503_to_connection_error(api_client_session) -> None:
    """Map HTTP 503 responses to connection errors."""
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, status=503)

        with pytest.raises(PmaApiConnectionError):
            await client.async_fetch_metrics()


@pytest.mark.asyncio
async def test_async_fetch_metrics_maps_timeout_to_connection_error(api_client_session) -> None:
    """Map timeouts to connection errors."""
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.metrics_url, exception=asyncio.TimeoutError())

        with pytest.raises(PmaApiConnectionError):
            await client.async_fetch_metrics()


@pytest.mark.asyncio
async def test_async_fetch_health_returns_health_json(api_client_session) -> None:
    """Fetch PMA health JSON."""
    payload = {"status": "ok", "version": "0.1.0"}
    client = PmaApiClient(object(), "pve01.local", 9782, "/metrics.json")

    with aioresponses() as mocked:
        mocked.get(client.health_url, payload=payload)

        result = await client.async_fetch_health()

    assert result == payload
