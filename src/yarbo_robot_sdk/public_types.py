"""Public type aliases for the Yarbo SDK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

DeviceData: TypeAlias = dict[str, Any]
"""DeviceMSG-like payload or data_feedback payload represented as a dict."""

CommandPayload: TypeAlias = dict[str, Any]
"""MQTT command payload represented as a dict."""

RawMqttCallback: TypeAlias = Callable[[str, bytes], Any]
"""Callback for raw MQTT subscriptions: ``(topic, payload_bytes)``."""

StatusCallback: TypeAlias = Callable[[str, DeviceData], Any]
"""Callback for decoded DeviceMSG-style payloads: ``(topic, data)``."""

DataFeedbackCallback: TypeAlias = Callable[[str, DeviceData], Any]
"""Callback for decoded data_feedback payloads: ``(topic, data)``."""
