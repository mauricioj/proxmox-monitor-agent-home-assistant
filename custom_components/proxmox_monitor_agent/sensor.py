"""Sensor platform for the Proxmox Monitor Agent integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import (
    PmaEntity,
    host_device_info,
    host_id,
    sanitize_id,
    vm_memory_percent,
)

Snapshot = Mapping[str, Any]
ValueFn = Callable[[Snapshot], Any]


HOST_SENSOR_DEFINITIONS: tuple[
    tuple[str, str, ValueFn, str | None, SensorDeviceClass | None], ...
] = (
    (
        "collection_status",
        "Collection status",
        lambda data: _nested_get(data, "collection", "status"),
        None,
        None,
    ),
    (
        "collection_duration",
        "Collection duration",
        lambda data: _format_duration_ms(_nested_get(data, "collection", "duration_ms")),
        None,
        None,
    ),
    (
        "cpu_usage_percent",
        "CPU usage",
        lambda data: _nested_get(data, "cpu", "usage_percent"),
        "%",
        None,
    ),
    (
        "load_average_1m",
        "Load average 1m",
        lambda data: _nested_get(data, "cpu", "load_average", "1m"),
        None,
        None,
    ),
    (
        "load_average_5m",
        "Load average 5m",
        lambda data: _nested_get(data, "cpu", "load_average", "5m"),
        None,
        None,
    ),
    (
        "load_average_15m",
        "Load average 15m",
        lambda data: _nested_get(data, "cpu", "load_average", "15m"),
        None,
        None,
    ),
    (
        "memory_used_percent",
        "Memory used",
        lambda data: _nested_get(data, "memory", "used_percent"),
        "%",
        None,
    ),
    (
        "swap_used_percent",
        "Swap used",
        lambda data: _nested_get(data, "memory", "swap_used_percent"),
        "%",
        None,
    ),
    (
        "uptime",
        "Uptime",
        lambda data: _format_duration_seconds(_nested_get(data, "host", "uptime_seconds")),
        None,
        None,
    ),
)

GUEST_SENSOR_DEFINITIONS: tuple[
    tuple[str, str, Callable[[Mapping[str, Any]], Any], str | None, SensorDeviceClass | None], ...
] = (
    ("status", "Status", lambda item: item.get("status"), None, None),
    ("cpu_usage_percent", "CPU usage", lambda item: item.get("cpu_usage_percent"), "%", None),
    ("memory_used_percent", "Memory used", vm_memory_percent, "%", None),
    (
        "uptime",
        "Uptime",
        lambda item: _format_duration_seconds(item.get("uptime_seconds")),
        None,
        None,
    ),
)

NETWORK_SENSOR_DEFINITIONS: tuple[
    tuple[str, str, Callable[[Mapping[str, Any]], Any], str | None, SensorDeviceClass | None], ...
] = (
    ("state", "State", lambda item: item.get("state"), None, None),
    (
        "rx_bytes",
        "RX bytes",
        lambda item: _bytes_to_human(item.get("rx_bytes")),
        None,
        None,
    ),
    (
        "tx_bytes",
        "TX bytes",
        lambda item: _bytes_to_human(item.get("tx_bytes")),
        None,
        None,
    ),
    ("rx_errors", "RX errors", lambda item: item.get("rx_errors"), None, None),
    ("tx_errors", "TX errors", lambda item: item.get("tx_errors"), None, None),
    ("speed_mbps", "Speed", lambda item: item.get("speed_mbps"), "Mbit/s", None),
)

USAGE_SENSOR_DEFINITIONS: tuple[
    tuple[str, str, Callable[[Mapping[str, Any]], Any], str | None, SensorDeviceClass | None], ...
] = (
    ("used_percent", "Used", lambda item: item.get("used_percent"), "%", None),
    (
        "available_bytes",
        "Available",
        lambda item: _bytes_to_human(item.get("available_bytes")),
        None,
        None,
    ),
    (
        "used_bytes",
        "Used bytes",
        lambda item: _bytes_to_human(item.get("used_bytes")),
        None,
        None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PMA sensors from a config entry."""
    coordinator: DataUpdateCoordinator[dict[str, Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]
    snapshot = coordinator.data or {}
    host = host_id(snapshot)
    host_device = host_device_info(snapshot)

    _migrate_sensor_units(hass, entry.entry_id, snapshot)

    entities: list[PmaSensor] = []
    entities.extend(_host_sensors(coordinator, host, host_device))
    entities.extend(_guest_sensors(coordinator, snapshot, host, "vm"))
    entities.extend(_guest_sensors(coordinator, snapshot, host, "lxc"))
    entities.extend(
        _item_sensors(
            coordinator,
            snapshot,
            host,
            "network",
            _network_device_info_factory(host),
            lambda item: _item_label(item, "name", "id"),
            None,
            NETWORK_SENSOR_DEFINITIONS,
        )
    )
    entities.extend(
        _item_sensors(
            coordinator,
            snapshot,
            host,
            "filesystems",
            lambda _item: host_device,
            lambda item: _item_label(item, "mountpoint", "name", "id"),
            "Filesystem",
            USAGE_SENSOR_DEFINITIONS,
        )
    )
    entities.extend(
        _item_sensors(
            coordinator,
            snapshot,
            host,
            "storage",
            lambda _item: host_device,
            lambda item: _item_label(item, "name", "id"),
            "Storage",
            USAGE_SENSOR_DEFINITIONS,
        )
    )
    entities.extend(
        _temperature_sensors(
            coordinator,
            snapshot,
            host,
            host_device,
        )
    )

    async_add_entities(entities)


class PmaSensor(PmaEntity, SensorEntity):
    """Sensor backed by the latest PMA coordinator snapshot."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        unique_id: str,
        name: str,
        device_info: DeviceInfo,
        value_fn: ValueFn,
        native_unit_of_measurement: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        """Initialize the PMA sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._value_fn = value_fn

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the latest snapshot."""
        return self._value_fn(self.snapshot)

    @property
    def available(self) -> bool:
        """Return if the sensor has coordinator data and its value is present."""
        return super().available and self.native_value is not None


def _host_sensors(
    coordinator: DataUpdateCoordinator[dict[str, Any]],
    host: str,
    device_info: DeviceInfo,
) -> list[PmaSensor]:
    """Build host-level sensors."""
    return [
        PmaSensor(
            coordinator,
            f"pma_{host}_{metric}",
            name,
            device_info,
            value_fn,
            unit,
            device_class,
            SensorStateClass.MEASUREMENT if unit is not None and device_class is None else None,
        )
        for metric, name, value_fn, unit, device_class in HOST_SENSOR_DEFINITIONS
    ]


def _guest_sensors(
    coordinator: DataUpdateCoordinator[dict[str, Any]],
    snapshot: Snapshot,
    host: str,
    guest_type: str,
) -> list[PmaSensor]:
    """Build VM or LXC sensors."""
    if guest_type == "vm":
        collection = _list(snapshot, "virtualization", "vms")
        id_key = "vmid"
        label = "VM"
    else:
        collection = _list(snapshot, "virtualization", "containers")
        id_key = "ctid"
        label = "LXC"

    entities: list[PmaSensor] = []
    for item in collection:
        item_id = item.get(id_key)
        if item_id is None:
            continue
        item_fragment = sanitize_id(item_id)
        device_key = f"{host}_{guest_type}_{item_fragment}"
        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, device_key)},
            "name": _guest_name(label, item),
            "via_device": (DOMAIN, host),
        }

        for metric, name, item_value_fn, unit, device_class in GUEST_SENSOR_DEFINITIONS:
            entities.append(
                PmaSensor(
                    coordinator,
                    f"pma_{host}_{guest_type}_{item_fragment}_{metric}",
                    name,
                    device_info,
                    _item_value_fn(
                        ("virtualization", "vms")
                        if guest_type == "vm"
                        else ("virtualization", "containers"),
                        id_key,
                        item_id,
                        item_value_fn,
                    ),
                    unit,
                    device_class,
                    SensorStateClass.MEASUREMENT if unit is not None and device_class is None else None,
                )
            )

    return entities


def _item_sensors(
    coordinator: DataUpdateCoordinator[dict[str, Any]],
    snapshot: Snapshot,
    host: str,
    collection_key: str,
    device_info_fn: Callable[[Mapping[str, Any]], DeviceInfo],
    item_label_fn: Callable[[Mapping[str, Any]], str],
    item_name_prefix: str | None,
    definitions: tuple[
        tuple[str, str, Callable[[Mapping[str, Any]], Any], str | None, SensorDeviceClass | None], ...
    ],
) -> list[PmaSensor]:
    """Build sensors for list items identified by their PMA item id."""
    entities: list[PmaSensor] = []
    for item in _list(snapshot, collection_key):
        item_id = item.get("id")
        if item_id is None:
            continue
        item_fragment = sanitize_id(item_id)
        item_label = item_label_fn(item)
        device_info = device_info_fn(item)

        for metric, name, item_value_fn, unit, device_class in definitions:
            if metric == "speed_mbps" and item.get(metric) is None:
                continue
            if metric.endswith("_bytes"):
                unit = _bytes_unit(item.get(metric))
            if item_name_prefix is None:
                entity_name = name
            else:
                entity_name = f"{item_name_prefix} {item_label} {name}"
            entities.append(
                PmaSensor(
                    coordinator,
                    f"pma_{host}_{item_fragment}_{metric}",
                    entity_name,
                    device_info,
                    _item_value_fn((collection_key,), "id", item_id, item_value_fn),
                    unit,
                    device_class,
                    SensorStateClass.MEASUREMENT if unit is not None and device_class is None else None,
                )
            )

    return entities


def _temperature_sensors(
    coordinator: DataUpdateCoordinator[dict[str, Any]],
    snapshot: Snapshot,
    host: str,
    device_info: DeviceInfo,
) -> list[PmaSensor]:
    """Build host temperature sensors."""
    entities: list[PmaSensor] = []
    for item in _list(snapshot, "sensors", "temperatures"):
        item_id = item.get("id")
        if item_id is None:
            continue

        entities.append(
            PmaSensor(
                coordinator,
                f"pma_{host}_{sanitize_id(item_id)}",
                _item_label(item, "label", "raw_label", "id"),
                device_info,
                _item_value_fn(
                    ("sensors", "temperatures"),
                    "id",
                    item_id,
                    lambda temp: temp.get("value"),
                ),
                UnitOfTemperature.CELSIUS,
                SensorDeviceClass.TEMPERATURE,
                SensorStateClass.MEASUREMENT,
            )
        )

    return entities


def _migrate_sensor_units(hass: HomeAssistant, entry_id: str, snapshot: Snapshot) -> None:
    """Update legacy registry units to the current display units."""
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry_id):
        if entity_entry.domain != "sensor":
            continue
        if not _is_managed_unit_unique_id(entity_entry.unique_id):
            continue
        desired_unit = _desired_unit_for_unique_id(entity_entry.unique_id, snapshot)
        if entity_entry.unit_of_measurement == desired_unit:
            continue
        registry.async_update_entity(
            entity_entry.entity_id,
            unit_of_measurement=desired_unit,
        )


def _desired_unit_for_unique_id(unique_id: str | None, snapshot: Snapshot) -> str | None:
    """Return the target unit for a known sensor unique id."""
    if unique_id is None:
        return None

    if unique_id.endswith("_collection_duration") or unique_id.endswith("_uptime"):
        return None

    if unique_id.endswith("_rx_bytes") or unique_id.endswith("_tx_bytes"):
        value = _raw_bytes_value_for_unique_id(unique_id, snapshot, "network", "id")
        return _bytes_unit(value)

    if unique_id.endswith("_available_bytes") or unique_id.endswith("_used_bytes"):
        value = _raw_bytes_value_for_unique_id(unique_id, snapshot, "filesystems", "id")
        if value is None:
            value = _raw_bytes_value_for_unique_id(unique_id, snapshot, "storage", "id")
        return _bytes_unit(value)

    return None


def _is_managed_unit_unique_id(unique_id: str | None) -> bool:
    """Return whether an entity's unit is managed by this integration."""
    if unique_id is None:
        return False
    return (
        unique_id.endswith("_collection_duration")
        or unique_id.endswith("_uptime")
        or unique_id.endswith("_rx_bytes")
        or unique_id.endswith("_tx_bytes")
        or unique_id.endswith("_available_bytes")
        or unique_id.endswith("_used_bytes")
    )


def _item_value_fn(
    collection_path: tuple[str, ...],
    id_key: str,
    expected_id: object,
    item_value_fn: Callable[[Mapping[str, Any]], Any],
) -> ValueFn:
    """Return a value function that finds an item in the current snapshot."""

    def _value(snapshot: Snapshot) -> Any:
        for item in _list(snapshot, *collection_path):
            if item.get(id_key) == expected_id:
                return item_value_fn(item)
        return None

    return _value


def _bytes_to_human(value: Any) -> float | None:
    """Convert bytes to a human-readable binary unit for display."""
    if not isinstance(value, int | float):
        return None
    if value < 1024:
        return round(value, 2)
    if value < 1024**2:
        return round(value / 1024, 2)
    if value < 1024**3:
        return round(value / 1024**2, 2)
    if value < 1024**4:
        return round(value / 1024**3, 2)
    return round(value / 1024**4, 2)


def _bytes_unit(value: Any) -> str | None:
    """Return the best unit for a byte value."""
    if not isinstance(value, int | float):
        return None
    if value < 1024:
        return "B"
    if value < 1024**2:
        return "KiB"
    if value < 1024**3:
        return "MiB"
    if value < 1024**4:
        return "GiB"
    return "TiB"


def _format_duration_seconds(value: Any) -> str | None:
    """Format seconds as a human-readable duration."""
    if not isinstance(value, int | float):
        return None
    return str(timedelta(seconds=value))


def _format_duration_ms(value: Any) -> str | None:
    """Format milliseconds as a human-readable duration."""
    if not isinstance(value, int | float):
        return None
    return str(timedelta(milliseconds=value))


def _raw_bytes_value_for_unique_id(
    unique_id: str,
    snapshot: Snapshot,
    collection_key: str,
    id_key: str,
) -> Any:
    """Return the raw byte value for a byte sensor unique id."""
    suffix = ""
    if unique_id.endswith("_rx_bytes"):
        suffix = "_rx_bytes"
    elif unique_id.endswith("_tx_bytes"):
        suffix = "_tx_bytes"
    elif unique_id.endswith("_available_bytes"):
        suffix = "_available_bytes"
    elif unique_id.endswith("_used_bytes"):
        suffix = "_used_bytes"
    if not suffix:
        return None

    for item in _list(snapshot, collection_key):
        item_id = item.get(id_key)
        if item_id is None:
            continue
        if unique_id.endswith(f"{sanitize_id(item_id)}{suffix}"):
            metric = suffix.removeprefix("_")
            return item.get(metric)
    return None


def _nested_get(data: Mapping[str, Any], *keys: str) -> Any:
    """Return a nested mapping value or None."""
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _list(data: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    """Return a nested list containing mapping items."""
    value = _nested_get(data, *keys)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _guest_name(label: str, item: Mapping[str, Any]) -> str:
    """Return a display name for a VM or LXC device."""
    item_id = item.get("vmid") if label == "VM" else item.get("ctid")
    name = item.get("name")
    if name:
        return f"{label} {item_id} {name}"
    return f"{label} {item_id}"


def _item_label(item: Mapping[str, Any], *keys: str) -> str:
    """Return a stable display label for a collection item."""
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return "unknown"


def _network_device_info_factory(host: str) -> Callable[[Mapping[str, Any]], DeviceInfo]:
    """Return device info for a network interface under the host device."""

    def _device_info(item: Mapping[str, Any]) -> DeviceInfo:
        item_id = sanitize_id(item.get("id") or item.get("name") or "unknown")
        name = item.get("name") or item.get("id") or item_id
        return {
            "identifiers": {(DOMAIN, f"{host}_nic_{item_id}")},
            "name": f"NIC {name}",
            "via_device": (DOMAIN, host),
        }

    return _device_info
