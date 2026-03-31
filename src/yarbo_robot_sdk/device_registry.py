"""Device capability registry.

Loads device type definitions from JSON configuration files in the
devices/ directory. Each JSON file defines one device type with its
topics, APIs, field definitions (including HA entity metadata), and
control topic/field definitions for controllable entities.

To add a new device type, create a new JSON file in devices/.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .models import ControlFieldDefinition, FieldDefinition

_LOGGER = logging.getLogger(__name__)

DEVICES_DIR = Path(__file__).parent / "devices"

VALID_ENTITY_TYPES = {"sensor", "binary_sensor", "device_tracker"}
VALID_CONTROL_ENTITY_TYPES = {"select"}


@dataclass
class TopicDefinition:
    """MQTT topic definition."""

    name: str
    template: str
    description: str


@dataclass
class ApiDefinition:
    """REST API endpoint definition."""

    name: str
    method: str
    path_template: str
    description: str


@dataclass
class ControlTopicDefinition:
    """MQTT control (publish) topic definition."""

    name: str
    template: str
    description: str


@dataclass
class DeviceType:
    """Device type with its capabilities."""

    type_id: str
    name: str
    topics: list[TopicDefinition] = field(default_factory=list)
    apis: list[ApiDefinition] = field(default_factory=list)
    status_fields: list[FieldDefinition] = field(default_factory=list)
    control_commands: list[str] = field(default_factory=list)
    control_topics: list[ControlTopicDefinition] = field(default_factory=list)
    control_fields: list[ControlFieldDefinition] = field(default_factory=list)


class DeviceRegistryError(Exception):
    """Raised when a device JSON configuration is invalid."""


def _parse_field(raw: dict, json_file: str) -> FieldDefinition:
    """Parse a single field definition from JSON dict."""
    required = ("path", "name", "entity_type")
    for key in required:
        if key not in raw:
            raise DeviceRegistryError(
                f"Missing required field '{key}' in field definition in {json_file}"
            )

    entity_type = raw["entity_type"]
    if entity_type not in VALID_ENTITY_TYPES:
        raise DeviceRegistryError(
            f"Invalid entity_type '{entity_type}' in {json_file}. "
            f"Must be one of {VALID_ENTITY_TYPES}"
        )

    return FieldDefinition(
        path=raw["path"],
        name=raw["name"],
        entity_type=entity_type,
        device_class=raw.get("device_class"),
        unit=raw.get("unit"),
        icon=raw.get("icon"),
        value_map=raw.get("value_map"),
        enabled_by_default=raw.get("enabled_by_default", True),
        category=raw.get("category"),
    )


def _parse_control_field(raw: dict, json_file: str) -> ControlFieldDefinition:
    """Parse a single control field definition from JSON dict."""
    required = (
        "path", "name", "entity_type",
        "command_topic", "command_key",
        "options", "value_map", "state_value_map",
    )
    for key in required:
        if key not in raw:
            raise DeviceRegistryError(
                f"Missing required field '{key}' in control_field definition in {json_file}"
            )

    entity_type = raw["entity_type"]
    if entity_type not in VALID_CONTROL_ENTITY_TYPES:
        raise DeviceRegistryError(
            f"Invalid entity_type '{entity_type}' in control_fields in {json_file}. "
            f"Must be one of {VALID_CONTROL_ENTITY_TYPES}"
        )

    return ControlFieldDefinition(
        path=raw["path"],
        name=raw["name"],
        entity_type=entity_type,
        command_topic=raw["command_topic"],
        command_key=raw["command_key"],
        options=raw["options"],
        value_map=raw["value_map"],
        state_value_map=raw["state_value_map"],
        icon=raw.get("icon"),
        enabled_by_default=raw.get("enabled_by_default", True),
        category=raw.get("category"),
    )


def _load_device_type(json_file: Path) -> DeviceType:
    """Load a single device type from a JSON file."""
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DeviceRegistryError(
            f"Invalid JSON in {json_file.name}: {e}"
        ) from e

    filename = json_file.name

    if "type_id" not in data:
        raise DeviceRegistryError(f"Missing 'type_id' in {filename}")
    if "name" not in data:
        raise DeviceRegistryError(f"Missing 'name' in {filename}")

    topics = [
        TopicDefinition(
            name=t["name"],
            template=t["template"],
            description=t.get("description", ""),
        )
        for t in data.get("topics", [])
    ]

    apis = [
        ApiDefinition(
            name=a["name"],
            method=a["method"],
            path_template=a["path_template"],
            description=a.get("description", ""),
        )
        for a in data.get("apis", [])
    ]

    fields = [
        _parse_field(f, filename)
        for f in data.get("fields", [])
    ]

    control_topics = [
        ControlTopicDefinition(
            name=ct["name"],
            template=ct["template"],
            description=ct.get("description", ""),
        )
        for ct in data.get("control_topics", [])
    ]

    control_fields = [
        _parse_control_field(cf, filename)
        for cf in data.get("control_fields", [])
    ]

    return DeviceType(
        type_id=data["type_id"],
        name=data["name"],
        topics=topics,
        apis=apis,
        status_fields=fields,
        control_commands=data.get("control_commands", []),
        control_topics=control_topics,
        control_fields=control_fields,
    )


def _load_device_types() -> dict[str, DeviceType]:
    """Scan devices/*.json and build the registry."""
    registry: dict[str, DeviceType] = {}

    if not DEVICES_DIR.exists():
        _LOGGER.warning("Devices directory not found: %s", DEVICES_DIR)
        return registry

    for json_file in sorted(DEVICES_DIR.glob("*.json")):
        try:
            device_type = _load_device_type(json_file)
            registry[device_type.type_id] = device_type
            _LOGGER.debug(
                "Loaded device type '%s' from %s (%d fields, %d control_fields)",
                device_type.type_id,
                json_file.name,
                len(device_type.status_fields),
                len(device_type.control_fields),
            )
        except DeviceRegistryError:
            raise
        except Exception as e:
            raise DeviceRegistryError(
                f"Unexpected error loading {json_file.name}: {e}"
            ) from e

    return registry


# Load registry on module import
DEVICE_REGISTRY: dict[str, DeviceType] = _load_device_types()


def get_device_type(type_id: str) -> DeviceType | None:
    """Look up a device type by its ID."""
    return DEVICE_REGISTRY.get(type_id)


def list_device_types() -> list[DeviceType]:
    """Return all registered device types."""
    return list(DEVICE_REGISTRY.values())


def get_field_definitions(type_id: str) -> list[FieldDefinition]:
    """Return status field definitions for a device type.

    Returns an empty list if the device type is not found.
    """
    device_type = DEVICE_REGISTRY.get(type_id)
    if device_type is None:
        return []
    return device_type.status_fields


def get_control_field_definitions(type_id: str) -> list[ControlFieldDefinition]:
    """Return control field definitions for a device type.

    Returns an empty list if the device type is not found.
    """
    device_type = DEVICE_REGISTRY.get(type_id)
    if device_type is None:
        return []
    return device_type.control_fields


def resolve_control_topic(sn: str, type_id: str, topic_name: str) -> str:
    """Resolve a control topic template for a given device SN.

    Args:
        sn: Device serial number.
        type_id: Device type ID.
        topic_name: Name of the control topic (from control_topics[].name).

    Returns:
        Resolved topic string with {sn} substituted.

    Raises:
        YarboSDKError: If device type or topic name is not found.
    """
    from yarbo_robot_sdk.exceptions import YarboSDKError

    device_type = DEVICE_REGISTRY.get(type_id)
    if device_type is None:
        raise YarboSDKError(f"Unknown device type: {type_id}")
    for ct in device_type.control_topics:
        if ct.name == topic_name:
            return ct.template.replace("{sn}", sn)
    raise YarboSDKError(
        f"No control topic '{topic_name}' defined for device type: {type_id}"
    )
