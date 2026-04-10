"""YarboClient — main SDK entry point."""

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

_LOGGER = logging.getLogger(__name__)

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
    resolve_device_msg_topic,
    resolve_topic_by_name,
)
from yarbo_robot_sdk.device_registry import resolve_control_topic
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

        # data_feedback listeners: {sn: [(topic_filter, callback), ...]}
        self._feedback_listeners: dict[str, list[tuple[str, Callable]]] = {}
        self._feedback_lock = threading.Lock()

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

    def subscribe_data_feedback(
        self,
        sn: str,
        type_id: str,
        callback: Callable[[str, dict], Any] | None = None,
    ) -> None:
        """Subscribe to device data_feedback topic (snowbot/{sn}/device/data_feedback).

        This topic receives responses to app commands (e.g. read_gps_ref).
        Response format: {"topic": "...", "msg": "...", "state": 0, "data": {...}}

        The callback receives (topic: str, data: dict). Internally, messages are
        also dispatched to one-time listeners registered by request_with_feedback().

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            callback: Optional callback for all data_feedback messages.
        """
        topic = resolve_topic_by_name(sn, type_id, "data_feedback")

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}

            # Dispatch to one-time listeners registered by request_with_feedback
            response_topic = data.get("topic", "")
            with self._feedback_lock:
                listeners = self._feedback_listeners.get(sn, [])
                for topic_filter, listener_cb in listeners:
                    if topic_filter == response_topic:
                        listener_cb(topic_str, data)

            # Also invoke the general callback if provided
            if callback is not None:
                callback(topic_str, data)

        self.mqtt_subscribe(topic, _wrapper)

    def request_with_feedback(
        self,
        sn: str,
        type_id: str,
        command_topic_name: str,
        payload: dict,
        response_topic_filter: str,
        timeout: float = 10.0,
    ) -> dict:
        """Publish a command and wait for the matching data_feedback response.

        This is a synchronous blocking method. In HA, call via async_add_executor_job.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            command_topic_name: Control topic name to publish to.
            payload: Command payload dict.
            response_topic_filter: Expected 'topic' field value in the data_feedback response.
            timeout: Maximum seconds to wait for response.

        Returns:
            The full response dict from data_feedback.

        Raises:
            TimeoutError: If no matching response arrives within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        event = threading.Event()
        result: dict = {}

        def _on_match(topic_str: str, data: dict) -> None:
            result.update(data)
            event.set()

        # Register one-time listener
        with self._feedback_lock:
            if sn not in self._feedback_listeners:
                self._feedback_listeners[sn] = []
            entry = (response_topic_filter, _on_match)
            self._feedback_listeners[sn].append(entry)

        try:
            # Publish the command
            self.mqtt_publish_command(sn, type_id, command_topic_name, payload)

            # Wait for matching response
            if not event.wait(timeout):
                raise TimeoutError(
                    f"No data_feedback response for '{response_topic_filter}' "
                    f"within {timeout}s"
                )

            # Check response state
            state = result.get("state")
            if state is not None and state != 0:
                raise YarboSDKError(
                    f"Command '{response_topic_filter}' failed with state={state}: "
                    f"{result.get('msg', '')}"
                )

            return result
        finally:
            # Clean up one-time listener
            with self._feedback_lock:
                listeners = self._feedback_listeners.get(sn, [])
                if entry in listeners:
                    listeners.remove(entry)

    def read_gps_ref(self, sn: str, type_id: str, timeout: float = 10.0) -> dict:
        """Request GPS reference origin coordinates from the device.

        Sends read_gps_ref command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing data.ref.latitude, data.ref.longitude,
            data.rtkFixType, etc.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "read_gps_ref", {}, "read_gps_ref", timeout
        )

    def get_map(self, sn: str, type_id: str, timeout: float = 30.0) -> dict:
        """Request map/zone data from the device.

        Sends get_map command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response (default 30s due to
                large payload size).

        Returns:
            Response dict containing data.areas, data.pathways, data.sidewalks,
            data.deadends, data.chargingData, etc.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "get_map", {}, "get_map", timeout
        )

    def read_all_plan(self, sn: str, type_id: str, timeout: float = 10.0) -> dict:
        """Request all auto plans from the device.

        Sends read_all_plan command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing data.data (list of plans with id, name,
            areaIds, enable_self_order).

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "read_all_plan", {}, "read_all_plan", timeout
        )

    def get_device_msg(self, sn: str, type_id: str, timeout: float = 10.0) -> dict:
        """Request full DeviceMSG snapshot from the device.

        Sends get_device_msg command and waits for the response via data_feedback.
        The response structure is identical to the real-time DeviceMSG push but
        contains all fields (some fields are omitted in real-time push for
        bandwidth savings).

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing the full DeviceMSG snapshot.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "get_device_msg", {}, "get_device_msg", timeout
        )

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

        _LOGGER.debug(
            "MQTT publish → topic=%s payload=%s compressed=%s",
            topic, payload, should_compress(fw),
        )
        self._mqtt.publish(topic, encoded)

    # --- Lifecycle ---

    def close(self) -> None:
        """Clean up resources."""
        self.mqtt_disconnect()
