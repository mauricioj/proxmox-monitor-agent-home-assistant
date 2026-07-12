"""Test configuration for Proxmox Monitor Agent."""

from __future__ import annotations

import asyncio
import sys

import pytest
import pytest_socket

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Use a selector loop on Windows so pytest-socket can create test loops."""
    policy = asyncio.get_event_loop_policy()
    if sys.platform == "win32":
        policy._loop_factory = asyncio.SelectorEventLoop  # type: ignore[attr-defined]
        policy.new_event_loop = asyncio.SelectorEventLoop  # type: ignore[method-assign]
    return policy


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef):
    """Allow sockets before pytest-asyncio creates the event loop."""
    if fixturedef.argname == "event_loop":
        pytest_socket.enable_socket()
        try:
            yield
        finally:
            pytest_socket.disable_socket(allow_unix_socket=True)
    else:
        yield
