# Proxmox Monitor Agent for Home Assistant

[![Release](https://img.shields.io/github/v/tag/mauricioj/proxmox-monitor-agent-home-assistant?label=release)](https://github.com/mauricioj/proxmox-monitor-agent-home-assistant/releases)

Custom Home Assistant integration for Proxmox Monitor Agent.

The integration polls an existing Proxmox Monitor Agent HTTP endpoint and creates Home Assistant devices and entities from PMA Schema v1 snapshots.

Example payload: `examples/metrics.example.json`

## Installation

Use HACS as a custom repository or copy `custom_components/proxmox_monitor_agent` into your Home Assistant `custom_components` directory.

For HACS, add this repository as a custom repository and use the current release tag.

Restart Home Assistant after installing the integration.

## Scope

This integration does not install the Proxmox agent, use SSH, publish MQTT discovery, or manage history outside Home Assistant.

## Configuration

The config flow asks for:

- Host
- Port, default `9782`
- Metrics path, default `/metrics.json`
- Scan interval, default from the agent health endpoint when available

One config entry represents one Proxmox host. Add another entry for each additional host.

## Default Endpoint

- Health: `http://<host>:9782/health`
- Metrics: `http://<host>:9782/metrics.json`

## First Version Entities

- Host status and resource sensors
- VM and LXC status, CPU, memory percent, and uptime
- Network interface counters
- Filesystem and storage usage sensors

## Diagnostics

The integration exposes a compact diagnostics view with endpoint, schema, collection, and host identity summaries.
