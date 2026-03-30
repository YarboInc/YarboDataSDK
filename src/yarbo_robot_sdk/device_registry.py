"""Device capability registry.

Declares supported device types, their topics, APIs, status fields,
and control commands. Add new device types to DEVICE_REGISTRY below.
"""

from dataclasses import dataclass, field


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
class DeviceType:
    """Device type with its capabilities."""

    type_id: str
    name: str
    topics: list[TopicDefinition] = field(default_factory=list)
    apis: list[ApiDefinition] = field(default_factory=list)
    status_fields: list[str] = field(default_factory=list)
    control_commands: list[str] = field(default_factory=list)


# ==========================================================================
# Device capability registry — add new device types here
# ==========================================================================
DEVICE_REGISTRY: dict[str, DeviceType] = {
    "mower": DeviceType(
        type_id="mower",
        name="割草机器人",
        topics=[
            TopicDefinition("device_msg", "snowbot/{sn}/device/DeviceMSG", "设备实时信息"),
        ],
        apis=[
            ApiDefinition("device_detail", "GET", "/devices/{sn}", "设备详情"),
        ],
        status_fields=[
            "BatteryMSG.capacity",
            "BatteryMSG.status",
            "StateMSG.working_state",
            "StateMSG.charging_status",
            "StateMSG.error_code",
            "CombinedOdom.x",
            "CombinedOdom.y",
            "CombinedOdom.phi",
        ],
        control_commands=[],  # Phase 2
    ),
    "snowbot": DeviceType(
        type_id="snowbot",
        name="扫雪机器人",
        topics=[
            TopicDefinition("device_msg", "snowbot/{sn}/device/DeviceMSG", "设备实时信息"),
        ],
        apis=[
            ApiDefinition("device_detail", "GET", "/devices/{sn}", "设备详情"),
        ],
        status_fields=[
            "BatteryMSG.capacity",
            "BatteryMSG.status",
            "BatteryMSG.temp_err",
            "StateMSG.working_state",
            "StateMSG.charging_status",
            "StateMSG.error_code",
            "CombinedOdom.x",
            "CombinedOdom.y",
            "CombinedOdom.phi",
            "RTKMSG.status",
            "HeadMsg.head_type",
            "HeadSerialMsg.head_sn",
        ],
        control_commands=[],  # Phase 2
    ),
}


def get_device_type(type_id: str) -> DeviceType | None:
    """Look up a device type by its ID."""
    return DEVICE_REGISTRY.get(type_id)


def list_device_types() -> list[DeviceType]:
    """Return all registered device types."""
    return list(DEVICE_REGISTRY.values())
