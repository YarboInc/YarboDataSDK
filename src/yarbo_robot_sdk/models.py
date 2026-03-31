"""Data models for Yarbo Robot SDK."""

from dataclasses import dataclass, field


@dataclass
class Device:
    """Device basic information."""

    sn: str
    type_id: str
    name: str
    model: str
    online: bool
    user_type: str = ""


@dataclass
class FieldDefinition:
    """Structured field definition with HA entity metadata.

    Attributes:
        path: Dot-separated path in MQTT message (e.g. "BatteryMSG.capacity").
              Use "__device__." prefix for fields from Device object (e.g. "__device__.online").
        name: Display name for the entity.
        entity_type: HA entity type — "sensor", "binary_sensor", or "device_tracker".
        device_class: HA device_class (e.g. "battery", "connectivity", "enum").
        unit: Unit of measurement (e.g. "%", "°C", "m").
        icon: MDI icon (e.g. "mdi:battery").
        value_map: Maps raw values to readable strings. Keys are stringified.
        enabled_by_default: Whether the entity is enabled by default in HA.
        category: Field grouping for organization (e.g. "battery", "status", "position").
    """

    path: str
    name: str
    entity_type: str
    device_class: str | None = None
    unit: str | None = None
    icon: str | None = None
    value_map: dict[str, str] | None = None
    enabled_by_default: bool = True
    category: str | None = None
