"""Data models for Yarbo Robot SDK."""

from dataclasses import dataclass


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
        custom_extractor: Name of a special extraction function (e.g. "network_priority").
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
    custom_extractor: str | None = None


@dataclass
class ControlFieldDefinition:
    """Field definition for a controllable HA entity (select, switch, number).

    Attributes:
        path: Dot-separated path to read the current state value from MQTT data
              (e.g. "HeartBeatMSG.working_state").
        name: Display name for the entity.
        entity_type: HA entity type — "select", "switch", or "number".
        command_topic: Name reference to a control_topic entry (used to resolve
                       the publish topic template, e.g. "set_working_state").
        command_key: Key used in the command payload dict for select entities
                     (e.g. "state" → publishes {"state": <raw_value>}).
        options: Human-readable option list for select entities.
        value_map: Maps each option to the raw command value for select entities.
        state_value_map: Maps raw state value strings to options for select entities.
        extra_payload: Extra fields merged into the command payload (e.g. {"source": "smart_home"}).
        command_builder: Named strategy for building the command payload
                         (e.g. "sound_switch", "sound_volume", "light_switch").
        min_value: Minimum value for number entities.
        max_value: Maximum value for number entities.
        step: Step size for number entities.
        unit: Unit of measurement for number entities (e.g. "%").
        icon: MDI icon (e.g. "mdi:play-pause").
        enabled_by_default: Whether the entity is enabled by default in HA.
        category: Field grouping for organization (e.g. "control").
    """

    path: str
    name: str
    entity_type: str
    command_topic: str
    command_key: str | None = None
    options: list[str] | None = None
    value_map: dict[str, int] | None = None
    state_value_map: dict[str, str] | None = None
    extra_payload: dict | None = None
    command_builder: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    unit: str | None = None
    icon: str | None = None
    enabled_by_default: bool = True
    category: str | None = None
