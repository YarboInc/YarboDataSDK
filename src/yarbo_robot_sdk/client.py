"""YarboClient — main SDK entry point."""

import json
from collections.abc import Callable
from typing import Any

from yarbo_robot_sdk import endpoints
from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.codec import (
    decode_mqtt_payload,
    encode_mqtt_payload,
    parse_version,
    should_compress,
)
from yarbo_robot_sdk.config import DEFAULT_API_BASE_URL
from yarbo_robot_sdk.config_provider import ConfigProvider
from yarbo_robot_sdk.device_helpers import (
    extract_field,
    resolve_device_msg_topic,
    resolve_topic_by_name,
)
from yarbo_robot_sdk.device_registry import (
    DeviceType,
    get_control_field_definitions,
    get_device_type,
    list_device_types,
    resolve_control_topic,
)
from yarbo_robot_sdk.exceptions import AuthenticationError, YarboSDKError
from yarbo_robot_sdk.models import Device
from yarbo_robot_sdk.mqtt_client import MqttClient
from yarbo_robot_sdk.rest_client import RestClient


class YarboClient:
    """Yarbo Robot SDK client.

    Usage::

        # Dev — pass all config explicitly
        client = YarboClient(
            api_base_url="https://api.yarbo.com",
            mqtt_host="mqtt.yarbo.com",
            mqtt_port=8883,
            rsa_public_key="-----BEGIN PUBLIC KEY-----\\n..."
        )

        # Production — only api_base_url required, rest fetched from cloud
        client = YarboClient(api_base_url="https://api.yarbo.com")

        client.login("user@email.com", "password")
        devices = client.get_devices()

        client.mqtt_connect()
        client.subscribe_device_message("SN123", "snowbot", my_callback)
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        mqtt_host: str | None = None,
        mqtt_port: int | None = None,
        mqtt_use_tls: bool | None = None,
        rsa_public_key: str | None = None,
    ):
        self._config = ConfigProvider(
            api_base_url=api_base_url or DEFAULT_API_BASE_URL,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_use_tls=mqtt_use_tls,
            rsa_public_key=rsa_public_key,
        )

        _api_base = self._config.get("api_base_url")
        if not _api_base:
            raise YarboSDKError("api_base_url is required")

        _rsa_key = self._config.get("rsa_public_key")
        if not _rsa_key:
            raise YarboSDKError(
                "rsa_public_key is required: pass via constructor or ensure cloud config provides it"
            )

        self._api_base_url = _api_base
        self._auth = AuthManager(_api_base, _rsa_key)
        self._rest = RestClient(self._auth, _api_base)
        self._mqtt: MqttClient | None = None

        # Per-device firmware version cache: {sn: (major, minor, patch)}
        self._firmware_versions: dict[str, tuple[int, int, int]] = {}

    # --- Auth ---

    def login(self, username: str, password: str) -> None:
        """Login with username and password (password is RSA-encrypted internally)."""
        self._auth.login(username, password)

    def restore_session(self, username: str, token: str, refresh_token: str) -> None:
        """Restore a previous session from saved tokens (no login needed)."""
        self._auth.restore(username, token, refresh_token)

    @property
    def token(self) -> str | None:
        """Current JWT token. Host apps can read this for persistence."""
        return self._auth.token

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token. Host apps can read this for persistence."""
        return self._auth.refresh_token

    # --- REST API ---

    def get_devices(self) -> list[Device]:
        """Get all devices linked to the current account."""
        data = self._rest.get(endpoints.DEVICES_LIST)
        return [Device(**d) for d in data["devices"]]

    # --- MQTT ---

    def mqtt_connect(self) -> None:
        """Connect to the MQTT broker using token-based JWT auth."""
        if self._mqtt is None:
            mqtt_host = self._config.get("mqtt_host")
            mqtt_port = self._config.get("mqtt_port")
            mqtt_use_tls = self._config.get("mqtt_use_tls")

            if not mqtt_host or not mqtt_port:
                raise YarboSDKError(
                    "mqtt_host and mqtt_port are required: "
                    "pass via constructor or ensure cloud config provides them"
                )

            self._mqtt = MqttClient(
                auth_manager=self._auth,
                host=mqtt_host,
                port=mqtt_port,
                use_tls=mqtt_use_tls if mqtt_use_tls is not None else True,
            )
        self._mqtt.connect()

    def mqtt_subscribe(self, topic: str, callback: Callable[[str, bytes], Any]) -> None:
        """Subscribe to an MQTT topic with a callback."""
        if self._mqtt is None:
            raise YarboSDKError("MQTT not connected. Call mqtt_connect() first.")
        self._mqtt.subscribe(topic, callback)

    def mqtt_unsubscribe(self, topic: str) -> None:
        """Unsubscribe from an MQTT topic."""
        if self._mqtt is None:
            raise YarboSDKError("MQTT not connected.")
        self._mqtt.unsubscribe(topic)

    def mqtt_disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._mqtt:
            self._mqtt.disconnect()

    # --- High-level device methods ---

    def get_device_status(self, sn: str) -> dict:
        """Get full device status via REST API."""
        return self._rest.get(endpoints.DEVICE_DETAIL.format(sn=sn))

    def get_battery(self, sn: str) -> dict | None:
        """Get battery info. Returns {'capacity': int, 'status': int, ...}."""
        status = self.get_device_status(sn)
        return extract_field(status, "BatteryMSG")

    def get_position(self, sn: str) -> dict | None:
        """Get device position. Returns {'x': float, 'y': float, 'phi': float}."""
        status = self.get_device_status(sn)
        return extract_field(status, "CombinedOdom")

    def get_working_state(self, sn: str) -> int | None:
        """Get working state enum value."""
        status = self.get_device_status(sn)
        return extract_field(status, "StateMSG.working_state")

    def subscribe_device_message(
        self,
        sn: str,
        type_id: str,
        callback: Callable[[str, dict], Any],
    ) -> None:
        """Subscribe to device real-time message (snowbot/{sn}/device/DeviceMSG).

        Callback receives (topic: str, data: dict) where data is the parsed JSON payload.
        Automatically decompresses zlib-compressed messages and falls back to plaintext.
        Also extracts and caches the device firmware version from the 'version' field.
        """
        topic = resolve_device_msg_topic(sn, type_id)

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}
                callback(topic_str, data)
                return
            # Auto-extract and cache firmware version
            version_str = data.get("version", "")
            if version_str:
                parsed = parse_version(str(version_str))
                if parsed is not None:
                    self._firmware_versions[sn] = parsed
            callback(topic_str, data)

        self.mqtt_subscribe(topic, _wrapper)

    def unsubscribe_device_message(self, sn: str, type_id: str) -> None:
        """Unsubscribe from device real-time message."""
        topic = resolve_device_msg_topic(sn, type_id)
        self.mqtt_unsubscribe(topic)

    def subscribe_heart_beat(
        self,
        sn: str,
        type_id: str,
        callback: Callable[[str, dict], Any],
    ) -> None:
        """Subscribe to device heart beat topic (snowbot/{sn}/device/heart_beat).

        Callback receives (topic: str, data: dict) where data is the parsed payload,
        e.g. {"working_state": 0}. Automatically handles zlib-compressed messages.
        """
        topic = resolve_topic_by_name(sn, type_id, "heart_beat")

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}
            callback(topic_str, data)

        self.mqtt_subscribe(topic, _wrapper)

    def mqtt_publish_command(
        self,
        sn: str,
        type_id: str,
        command_topic_name: str,
        payload: dict,
    ) -> None:
        """Publish a command to a device control topic.

        Automatically compresses the payload with zlib if the device firmware
        version is >= 3.9.0; otherwise sends plaintext JSON.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            command_topic_name: Name of the control topic (from control_topics[].name).
            payload: Command payload dict to send.

        Raises:
            YarboSDKError: If MQTT is not connected or the topic name is unknown.
        """
        if self._mqtt is None:
            raise YarboSDKError("MQTT not connected. Call mqtt_connect() first.")

        topic = resolve_control_topic(sn, type_id, command_topic_name)
        fw = self._firmware_versions.get(sn)
        if should_compress(fw):
            encoded = encode_mqtt_payload(payload)
        else:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        self._mqtt.publish(topic, encoded)

    def set_working_state(self, sn: str, type_id: str, state: int) -> None:
        """Set device working state.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            state: 0 = standby, 1 = working.
        """
        self.mqtt_publish_command(sn, type_id, "set_working_state", {"state": state})

    # --- Device Registry ---

    def get_device_type(self, type_id: str) -> DeviceType | None:
        """Query device type capabilities from the registry."""
        return get_device_type(type_id)

    def list_device_types(self) -> list[DeviceType]:
        """List all registered device types."""
        return list_device_types()

    # --- Lifecycle ---

    def close(self) -> None:
        """Clean up resources."""
        self.mqtt_disconnect()
