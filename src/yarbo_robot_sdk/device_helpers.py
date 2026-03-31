"""High-level device helpers — resolve topics and extract nested fields."""

from typing import Any

from yarbo_robot_sdk.device_registry import get_device_type
from yarbo_robot_sdk.exceptions import YarboSDKError


def resolve_device_msg_topic(sn: str, type_id: str) -> str:
    """Look up the DeviceMSG topic template for a device type and substitute the SN.

    Args:
        sn: Device serial number.
        type_id: Device type ID (e.g. "mower", "snowbot").

    Returns:
        Resolved topic string (e.g. "snowbot/SN001/device/DeviceMSG").

    Raises:
        YarboSDKError: If device type is unknown or has no device_msg topic.
    """
    device_type = get_device_type(type_id)
    if device_type is None:
        raise YarboSDKError(f"Unknown device type: {type_id}")
    for topic in device_type.topics:
        if topic.name == "device_msg":
            return topic.template.replace("{sn}", sn)
    raise YarboSDKError(f"No device_msg topic defined for device type: {type_id}")


def resolve_topic_by_name(sn: str, type_id: str, topic_name: str) -> str:
    """Look up a topic template by name for a device type and substitute the SN.

    Args:
        sn: Device serial number.
        type_id: Device type ID.
        topic_name: The topic name to look up (e.g. "heart_beat", "device_msg").

    Returns:
        Resolved topic string with {sn} substituted.

    Raises:
        YarboSDKError: If device type is unknown or topic name is not found.
    """
    device_type = get_device_type(type_id)
    if device_type is None:
        raise YarboSDKError(f"Unknown device type: {type_id}")
    for topic in device_type.topics:
        if topic.name == topic_name:
            return topic.template.replace("{sn}", sn)
    raise YarboSDKError(
        f"No topic '{topic_name}' defined for device type: {type_id}"
    )


def extract_field(data: dict, field_path: str) -> Any:
    """Extract a value from a nested dict using dot-separated path.

    Args:
        data: Nested dictionary (e.g. MQTT message payload).
        field_path: Dot-separated key path (e.g. "BatteryMSG.capacity").

    Returns:
        The value at the path, or None if any key is missing.
    """
    current = data
    for key in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
